"""Identity results cache: cache/identity/<key>/ (summary.json + .npy arrays).

Arrays are [frames, 2] (column 0 = red / fighter_a, column 1 = blue /
fighter_b): state (0 tracked, 1 occluded, 2 uncertain), det (global detection
index or -1), conf, reason (index into UncertainReason or -1).
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import numpy as np

from fight_analyzer.config import TrackingSettings
from fight_analyzer.contracts import (
    SCHEMA_VERSION,
    FighterAnchor,
    FighterFrameState,
    FighterTimeline,
    FrameRecord,
    ShotInfo,
    TrackingSummary,
    TrackState,
    TrackStateRun,
)
from fight_analyzer.fsutil import cache_key, staging_dir
from fight_analyzer.pose.cache import PoseArrays

from .identity import FIGHTERS, IDENTITY_VERSION, IdentityResult

ARRAYS = ("state", "det", "conf", "reason")
STATES = (TrackState.tracked, TrackState.occluded, TrackState.uncertain)
SUMMARY = "summary.json"


# Cache keys depend on the format of the stored data (its own version), not on the
# contract schema: a new optional field elsewhere must not force hours of identity
# tracking again. Frozen at the schema the existing entries were written with.
KEY_SCHEMA = "1.2.0"


def identity_key(prep_key: str, anchors: list[FighterAnchor], s: TrackingSettings) -> tuple[str, dict]:
    inputs = {"kind": "identity", "version": IDENTITY_VERSION, "schema_version": KEY_SCHEMA,
              "prep_key": prep_key, "settings": asdict(s),
              "anchors": sorted((a.frame_index, a.red_detection_id, a.blue_detection_id) for a in anchors)}
    return cache_key(inputs), inputs


def entry_dir(cache_root: Path, key: str) -> Path:
    return cache_root / "identity" / key


def shots_from(shot_id: np.ndarray) -> list[ShotInfo]:
    if shot_id.size == 0:
        return []
    starts = [0, *(np.flatnonzero(np.diff(shot_id)) + 1).tolist()]
    ends = [*(s - 1 for s in starts[1:]), int(shot_id.size - 1)]
    return [ShotInfo(index=i, start_frame=a, end_frame=b) for i, (a, b) in enumerate(zip(starts, ends))]


def write(cache_root: Path, key: str, result: IdentityResult, summary: TrackingSummary) -> None:
    with staging_dir(entry_dir(cache_root, key)) as stage:
        for name in ARRAYS:
            np.save(stage / f"{name}.npy", np.ascontiguousarray(getattr(result, name)), allow_pickle=False)
        (stage / SUMMARY).write_text(summary.model_dump_json(indent=2), encoding="utf-8")


def read_summary(cache_root: Path, key: str) -> TrackingSummary | None:
    try:
        return TrackingSummary.model_validate_json((entry_dir(cache_root, key) / SUMMARY).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def read_arrays(cache_root: Path, key: str) -> dict[str, np.ndarray] | None:
    d = entry_dir(cache_root, key)
    try:
        out = {name: np.load(d / f"{name}.npy", allow_pickle=False) for name in ARRAYS}
    except (OSError, ValueError):
        return None
    frames = out["state"].shape[0]
    if any(a.shape[0] != frames or a.ndim != 2 or a.shape[1] != 2 for a in out.values()):
        return None
    return out


def frame_states(arrays: dict[str, np.ndarray], t: int, first_det: int) -> list[FighterFrameState]:
    out = []
    for f, fighter in enumerate(FIGHTERS):
        d = int(arrays["det"][t, f])
        out.append(FighterFrameState(fighter_id=fighter, state=STATES[int(arrays["state"][t, f])],
                                     detection_id=d - first_det if d >= 0 else None,
                                     confidence=round(float(arrays["conf"][t, f]), 3)))
    return out


def annotated_frame(poses: PoseArrays, i: int, ident: dict[str, np.ndarray] | None,
                    track_id: np.ndarray | None = None) -> FrameRecord:
    """Frame i as the browser draws it: detections with their temporary track number and,
    where the identity is verified, the fighter id (the MP4 export draws the same records)."""
    record = poses.frame(i)
    first = int(poses.det_offsets[i])
    if track_id is not None:
        for det in record.detections:
            tid = int(track_id[first + det.detection_id])
            det.track_id = tid if tid >= 0 else None
    if ident is not None and i < ident["state"].shape[0]:
        record.fighters = frame_states(ident, i, first)
        for state in record.fighters:
            if state.detection_id is not None and state.state != "uncertain":
                record.detections[state.detection_id].fighter_id = state.fighter_id
    return record


def timeline(arrays: dict[str, np.ndarray]) -> list[FighterTimeline]:
    out = []
    for f, fighter in enumerate(FIGHTERS):
        st = arrays["state"][:, f]
        if st.size == 0:
            out.append(FighterTimeline(fighter_id=fighter, runs=[]))
            continue
        change = np.flatnonzero(np.diff(st)) + 1
        starts = [0, *change.tolist()]
        ends = [*(c - 1 for c in change.tolist()), int(st.size - 1)]
        out.append(FighterTimeline(fighter_id=fighter, runs=[
            TrackStateRun(start_frame=a, end_frame=b, state=STATES[int(st[a])]) for a, b in zip(starts, ends)]))
    return out
