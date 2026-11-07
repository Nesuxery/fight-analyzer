"""Pose cache: cache/pose/<key>/manifest.json + NumPy arrays.

No pickle anywhere: arrays are plain numeric .npy files written and read with
allow_pickle=False, metadata is JSON following the PoseCacheManifest
contract. The key covers the analysis video content (SHA-256), the model
(name, weights SHA-256, framework version), the analysis settings and the
schema version, so any change produces a new entry instead of stale data.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from fight_analyzer.contracts import (
    KEYPOINT_COUNT,
    SCHEMA_VERSION,
    BoundingBox,
    FrameRecord,
    Keypoint,
    ModelInfo,
    PersonDetection,
    PoseAnalysisSettings,
    PoseArrayInfo,
    PoseCacheManifest,
    VideoInfo,
)
from fight_analyzer.contracts.common import utcnow
from fight_analyzer.fsutil import cache_key, sha256_file, staging_dir

CACHE_FORMAT = 1
MANIFEST = "manifest.json"

# name -> (dtype, ndim, trailing shape)
ARRAY_SPECS: dict[str, tuple[str, int, tuple[int, ...]]] = {
    "frame_index": ("int32", 1, ()),
    "timestamp_ms": ("float64", 1, ()),
    "det_offsets": ("int64", 1, ()),
    "boxes": ("float32", 2, (4,)),
    "box_conf": ("float32", 1, ()),
    "keypoints": ("float32", 3, (KEYPOINT_COUNT, 3)),
}


class CacheCorrupt(Exception):
    pass


@dataclass
class PoseArrays:
    frame_index: np.ndarray
    timestamp_ms: np.ndarray
    det_offsets: np.ndarray
    boxes: np.ndarray
    box_conf: np.ndarray
    keypoints: np.ndarray

    @property
    def frame_count(self) -> int:
        return int(self.frame_index.shape[0])

    @property
    def detection_count(self) -> int:
        return int(self.boxes.shape[0])

    def max_persons(self) -> int:
        return int(np.diff(self.det_offsets).max()) if self.frame_count else 0

    def validate(self) -> None:
        f, n = self.frame_count, self.detection_count
        for name, (dtype, ndim, tail) in ARRAY_SPECS.items():
            arr = getattr(self, name)
            if arr.dtype != np.dtype(dtype) or arr.ndim != ndim or tuple(arr.shape[1:]) != tail:
                raise CacheCorrupt(f"{name}: unexpected dtype/shape {arr.dtype}{arr.shape}")
        if self.timestamp_ms.shape[0] != f or self.det_offsets.shape[0] != f + 1:
            raise CacheCorrupt("per-frame arrays disagree on frame count")
        if self.box_conf.shape[0] != n or self.keypoints.shape[0] != n:
            raise CacheCorrupt("per-detection arrays disagree on detection count")
        if f and (self.det_offsets[0] != 0 or self.det_offsets[-1] != n
                  or np.any(np.diff(self.det_offsets) < 0)):
            raise CacheCorrupt("det_offsets is not a valid index")

    def frame(self, i: int) -> FrameRecord:
        """FrameRecord for row i."""
        a, b = int(self.det_offsets[i]), int(self.det_offsets[i + 1])
        return frame_record(int(self.frame_index[i]), float(self.timestamp_ms[i]),
                            self.boxes[a:b], self.box_conf[a:b], self.keypoints[a:b])


def frame_record(frame_index: int, timestamp_ms: float, boxes: np.ndarray, conf: np.ndarray,
                 keypoints: np.ndarray, decimals: int = 1) -> FrameRecord:
    """Contract form of one frame's detections (coordinates rounded for transport)."""
    detections = []
    for d in range(boxes.shape[0]):
        x1, y1, x2, y2 = (round(float(v), decimals) for v in boxes[d])
        detections.append(PersonDetection(
            detection_id=d,
            bbox=BoundingBox(x1=x1, y1=y1, x2=max(x1, x2), y2=max(y1, y2)),
            confidence=round(float(np.clip(conf[d], 0, 1)), 3),
            keypoints=[Keypoint(x=round(float(k[0]), decimals), y=round(float(k[1]), decimals),
                                confidence=round(float(np.clip(k[2], 0, 1)), 3))
                       for k in keypoints[d]],
        ))
    return FrameRecord(frame_index=frame_index, timestamp_ms=round(timestamp_ms, 3),
                       detections=detections)


# Cache keys depend on the format of the stored data (its own version), not on the
# contract schema: a new optional field elsewhere must not force hours of pose
# extraction again. Frozen at the schema the existing entries were written with.
KEY_SCHEMA = "1.2.0"


def pose_cache_key(video_sha256: str, model: ModelInfo,
                   settings: PoseAnalysisSettings) -> tuple[str, dict[str, object]]:
    inputs: dict[str, object] = {
        "kind": "pose",
        "cache_format": CACHE_FORMAT,
        "schema_version": KEY_SCHEMA,
        "video_sha256": video_sha256,
        "model": {"name": model.name, "weights_sha256": model.weights_sha256,
                  "framework_version": model.framework_version},
        "settings": settings.model_dump(mode="json"),
    }
    return cache_key(inputs), inputs


def entry_dir(cache_root: Path, key: str) -> Path:
    return cache_root / "pose" / key


def write_entry(cache_root: Path, key: str, key_inputs: dict[str, object], *, video: VideoInfo,
                video_sha256: str, model: ModelInfo, settings: PoseAnalysisSettings,
                arrays: PoseArrays, processing_s: float | None) -> PoseCacheManifest:
    arrays.validate()
    final = entry_dir(cache_root, key)
    with staging_dir(final) as stage:
        infos: dict[str, PoseArrayInfo] = {}
        for name in ARRAY_SPECS:
            arr = np.ascontiguousarray(getattr(arrays, name))
            path = stage / f"{name}.npy"
            np.save(path, arr, allow_pickle=False)
            infos[name] = PoseArrayInfo(file=path.name, dtype=str(arr.dtype),
                                        shape=list(arr.shape), sha256=sha256_file(path))
        manifest = PoseCacheManifest(
            cache_key=key, key_inputs=key_inputs, created_at=utcnow(),
            video=video, video_sha256=video_sha256, model=model, settings=settings,
            frame_count=arrays.frame_count, detection_count=arrays.detection_count,
            max_persons=arrays.max_persons(), processing_s=processing_s, arrays=infos,
        )
        (stage / MANIFEST).write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return manifest


def read_manifest(cache_root: Path, key: str) -> PoseCacheManifest | None:
    path = entry_dir(cache_root, key) / MANIFEST
    if not path.is_file():
        return None
    try:
        manifest = PoseCacheManifest.model_validate_json(path.read_text(encoding="utf-8"))
    except ValueError:
        return None
    return manifest if manifest.cache_key == key else None


def load_arrays(cache_root: Path, manifest: PoseCacheManifest, *, check_hashes: bool = True,
                mmap: bool = False) -> PoseArrays:
    """Load (and by default hash-verify) an entry. Raises CacheCorrupt."""
    d = entry_dir(cache_root, manifest.cache_key)
    loaded: dict[str, np.ndarray] = {}
    for name in ARRAY_SPECS:
        info = manifest.arrays.get(name)
        if info is None:
            raise CacheCorrupt(f"manifest lacks {name}")
        path = d / info.file
        if not path.is_file():
            raise CacheCorrupt(f"missing {info.file}")
        if check_hashes and sha256_file(path) != info.sha256:
            raise CacheCorrupt(f"{info.file} does not match its checksum")
        try:
            arr = np.load(path, allow_pickle=False, mmap_mode="r" if mmap else None)
        except ValueError as exc:  # object arrays need pickle: refused
            raise CacheCorrupt(f"{info.file}: {exc}") from exc
        if list(arr.shape) != info.shape or str(arr.dtype) != info.dtype:
            raise CacheCorrupt(f"{info.file}: shape/dtype differ from manifest")
        loaded[name] = arr
    arrays = PoseArrays(**loaded)
    arrays.validate()
    return arrays
