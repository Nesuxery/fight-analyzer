"""Video metadata contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .common import Contract

Rotation = Literal[0, 90, 180, 270]


class VideoInfo(Contract):
    """Properties of the prepared (analysis) video that all frame indices and
    pixel coordinates refer to. Width/height are the displayed size, i.e.
    after applying the container rotation."""

    width: int = Field(gt=0, description="Frame width in pixels.")
    height: int = Field(gt=0, description="Frame height in pixels.")
    fps: float = Field(gt=0, description="Frames per second (exact = fps_num / fps_den).")
    frame_count: int = Field(ge=0, description="Number of decodable frames.")
    duration_ms: float = Field(ge=0, description="Duration in milliseconds.")
    codec: str | None = Field(default=None, description="Video codec name, e.g. 'h264'.")
    rotation_deg: Rotation = Field(
        default=0, description="Rotation that was applied to reach width/height."
    )
    fps_num: int | None = Field(default=None, gt=0, description="Constant frame rate numerator.")
    fps_den: int | None = Field(default=None, gt=0, description="Constant frame rate denominator.")
    has_audio: bool = False


class SourceVideo(Contract):
    """The file the user uploaded, as probed by FFmpeg."""

    filename: str = Field(max_length=255)
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    container: str | None = None
    codec: str | None = None
    width: int = Field(gt=0, description="Displayed width (rotation applied).")
    height: int = Field(gt=0, description="Displayed height (rotation applied).")
    fps: float | None = Field(default=None, description="Average frame rate reported by FFmpeg.")
    duration_ms: float = Field(ge=0)
    rotation_deg: Rotation = 0
    has_audio: bool = False


class TranscodeInfo(Contract):
    """Settings used to produce the analysis copy (part of its cache key)."""

    version: int = Field(ge=1, description="Bumped whenever the FFmpeg recipe changes.")
    max_short_side: int
    max_fps: float
    crf: int
    preset: str
    audio_bitrate_k: int
    ffmpeg_version: str | None = None


class AnalysisVideo(Contract):
    """Constant-frame-rate, browser-playable H.264 copy used by both the
    analysis engine and the browser."""

    video: VideoInfo
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)
    cache_key: str
    cache_hit: bool = False
    transcode: TranscodeInfo
