"""Selection-independent tracking preparation (one pass over the analysis video).

Produces camera cuts, per-detection appearance descriptors, OC-SORT
tracklets split at contacts/gaps, and candidate frames for the selection
screen. Cached in cache/tracking_prep/<key>/ (JSON manifest + .npy arrays,
no pickle), so re-selecting fighters only re-runs the fast identity step.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Iterator
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np

from fight_analyzer.config import TrackingSettings
from fight_analyzer.contracts import SCHEMA_VERSION
from fight_analyzer.contracts.common import utcnow
from fight_analyzer.fsutil import cache_key, sha256_file, staging_dir
from fight_analyzer.pose.cache import PoseArrays

from . import appearance, candidates, cuts, tracklets

TRACKING_PREP_VERSION = 1
MANIFEST = "manifest.json"
ARRAYS = ("shot_id", "cut_step", "track_id", "contact", "feat", "feat_q", "seg_id")


@dataclass
class PrepData:
    shot_id: np.ndarray  # [F] int32
    cut_step: np.ndarray  # [F] float32, colour change to the previous frame
    track_id: np.ndarray  # [N] int32, temporary tracker id or -1
    contact: np.ndarray  # [N] uint8
    feat: np.ndarray  # [N, DIM] float32 appearance descriptors
    feat_q: np.ndarray  # [N] float32 descriptor quality
    seg_id: np.ndarray  # [N] int32 segment (tracklet piece) id
    cuts: list[int]
    candidates: list[int]
    candidate_scores: list[float]
    tracker: str


def iter_frames(path: Path) -> Iterator[np.ndarray]:
    cap = cv2.VideoCapture(str(path))
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                return
            yield frame
    finally:
        cap.release()


def compute(frames: Iterable[np.ndarray], arrays: PoseArrays, fps: float, frame_height: int,
            s: TrackingSettings, on_progress: Callable[[int], None] | None = None) -> PrepData:
    n, f_count = arrays.detection_count, arrays.frame_count
    feat = np.zeros((n, appearance.DIM), np.float32)
    feat_q = np.zeros(n, np.float32)
    scorer = cuts.CutScorer()
    t = -1
    for t, frame in enumerate(frames):
        if t >= f_count:
            break
        scorer.add(cuts.signature(frame))
        for d in range(int(arrays.det_offsets[t]), int(arrays.det_offsets[t + 1])):
            feat[d], feat_q[d] = appearance.describe(frame, arrays.keypoints[d], arrays.boxes[d])
        if on_progress and t % 10 == 0:
            on_progress(t + 1)
    seen = t + 1
    step, skip = scorer.finish()
    if seen < f_count:  # fewer decodable frames than poses: treat the rest as unchanged
        step = np.concatenate([step, np.zeros(f_count - seen, np.float32)])
        skip = np.concatenate([skip, np.ones(f_count - seen, np.float32)])
    cut_list = cuts.detect_cuts(step, skip, s)
    shot_id = cuts.shot_ids(f_count, cut_list)
    track_id = tracklets.run_tracker(arrays, shot_id, s, fps)
    contact = tracklets.contact_flags(arrays, s)
    det_frame = np.repeat(np.arange(f_count), np.diff(arrays.det_offsets)).astype(np.int64)
    seg_id = tracklets.build_segments(det_frame, track_id, contact, shot_id, s)
    scores = candidates.frame_scores(arrays, contact, shot_id, cut_list, frame_height)
    picked = candidates.pick(scores, s.candidates)
    if on_progress:
        on_progress(f_count)
    return PrepData(shot_id=shot_id, cut_step=step[:f_count], track_id=track_id,
                    contact=contact.astype(np.uint8), feat=feat, feat_q=feat_q, seg_id=seg_id,
                    cuts=cut_list, candidates=picked,
                    candidate_scores=[round(float(scores[c]), 3) for c in picked],
                    tracker=tracklets.tracker_name(s))


# Cache keys depend on the format of the stored data (its own version), not on the
# contract schema: a new optional field elsewhere must not force hours of tracking
# preparation again. Frozen at the schema the existing entries were written with.
KEY_SCHEMA = "1.2.0"


def prep_key(pose_key: str, s: TrackingSettings) -> tuple[str, dict]:
    inputs = {"kind": "tracking_prep", "version": TRACKING_PREP_VERSION,
              "schema_version": KEY_SCHEMA, "pose_key": pose_key, "settings": asdict(s)}
    return cache_key(inputs), inputs


def entry_dir(cache_root: Path, key: str) -> Path:
    return cache_root / "tracking_prep" / key


def write(cache_root: Path, key: str, inputs: dict, data: PrepData) -> None:
    with staging_dir(entry_dir(cache_root, key)) as stage:
        info = {}
        for name in ARRAYS:
            arr = np.ascontiguousarray(getattr(data, name))
            np.save(stage / f"{name}.npy", arr, allow_pickle=False)
            info[name] = {"dtype": str(arr.dtype), "shape": list(arr.shape),
                          "sha256": sha256_file(stage / f"{name}.npy")}
        manifest = {"schema_version": SCHEMA_VERSION, "cache_key": key, "key_inputs": inputs,
                    "created_at": utcnow().isoformat(), "cuts": [int(c) for c in data.cuts],
                    "candidates": [int(c) for c in data.candidates],
                    "candidate_scores": [float(v) for v in data.candidate_scores],
                    "tracker": data.tracker, "arrays": info}
        (stage / MANIFEST).write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def read(cache_root: Path, key: str, check_hashes: bool = True) -> PrepData | None:
    d = entry_dir(cache_root, key)
    try:
        manifest = json.loads((d / MANIFEST).read_text(encoding="utf-8"))
        if manifest.get("cache_key") != key:
            return None
        loaded = {}
        for name in ARRAYS:
            info = manifest["arrays"][name]
            path = d / f"{name}.npy"
            if check_hashes and sha256_file(path) != info["sha256"]:
                return None
            arr = np.load(path, allow_pickle=False)
            if list(arr.shape) != info["shape"] or str(arr.dtype) != info["dtype"]:
                return None
            loaded[name] = arr
    except (OSError, ValueError, KeyError):
        return None
    return PrepData(**loaded, cuts=list(manifest["cuts"]), candidates=list(manifest["candidates"]),
                    candidate_scores=list(manifest["candidate_scores"]), tracker=manifest["tracker"])
