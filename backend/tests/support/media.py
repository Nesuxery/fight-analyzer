"""Synthetic test videos made with the bundled FFmpeg."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

from fight_analyzer.system.ffmpeg import locate_ffmpeg

FFMPEG = locate_ffmpeg().path


def _run(args: list[str]) -> None:
    subprocess.run([FFMPEG, "-hide_banner", "-v", "error", "-y", *args], check=True,
                   stdin=subprocess.DEVNULL)


def make_video(path: Path, *, seconds: float = 2, size: str = "320x180", rate: str = "25",
               audio: bool = False, extra_output: list[str] | None = None) -> Path:
    args = ["-f", "lavfi", "-i", f"testsrc2=size={size}:rate={rate}:duration={seconds}"]
    if audio:
        args += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}", "-c:a", "aac"]
    args += ["-c:v", "libx264", "-pix_fmt", "yuv420p", *(extra_output or []), str(path)]
    _run(args)
    return path


def make_rotated(src: Path, path: Path, degrees: int = 90) -> Path:
    """Same pixels as `src` with a display-matrix rotation tag."""
    _run(["-display_rotation:v:0", str(degrees), "-i", str(src), "-c", "copy", str(path)])
    return path


def make_person_clip(path: Path, *, seconds: float = 1, rate: int = 5) -> Path:
    """Short clip of the photo of two people bundled with Ultralytics."""
    # Locate the bundled photo without importing ultralytics (no side effects).
    spec = importlib.util.find_spec("ultralytics")
    image = Path(spec.submodule_search_locations[0]) / "assets" / "zidane.jpg"
    _run(["-loop", "1", "-i", str(image), "-t", str(seconds), "-r", str(rate),
          "-vf", "scale=640:-2,format=yuv420p", "-c:v", "libx264", str(path)])
    return path
