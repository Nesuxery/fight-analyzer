"""Probe video files with FFmpeg (no ffprobe needed).

`probe_video` parses the stream header FFmpeg prints for an input;
`check_decodable` really decodes the first frames, so a renamed non-video or
a corrupt file is rejected even when its extension looks right.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from fight_analyzer.system.ffmpeg import locate_ffmpeg

_DURATION = re.compile(r"Duration:\s*(\d+):(\d{2}):(\d{2}(?:\.\d+)?)")
_INPUT = re.compile(r"Input #0, (.+?), from ")
_VIDEO = re.compile(r"Stream #\d+:\d+\S*: Video: ([^\s,]+)")
_AUDIO = re.compile(r"Stream #\d+:\d+\S*: Audio: ")
_SIZE = re.compile(r"(?<![\dxa-f])(\d{2,5})x(\d{2,5})(?!\d)")
_SAR = re.compile(r"SAR (\d+):(\d+)")
_FPS = re.compile(r"([\d.]+) fps")
_TBR = re.compile(r"([\d.]+)(k?) tbr")
_ROTATION = re.compile(r"rotation of (-?[\d.]+) degrees")
_ROTATE_TAG = re.compile(r"^\s*rotate\s*:\s*(-?\d+)", re.MULTILINE)


class ProbeError(Exception):
    """Invalid or unsupported video. `message` is shown to the user."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ProbeResult:
    container: str | None
    codec: str | None
    coded_width: int
    coded_height: int
    width: int  # displayed: square pixels, rotation applied
    height: int
    rotation_deg: int  # clockwise rotation needed for display: 0/90/180/270
    fps: float | None
    duration_s: float | None
    has_audio: bool


def _ffmpeg() -> str:
    info = locate_ffmpeg()
    if not info.path:
        raise ProbeError("ffmpeg_unavailable", "FFmpeg bulunamadı.")
    return info.path


def _snap_rotation(display_matrix_deg: float) -> int:
    # FFmpeg's display matrix angle is counter-clockwise; convert to the
    # clockwise rotation a player applies, snapped to a right angle.
    return int(round(-display_matrix_deg / 90.0)) * 90 % 360


def parse_header(text: str) -> ProbeResult:
    if "Input #0" not in text:
        raise ProbeError("invalid_video", "Dosya çözümlenebilir bir video değil.")
    lines = text.splitlines()
    video_idx = next((i for i, line in enumerate(lines) if _VIDEO.search(line)), None)
    if video_idx is None:
        raise ProbeError("no_video_stream", "Dosyada video akışı bulunamadı.")
    vline = lines[video_idx]
    codec = _VIDEO.search(vline).group(1)  # type: ignore[union-attr]
    # Video stream side data / metadata until the next stream.
    block_lines = [vline]
    for line in lines[video_idx + 1:]:
        if "Stream #" in line:
            break
        block_lines.append(line)
    block = "\n".join(block_lines)

    size = _SIZE.search(vline.split(codec, 1)[-1])
    if not size:
        raise ProbeError("invalid_video", "Video çözünürlüğü okunamadı.")
    coded_w, coded_h = int(size.group(1)), int(size.group(2))
    if coded_w <= 0 or coded_h <= 0:
        raise ProbeError("invalid_video", "Video çözünürlüğü geçersiz.")

    width, height = coded_w, coded_h
    if (sar := _SAR.search(vline)) and int(sar.group(2)) > 0 and int(sar.group(1)) > 0:
        num, den = int(sar.group(1)), int(sar.group(2))
        if num != den:
            width = round(coded_w * num / den)

    rotation = 0
    if m := _ROTATION.search(block):
        rotation = _snap_rotation(float(m.group(1)))
    elif m := _ROTATE_TAG.search(block):
        rotation = int(m.group(1)) % 360 // 90 * 90
    if rotation in (90, 270):
        width, height = height, width

    fps = None
    if m := _FPS.search(vline):
        fps = float(m.group(1))
    elif m := _TBR.search(vline):
        fps = float(m.group(1)) * (1000 if m.group(2) else 1)

    duration = None
    if m := _DURATION.search(text):
        duration = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))

    container = m.group(1) if (m := _INPUT.search(text)) else None
    return ProbeResult(
        container=container,
        codec=codec,
        coded_width=coded_w,
        coded_height=coded_h,
        width=width,
        height=height,
        rotation_deg=rotation,
        fps=fps if fps and fps > 0 else None,
        duration_s=duration,
        has_audio=bool(_AUDIO.search(text)),
    )


def probe_video(path: Path, timeout_s: float = 30) -> ProbeResult:
    try:
        proc = subprocess.run([_ffmpeg(), "-hide_banner", "-nostdin", "-i", str(path)],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout_s)
    except subprocess.TimeoutExpired:
        raise ProbeError("invalid_video", "Video bilgileri zamanında okunamadı.") from None
    return parse_header(proc.stderr)


def check_decodable(path: Path, frames: int = 5, timeout_s: float = 60) -> int:
    """Decode the first frames; returns how many were decoded."""
    cmd = [_ffmpeg(), "-hide_banner", "-nostdin", "-v", "error", "-i", str(path),
           "-map", "0:v:0", "-frames:v", str(frames), "-f", "null", "-",
           "-progress", "pipe:1", "-nostats"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout_s)
    except subprocess.TimeoutExpired:
        raise ProbeError("undecodable_video", "Video kareleri zamanında çözülemedi.") from None
    decoded = [int(v) for v in re.findall(r"^frame=(\d+)", proc.stdout, re.MULTILINE)]
    count = decoded[-1] if decoded else 0
    if proc.returncode != 0 or count == 0:
        raise ProbeError("undecodable_video", "Video kareleri çözülemedi; dosya bozuk olabilir.")
    return count
