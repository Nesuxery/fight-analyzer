"""Persistent job and worker state in SQLite.

The API process and the worker process share this database. WAL mode lets
the API read while the worker writes. Every call opens its own short-lived
connection, so the store is safe to use from any thread or process.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fight_analyzer import nonfight
from fight_analyzer import rounds as rounds_mod
from fight_analyzer.config import BroadcastSettings, RulesetSettings
from fight_analyzer.contracts import (
    Job,
    JobError,
    JobOutputs,
    JobStatus,
    JobType,
    MatchSetup,
    OutdatedReason,
    PipelineStage,
    ScoringSummary,
    StageProgress,
    VideoInfo,
)
from fight_analyzer.contracts.common import utcnow
from fight_analyzer.contracts.fighters import swap_fighter_ids
from fight_analyzer.export.style import corner_hex_colors

# Each entry upgrades the schema by one version (PRAGMA user_version).
MIGRATIONS: tuple[str, ...] = (
    """
    CREATE TABLE jobs (
        job_id           TEXT PRIMARY KEY,
        job_type         TEXT NOT NULL,
        status           TEXT NOT NULL,
        stage            TEXT,
        progress         REAL NOT NULL DEFAULT 0,
        message          TEXT,
        params_json      TEXT NOT NULL DEFAULT '{}',
        video_json       TEXT,
        error_json       TEXT,
        worker_id        TEXT,
        attempts         INTEGER NOT NULL DEFAULT 0,
        cancel_requested INTEGER NOT NULL DEFAULT 0,
        created_at       TEXT NOT NULL,
        updated_at       TEXT NOT NULL,
        started_at       TEXT,
        finished_at      TEXT,
        heartbeat_at     TEXT
    );
    CREATE INDEX idx_jobs_status_created ON jobs (status, created_at);
    CREATE TABLE workers (
        worker_id    TEXT PRIMARY KEY,
        pid          INTEGER NOT NULL,
        started_at   TEXT NOT NULL,
        heartbeat_at TEXT NOT NULL,
        info_json    TEXT NOT NULL DEFAULT '{}'
    );
    """,
    """
    ALTER TABLE jobs ADD COLUMN outputs_json TEXT;
    ALTER TABLE jobs ADD COLUMN progress_json TEXT;
    """,
)


def _ts(dt: datetime) -> str:
    # Fixed-width UTC ISO strings sort lexicographically in time order.
    return dt.isoformat(timespec="milliseconds")


@dataclass(frozen=True)
class WorkerRecord:
    worker_id: str
    pid: int
    started_at: datetime
    heartbeat_at: datetime
    info: dict[str, Any]


class JobStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, timeout=10, isolation_level=None)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA busy_timeout = 10000")
            conn.execute("PRAGMA synchronous = NORMAL")
            yield conn
        finally:
            conn.close()

    # ---- schema -------------------------------------------------------

    def initialize(self) -> int:
        """Create or upgrade the schema. Returns the schema version."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("BEGIN IMMEDIATE")
            try:
                version = conn.execute("PRAGMA user_version").fetchone()[0]
                for target, sql in enumerate(MIGRATIONS[version:], start=version + 1):
                    for statement in filter(str.strip, sql.split(";")):
                        conn.execute(statement)
                    conn.execute(f"PRAGMA user_version = {target}")
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            return conn.execute("PRAGMA user_version").fetchone()[0]

    def ping(self) -> None:
        with self._connect() as conn:
            conn.execute("SELECT 1 FROM jobs LIMIT 1").fetchall()

    # ---- jobs: API side -----------------------------------------------

    def create_job(self, job_type: JobType = JobType.analysis,
                   params: dict[str, Any] | None = None) -> Job:
        job_id = uuid.uuid4().hex
        now = _ts(utcnow())
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO jobs (job_id, job_type, status, params_json, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (job_id, job_type.value, JobStatus.queued.value, json.dumps(params or {}), now, now),
            )
        return self.get_job(job_id)  # type: ignore[return-value]

    def get_job(self, job_id: str) -> Job | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return _row_to_job(row) if row else None

    def get_params(self, job_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT params_json FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return json.loads(row["params_json"]) if row else {}

    def list_jobs(self, limit: int = 100, job_type: JobType | None = None) -> list[Job]:
        kind = job_type.value if job_type else None
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE ? IS NULL OR job_type = ? ORDER BY created_at DESC, rowid DESC LIMIT ?",
                (kind, kind, limit),
            ).fetchall()
        return [_row_to_job(r) for r in rows]

    def list_exports(self, source_job_id: str, limit: int = 50) -> list[Job]:
        """Export jobs made from one analysis, newest first."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE job_type = ? AND json_extract(params_json, '$.source_job_id') = ?"
                " ORDER BY created_at DESC, rowid DESC LIMIT ?",
                (JobType.export.value, source_job_id, limit),
            ).fetchall()
        return [_row_to_job(r) for r in rows]

    def count_by_status(self, job_type: JobType | None = None) -> dict[str, int]:
        kind = job_type.value if job_type else None
        with self._connect() as conn:
            rows = conn.execute("SELECT status, COUNT(*) AS n FROM jobs WHERE ? IS NULL OR job_type = ?"
                                " GROUP BY status", (kind, kind)).fetchall()
        return {r["status"]: r["n"] for r in rows}

    def request_cancel(self, job_id: str) -> Job | None:
        """Queued/waiting jobs are cancelled immediately; running jobs are
        flagged and the worker stops at its next progress report."""
        now = _ts(utcnow())
        with self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET status = 'cancelled', cancel_requested = 1, updated_at = ?,"
                " finished_at = ? WHERE job_id = ? AND status IN ('queued', 'awaiting_selection')",
                (now, now, job_id),
            )
            conn.execute(
                "UPDATE jobs SET cancel_requested = 1, updated_at = ?"
                " WHERE job_id = ? AND status = 'running'",
                (now, job_id),
            )
        return self.get_job(job_id)

    # ---- jobs: worker side --------------------------------------------

    def claim_next(self, worker_id: str) -> Job | None:
        """Atomically move the oldest queued job to running."""
        now = _ts(utcnow())
        with self._connect() as conn:
            row = conn.execute(
                "UPDATE jobs SET status = 'running', worker_id = ?, attempts = attempts + 1,"
                " started_at = COALESCE(started_at, ?), updated_at = ?, heartbeat_at = ?,"
                " error_json = NULL, progress_json = NULL"
                " WHERE job_id = (SELECT job_id FROM jobs WHERE status = 'queued'"
                "                 ORDER BY created_at, rowid LIMIT 1)"
                " RETURNING *",
                (worker_id, now, now, now),
            ).fetchone()
        return _row_to_job(row) if row else None

    def report_progress(self, job_id: str, worker_id: str, *, stage: PipelineStage | None,
                        progress: float, message: str | None = None,
                        detail: StageProgress | None = None) -> bool:
        """Store progress and refresh the job heartbeat.

        Returns True when cancellation was requested (or the job is no longer
        owned by this worker) and the caller should stop.
        """
        now = _ts(utcnow())
        with self._connect() as conn:
            row = conn.execute(
                "UPDATE jobs SET stage = ?, progress = ?, message = ?, progress_json = ?,"
                " updated_at = ?, heartbeat_at = ?"
                " WHERE job_id = ? AND worker_id = ? AND status = 'running'"
                " RETURNING cancel_requested",
                (stage.value if stage else None, min(max(progress, 0.0), 1.0), message,
                 detail.model_dump_json() if detail else None, now, now, job_id, worker_id),
            ).fetchone()
        return row is None or bool(row["cancel_requested"])

    def set_video(self, job_id: str, worker_id: str, video_json: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET video_json = ?, updated_at = ?"
                " WHERE job_id = ? AND worker_id = ? AND status = 'running'",
                (video_json, _ts(utcnow()), job_id, worker_id),
            )

    def merge_outputs(self, job_id: str, worker_id: str, **parts) -> None:
        """Update some JobOutputs fields, keeping the others."""
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                row = conn.execute(
                    "SELECT outputs_json FROM jobs WHERE job_id = ? AND worker_id = ? AND status = 'running'",
                    (job_id, worker_id)).fetchone()
                if row is not None:
                    current = JobOutputs.model_validate_json(row["outputs_json"] or "{}")
                    merged = current.model_copy(update=parts)
                    conn.execute("UPDATE jobs SET outputs_json = ?, updated_at = ? WHERE job_id = ?",
                                 (merged.model_dump_json(), _ts(utcnow()), job_id))
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise

    def update_params(self, job_id: str, patch: dict[str, Any]) -> Job | None:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                row = conn.execute("SELECT params_json FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
                if row is not None:
                    params = {**json.loads(row["params_json"] or "{}"), **patch}
                    conn.execute("UPDATE jobs SET params_json = ?, updated_at = ? WHERE job_id = ?",
                                 (json.dumps(params), _ts(utcnow()), job_id))
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise
        return self.get_job(job_id)

    def replace_scoring(self, job_id: str, summary: ScoringSummary) -> Job | None:
        """Store a momentum result computed outside the worker (the API, after an edit that
        changed the excluded parts). Only for a completed job, which no worker is writing
        to; None otherwise (a job being processed gets it from its scoring stage)."""
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                row = conn.execute("SELECT status, outputs_json FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
                if row is None or row["status"] != JobStatus.completed.value:
                    conn.execute("ROLLBACK")
                    return None
                outputs = JobOutputs.model_validate_json(row["outputs_json"] or "{}")
                conn.execute("UPDATE jobs SET outputs_json = ?, updated_at = ? WHERE job_id = ?",
                             (outputs.model_copy(update={"scoring": summary}).model_dump_json(), _ts(utcnow()),
                              job_id))
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise
        return self.get_job(job_id)

    def resubmit(self, job_id: str, *, allowed: tuple[str, ...],
                 params_patch: dict[str, Any] | Callable[[dict[str, Any]], dict[str, Any] | None] | None = None,
                 clear_outputs: tuple[str, ...] = (), message: str | None = None) -> Job | None:
        """Queue a finished/waiting job again (e.g. after a fighter selection).
        `params_patch` may be a function of the current params, evaluated inside the
        transaction (returning None aborts). Returns None when the job is not in one of
        the `allowed` statuses or the patch function refused."""
        now = _ts(utcnow())
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                row = conn.execute("SELECT status, params_json, outputs_json FROM jobs WHERE job_id = ?",
                                   (job_id,)).fetchone()
                if row is None or row["status"] not in allowed:
                    conn.execute("ROLLBACK")
                    return None
                current = json.loads(row["params_json"] or "{}")
                patch = params_patch(current) if callable(params_patch) else params_patch
                if callable(params_patch) and patch is None:
                    conn.execute("ROLLBACK")
                    return None
                params = {**current, **(patch or {})}
                outputs = JobOutputs.model_validate_json(row["outputs_json"] or "{}")
                outputs = outputs.model_copy(update={name: None for name in clear_outputs})
                conn.execute(
                    "UPDATE jobs SET status = 'queued', params_json = ?, outputs_json = ?, error_json = NULL,"
                    " worker_id = NULL, heartbeat_at = NULL, finished_at = NULL, cancel_requested = 0,"
                    " progress_json = NULL, message = ?, updated_at = ? WHERE job_id = ?",
                    (json.dumps(params), outputs.model_dump_json(), message, now, job_id))
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise
        return self.get_job(job_id)

    def swap_corners(self, job_id: str, *, allowed: tuple[str, ...], clear_outputs: tuple[str, ...],
                     message: str) -> Job | None:
        """Exchange red and blue in one transaction: every selection anchor and the names
        swap together and the job is queued again, so all results are derived again from
        the swapped fighter ids. User inputs that belong to a person (finish winner, point
        deductions) get that person's new fighter id, so they stay with the person.
        None if not allowed now or nothing was selected yet."""
        def swapped(params: dict[str, Any]) -> dict[str, Any] | None:
            selection = params.get("selection")
            if not selection:
                return None
            anchors = [{**a, "red_detection_id": a.get("blue_detection_id"),
                        "blue_detection_id": a.get("red_detection_id")} for a in selection["anchors"]]
            names = {**DEFAULT_NAMES, **(params.get("names") or {})}
            patch: dict[str, Any] = {"selection": {**selection, "anchors": anchors},
                                     "names": {"red": names["blue"], "blue": names["red"]}}
            # Every user input stored by fighter id belongs to a person: swap each one here.
            if params.get("match"):
                patch["match"] = swap_fighter_ids(MatchSetup.model_validate(params["match"])).model_dump(mode="json")
            return patch

        return self.resubmit(job_id, allowed=allowed, params_patch=swapped, clear_outputs=clear_outputs,
                             message=message)

    def pause(self, job_id: str, worker_id: str, message: str) -> None:
        """Running job waits for the user (fighter selection); the worker is free."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET status = 'awaiting_selection', message = ?, worker_id = NULL,"
                " heartbeat_at = NULL, updated_at = ?"
                " WHERE job_id = ? AND worker_id = ? AND status = 'running'",
                (message, _ts(utcnow()), job_id, worker_id),
            )

    def heartbeat_job(self, job_id: str, worker_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET heartbeat_at = ? WHERE job_id = ? AND worker_id = ?"
                " AND status = 'running'",
                (_ts(utcnow()), job_id, worker_id),
            )

    def finish(self, job_id: str, worker_id: str, status: JobStatus, *,
               error: JobError | None = None, message: str | None = None) -> None:
        if status not in (JobStatus.completed, JobStatus.failed, JobStatus.cancelled):
            raise ValueError(f"not a terminal status: {status}")
        now = _ts(utcnow())
        progress_sql = ", progress = 1" if status is JobStatus.completed else ""
        with self._connect() as conn:
            conn.execute(
                f"UPDATE jobs SET status = ?, error_json = ?, message = ?, updated_at = ?,"
                f" finished_at = ?, heartbeat_at = NULL{progress_sql}"
                " WHERE job_id = ? AND worker_id = ? AND status = 'running'",
                (status.value, error.model_dump_json() if error else None, message, now, now,
                 job_id, worker_id),
            )

    def requeue(self, job_id: str, worker_id: str, message: str) -> None:
        """Hand a running job back to the queue (e.g. worker shutting down)."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET status = 'queued', worker_id = NULL, heartbeat_at = NULL,"
                " progress_json = NULL, message = ?, updated_at = ?"
                " WHERE job_id = ? AND worker_id = ?"
                " AND status = 'running'",
                (message, _ts(utcnow()), job_id, worker_id),
            )

    def recover_stale(self, stale_after_s: float, max_attempts: int) -> int:
        """Requeue (or fail, once attempts are used up) running jobs whose
        worker stopped sending heartbeats. Returns the number of jobs touched."""
        now = utcnow()
        cutoff = _ts(now - timedelta(seconds=stale_after_s))
        error = JobError(code="worker_lost",
                         message="İşçi bu işi işlerken durdu.")
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                failed = conn.execute(
                    "UPDATE jobs SET status = 'failed', error_json = ?, worker_id = NULL,"
                    " heartbeat_at = NULL, updated_at = ?, finished_at = ?"
                    " WHERE status = 'running' AND (heartbeat_at IS NULL OR heartbeat_at < ?)"
                    " AND attempts >= ?",
                    (error.model_dump_json(), _ts(now), _ts(now), cutoff, max_attempts),
                ).rowcount
                requeued = conn.execute(
                    "UPDATE jobs SET status = 'queued', worker_id = NULL, heartbeat_at = NULL,"
                    " message = 'İşçi beklenmedik şekilde durduğu için yeniden kuyruğa alındı.',"
                    " updated_at = ?"
                    " WHERE status = 'running' AND (heartbeat_at IS NULL OR heartbeat_at < ?)",
                    (_ts(now), cutoff),
                ).rowcount
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise
        return failed + requeued

    # ---- workers ------------------------------------------------------

    def register_worker(self, worker_id: str, pid: int, info: dict[str, Any]) -> None:
        now = _ts(utcnow())
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO workers (worker_id, pid, started_at, heartbeat_at, info_json)"
                " VALUES (?, ?, ?, ?, ?)",
                (worker_id, pid, now, now, json.dumps(info)),
            )

    def heartbeat_worker(self, worker_id: str) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE workers SET heartbeat_at = ? WHERE worker_id = ?",
                         (_ts(utcnow()), worker_id))

    def remove_worker(self, worker_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM workers WHERE worker_id = ?", (worker_id,))

    def prune_workers(self, stale_after_s: float) -> None:
        cutoff = _ts(utcnow() - timedelta(seconds=stale_after_s))
        with self._connect() as conn:
            conn.execute("DELETE FROM workers WHERE heartbeat_at < ?", (cutoff,))

    def latest_worker(self) -> WorkerRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM workers ORDER BY heartbeat_at DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        return WorkerRecord(
            worker_id=row["worker_id"],
            pid=row["pid"],
            started_at=datetime.fromisoformat(row["started_at"]),
            heartbeat_at=datetime.fromisoformat(row["heartbeat_at"]),
            info=json.loads(row["info_json"]),
        )


DEFAULT_NAMES = {"red": "Dövüşçü 1", "blue": "Dövüşçü 2"}
# The video-layer corner colours of shared/overlay-style.json (one source for the
# browser overlay, the MP4 export and the `Fighter.color` field).
CORNER_COLORS = corner_hex_colors()


def _fighters(params: dict[str, Any]) -> list[dict[str, str]]:
    if not params.get("selection"):
        return []
    names = {**DEFAULT_NAMES, **(params.get("names") or {})}
    return [{"fighter_id": fid, "display_name": names[side], "color": CORNER_COLORS[side]}
            for fid, side in (("fighter_a", "red"), ("fighter_b", "blue"))]


RULESET = RulesetSettings()
BROADCAST = BroadcastSettings()
# Broadcast analyses from this version on find replays, stoppages and non-fight parts.
NONFIGHT_SINCE = 2
# Identity results from this version on use the appearance model and carry the data quality
# (tracking/identity.py IDENTITY_VERSION 6). Version 7 only lowers the confidence of some
# frames: results of version 6 stay current enough to open without the banner.
IDENTITY_SINCE = 6
# Events from this version on carry strike outcomes, target zones and damage signals (EVENTS_VERSION 4), the
# grappling states with their events and control times (EVENTS_VERSION 5) and the hidden-opponent estimate
# (EVENTS_VERSION 6: without it a grappling-heavy bout shows most of its grappling only as "not measured").
EVENTS_SINCE = 6


def _derived(params: dict[str, Any], outputs: JobOutputs, video: VideoInfo | None,
             status: str) -> dict[str, Any]:
    """Bout format, effective rounds, automatic excluded parts and what an older analysis
    lacks (no disk reads)."""
    names = {**DEFAULT_NAMES, **(params.get("names") or {})}
    bout = rounds_mod.bout_config(params, RULESET, names)
    match = MatchSetup.model_validate(params["match"]) if params.get("match") else None
    rounds, notes = [], []
    if video is not None:
        auto = outputs.broadcast.rounds if outputs.broadcast else []
        rounds, notes = rounds_mod.effective(auto, match, bout.scheduled_rounds, video.fps, bout.round_length_s)
    current = outputs.broadcast is not None and outputs.broadcast.version >= NONFIGHT_SINCE
    auto_exclusions = []
    if video is not None and current:  # an older analysis gets them when it is processed again
        claims = nonfight.from_rounds(rounds, bout.scheduled_rounds, match.ending if match else None,
                                      video.frame_count)
        found = nonfight.combine(claims, outputs.broadcast.segments, rounds, video.fps, video.frame_count,
                                 BROADCAST.min_segment_s)
        auto_exclusions = nonfight.with_dismissed(found, params.get("dismissed_auto") or [])
    outdated = []
    if outputs.tracking_prep is not None and status not in ("queued", "running"):
        if outputs.broadcast is None:
            outdated.append(OutdatedReason.broadcast_missing)
        elif not current:
            outdated.append(OutdatedReason.broadcast_outdated)
        if outputs.tracking is not None and outputs.tracking.version < IDENTITY_SINCE:
            outdated.append(OutdatedReason.identity_outdated)
        if outputs.events is not None and outputs.events.version < EVENTS_SINCE:
            outdated.append(OutdatedReason.events_outdated)
    return {"bout": bout, "rounds": rounds, "round_notes": notes, "outdated": outdated,
            "auto_exclusions": auto_exclusions}


def _row_to_job(row: sqlite3.Row) -> Job:
    params = json.loads(row["params_json"] or "{}")
    outputs = JobOutputs.model_validate_json(row["outputs_json"]) if row["outputs_json"] else JobOutputs()
    video = VideoInfo.model_validate_json(row["video_json"]) if row["video_json"] else None
    return Job(
        job_id=row["job_id"],
        job_type=row["job_type"],
        status=row["status"],
        stage=row["stage"],
        progress=row["progress"],
        message=row["message"],
        progress_detail=row["progress_json"] and json.loads(row["progress_json"]),
        source=params.get("source"),
        selection=params.get("selection"),
        exclusions=params.get("exclusions") or [],
        match=params.get("match"),
        fighters=_fighters(params),
        video=video,
        outputs=outputs,
        error=row["error_json"] and json.loads(row["error_json"]),
        attempts=row["attempts"],
        cancel_requested=bool(row["cancel_requested"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        **_derived(params, outputs, video, row["status"]),
    )
