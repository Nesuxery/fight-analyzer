"""Per-frame person detection and pose contracts.

Coordinates are pixels in the analysis video frame (VideoInfo width/height,
origin top-left, x right, y down). Points may lie slightly outside the frame.
Low-confidence joints are still reported; consumers choose their own
confidence threshold. No identity is assumed at this stage: fighter_id stays
null until the user selects the fighters.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, model_validator

from .common import JOB_ID_PATTERN, Contract, DataOrigin, VersionedContract
from .fighters import FighterFrameState, FighterId
from .video import VideoInfo


class KeypointName(StrEnum):
    """COCO-17 keypoints in model output order: index k of every keypoint list
    is the k-th member below (0 = nose ... 16 = right_ankle). This is the
    order predicted by the Ultralytics YOLO pose models (see
    https://docs.ultralytics.com/tasks/pose/#keypoint-index-map)."""

    nose = "nose"
    left_eye = "left_eye"
    right_eye = "right_eye"
    left_ear = "left_ear"
    right_ear = "right_ear"
    left_shoulder = "left_shoulder"
    right_shoulder = "right_shoulder"
    left_elbow = "left_elbow"
    right_elbow = "right_elbow"
    left_wrist = "left_wrist"
    right_wrist = "right_wrist"
    left_hip = "left_hip"
    right_hip = "right_hip"
    left_knee = "left_knee"
    right_knee = "right_knee"
    left_ankle = "left_ankle"
    right_ankle = "right_ankle"


COCO17_KEYPOINT_NAMES: tuple[str, ...] = tuple(k.value for k in KeypointName)
KEYPOINT_COUNT = len(COCO17_KEYPOINT_NAMES)


class SkeletonFormat(StrEnum):
    coco17 = "coco17"


class Keypoint(Contract):
    x: float = Field(description="Horizontal pixel coordinate.")
    y: float = Field(description="Vertical pixel coordinate.")
    confidence: float = Field(ge=0, le=1, description="Model confidence for this joint.")


class BoundingBox(Contract):
    x1: float
    y1: float
    x2: float
    y2: float

    @model_validator(mode="after")
    def _ordered(self) -> BoundingBox:
        if self.x2 < self.x1 or self.y2 < self.y1:
            raise ValueError("bounding box corners must satisfy x1 <= x2 and y1 <= y2")
        return self


class PersonDetection(Contract):
    detection_id: int = Field(ge=0, description="Index of this detection within its frame.")
    track_id: int | None = Field(
        default=None, description="Raw tracker id; may change after occlusions."
    )
    fighter_id: FighterId | None = Field(
        default=None, description="Resolved fighter identity, null for referee/others/unknown."
    )
    bbox: BoundingBox
    confidence: float = Field(ge=0, le=1, description="Person detection confidence.")
    keypoints: list[Keypoint] = Field(
        min_length=KEYPOINT_COUNT,
        max_length=KEYPOINT_COUNT,
        description="Joints in KeypointName order.",
    )


class FrameRecord(Contract):
    frame_index: int = Field(ge=0, description="0-based index into the analysis video.")
    timestamp_ms: float = Field(ge=0, description="Presentation time: frame_index / fps.")
    detections: list[PersonDetection] = Field(default_factory=list)
    fighters: list[FighterFrameState] = Field(
        default_factory=list, description="Identity state per fighter once tracking has run.")


class ModelInfo(Contract):
    name: str = Field(description="Model file name, e.g. 'yolo26s-pose.pt'.")
    framework_version: str | None = Field(default=None, description="e.g. ultralytics version.")
    device: str | None = Field(default=None, description="'cpu' or 'cuda:0'.")
    weights_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    source_url: str | None = Field(default=None, description="Official download location.")


class PoseAnalysisSettings(Contract):
    """Inference settings; part of the pose cache key."""

    imgsz: int = Field(gt=0, description="Model input size in pixels.")
    conf: float = Field(ge=0, le=1, description="Minimum person detection confidence.")
    iou: float = Field(ge=0, le=1, description="NMS IoU threshold (ignored by NMS-free models).")
    max_det: int = Field(gt=0, description="Maximum people per frame.")
    frame_step: int = Field(default=1, ge=1, description="1 = every frame is analysed.")


class PoseSummary(Contract):
    cache_key: str
    cache_hit: bool
    frame_count: int = Field(ge=0)
    detection_count: int = Field(ge=0)
    max_persons: int = Field(ge=0, description="Most people detected in a single frame.")
    model: ModelInfo
    settings: PoseAnalysisSettings
    processing_s: float | None = Field(default=None, description="Inference wall time.")


class PoseArrayInfo(Contract):
    file: str
    dtype: str
    shape: list[int]
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class PoseCacheManifest(VersionedContract):
    """manifest.json of a pose cache entry. Per-frame data lives next to it in
    NumPy .npy files (loaded with allow_pickle=False):
    frame_index[F] int32, timestamp_ms[F] float64, det_offsets[F+1] int64
    (detections of frame i are rows det_offsets[i]:det_offsets[i+1]),
    boxes[N,4] float32 (x1,y1,x2,y2), box_conf[N] float32,
    keypoints[N,17,3] float32 (x, y, confidence in KeypointName order)."""

    cache_key: str
    key_inputs: dict[str, object]
    created_at: datetime
    keypoint_names: list[KeypointName] = Field(default_factory=lambda: list(KeypointName))
    video: VideoInfo
    video_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    model: ModelInfo
    settings: PoseAnalysisSettings
    frame_count: int = Field(ge=0)
    detection_count: int = Field(ge=0)
    max_persons: int = Field(ge=0)
    processing_s: float | None = None
    arrays: dict[str, PoseArrayInfo]


class PoseSequence(VersionedContract):
    """Pose output of one job (export format)."""

    job_id: str = Field(pattern=JOB_ID_PATTERN)
    data_origin: DataOrigin
    skeleton: SkeletonFormat = SkeletonFormat.coco17
    keypoint_names: list[KeypointName] = Field(default_factory=lambda: list(KeypointName))
    video: VideoInfo
    model: ModelInfo
    frames: list[FrameRecord] = Field(default_factory=list)


class PoseChunk(VersionedContract):
    """A window of consecutive frames served to the UI."""

    job_id: str = Field(pattern=JOB_ID_PATTERN)
    data_origin: DataOrigin
    keypoint_names: list[KeypointName] = Field(default_factory=lambda: list(KeypointName))
    video: VideoInfo
    start_frame: int = Field(ge=0)
    frames: list[FrameRecord]


class PosePreview(VersionedContract):
    """Latest processed frame while pose extraction runs (sent at low rate)."""

    job_id: str = Field(pattern=JOB_ID_PATTERN)
    seq: int = Field(ge=0, description="Increments with every new preview.")
    frame: FrameRecord
    width: int = Field(gt=0, description="Analysis frame width the coordinates refer to.")
    height: int = Field(gt=0)
