"""Locate the FFmpeg executable.

Order: FA_FFMPEG env var, ffmpeg on PATH, then the binary bundled with the
pinned imageio-ffmpeg package (so a fresh setup works without a system-wide
FFmpeg install).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from functools import lru_cache

from fight_analyzer.contracts import CheckStatus, FfmpegInfo


def _version(path: str) -> str | None:
    try:
        out = subprocess.run([path, "-hide_banner", "-version"], capture_output=True, text=True,
                             timeout=10, check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    # "ffmpeg version 7.1-essentials_build-www.gyan.dev Copyright ..."
    first = out.splitlines()[0] if out else ""
    parts = first.split()
    return parts[2] if len(parts) > 2 and parts[1] == "version" else None


@lru_cache(maxsize=1)
def locate_ffmpeg() -> FfmpegInfo:
    candidates: list[tuple[str, str | None]] = [
        ("env", os.environ.get("FA_FFMPEG")),
        ("path", shutil.which("ffmpeg")),
    ]
    try:
        import imageio_ffmpeg

        candidates.append(("imageio-ffmpeg", imageio_ffmpeg.get_ffmpeg_exe()))
    except (ImportError, RuntimeError):
        pass

    for source, path in candidates:
        if path and (version := _version(path)):
            return FfmpegInfo(status=CheckStatus.ok, path=path, version=version,
                              source=source)  # type: ignore[arg-type]
    return FfmpegInfo(status=CheckStatus.unavailable)
