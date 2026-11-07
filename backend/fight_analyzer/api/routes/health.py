from __future__ import annotations

import sqlite3
from datetime import timedelta

from fastapi import APIRouter, Response, status

from fight_analyzer import __version__
from fight_analyzer.config import ACCEPTED_EXTENSIONS
from fight_analyzer.contracts import (
    UploadLimits,
    CheckStatus,
    ComponentCheck,
    ComputeInfo,
    HealthResponse,
    JobCounts,
    PoseModelInfo,
    WorkerInfo,
)
from fight_analyzer.contracts.common import utcnow
from fight_analyzer.system.ffmpeg import locate_ffmpeg

from ..deps import SettingsDep, StoreDep

router = APIRouter(tags=["system"])


@router.get("/upload-limits", response_model=UploadLimits)
def upload_limits(settings: SettingsDep) -> UploadLimits:
    lim = settings.upload
    return UploadLimits(max_bytes=lim.max_bytes, min_duration_s=lim.min_duration_s,
                        max_duration_s=lim.max_duration_s, max_long_side=lim.max_long_side,
                        max_short_side=lim.max_short_side, min_short_side=lim.min_short_side,
                        extensions=list(ACCEPTED_EXTENSIONS))


@router.get("/health", response_model=HealthResponse)
def health(store: StoreDep, settings: SettingsDep, response: Response) -> HealthResponse:
    """Fast status check. Returns 503 only when the database is unusable."""
    now = utcnow()
    counts = JobCounts()
    worker = WorkerInfo(status=CheckStatus.unavailable)
    try:
        store.ping()
        by_status = store.count_by_status()
        counts = JobCounts(**by_status, total=sum(by_status.values()))
        database = ComponentCheck(status=CheckStatus.ok)
        if record := store.latest_worker():
            fresh = now - record.heartbeat_at <= timedelta(seconds=settings.worker_stale_after_s)
            compute = record.info.get("compute")
            worker = WorkerInfo(
                status=CheckStatus.ok if fresh else CheckStatus.unavailable,
                worker_id=record.worker_id,
                pid=record.pid,
                last_heartbeat=record.heartbeat_at,
                compute=ComputeInfo.model_validate(compute) if compute else None,
            )
    except sqlite3.Error as exc:
        database = ComponentCheck(status=CheckStatus.unavailable, detail=str(exc))
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    ffmpeg = locate_ffmpeg()
    all_ok = all(c.status is CheckStatus.ok for c in (database, worker, ffmpeg))
    return HealthResponse(
        status=CheckStatus.ok if all_ok else CheckStatus.degraded,
        app_version=__version__,
        server_time=now,
        database=database,
        worker=worker,
        ffmpeg=ffmpeg,
        pose_model=PoseModelInfo(name=settings.pose_model,
                                 present=settings.pose_model_path.is_file()),
        jobs=counts,
    )
