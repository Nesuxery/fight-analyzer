"""Health / system status contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field

from .common import Contract, VersionedContract


class CheckStatus(StrEnum):
    ok = "ok"
    degraded = "degraded"
    unavailable = "unavailable"


class ComponentCheck(Contract):
    status: CheckStatus
    detail: str | None = None


class ComputeInfo(Contract):
    """Inference device chosen by the worker (detected with PyTorch)."""

    device: Literal["cpu", "cuda"]
    device_name: str
    requested: Literal["auto", "cpu", "cuda"]
    cuda_available: bool
    torch_version: str
    cuda_version: str | None = None
    cpu_threads: int = Field(ge=1)
    note: str | None = None


class WorkerInfo(Contract):
    status: CheckStatus
    worker_id: str | None = None
    pid: int | None = None
    last_heartbeat: datetime | None = None
    compute: ComputeInfo | None = None


class FfmpegInfo(Contract):
    status: CheckStatus
    path: str | None = None
    version: str | None = None
    source: Literal["env", "path", "imageio-ffmpeg"] | None = None


class PoseModelInfo(Contract):
    name: str
    present: bool = Field(description="Whether the weights file exists locally.")


class JobCounts(Contract):
    queued: int = 0
    running: int = 0
    awaiting_selection: int = 0
    completed: int = 0
    failed: int = 0
    cancelled: int = 0
    total: int = 0


class UploadLimits(VersionedContract):
    """Server-side upload limits (also checked by the UI before uploading)."""

    max_bytes: int = Field(gt=0)
    min_duration_s: float = Field(ge=0)
    max_duration_s: float = Field(gt=0)
    max_long_side: int = Field(gt=0)
    max_short_side: int = Field(gt=0)
    min_short_side: int = Field(gt=0)
    extensions: list[str]


class ErrorResponse(VersionedContract):
    """Body of every 4xx/5xx response produced by the API itself."""

    code: str
    message: str


class HealthResponse(VersionedContract):
    status: CheckStatus = Field(
        description="ok when database, worker and FFmpeg are ok; degraded otherwise."
    )
    app_version: str
    api_version: Literal["v1"] = "v1"
    server_time: datetime
    database: ComponentCheck
    worker: WorkerInfo
    ffmpeg: FfmpegInfo
    pose_model: PoseModelInfo
    jobs: JobCounts
