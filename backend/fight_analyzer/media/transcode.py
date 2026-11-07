"""Constant-frame-rate, browser-playable analysis copy (H.264/AAC MP4).

The copy is what both the pose engine and the browser use, so frame N is at
N / fps everywhere. Rotation is applied (and the rotation tag dropped),
non-square pixels are resampled to square, the aspect ratio is kept, the
short side is capped and audio is kept when present. No B-frames, so
presentation and decode order match.
"""

from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from fight_analyzer.config import TranscodeSettings
from fight_analyzer.system.ffmpeg import locate_ffmpeg

from .probe import ProbeError

# Bump whenever the command below changes in a way that alters the output.
TRANSCODE_VERSION = 2

_COMMON_RATES = [Fraction(24000, 1001), Fraction(24), Fraction(25), Fraction(30000, 1001),
                 Fraction(30), Fraction(50), Fraction(60000, 1001), Fraction(60)]


def choose_frame_rate(source_fps: float | None, max_fps: float) -> Fraction:
    """Pick the analysis frame rate.

    Prefer a common rate that divides the source evenly (59.94 -> 29.97,
    50 -> 25), so no frames are duplicated unevenly. Otherwise keep the
    source rate when it is within the limit, else use the highest allowed
    common rate (e.g. variable 36.13 fps phone/social clips -> 30).
    """
    allowed = [r for r in _COMMON_RATES if r <= Fraction(max_fps).limit_denominator(1001)]
    if not source_fps or source_fps <= 0:
        return max(allowed) if allowed else Fraction(max_fps).limit_denominator(1001)
    best: tuple[float, Fraction] | None = None
    for rate in allowed:
        ratio = source_fps / float(rate)
        if ratio < 0.999:
            continue
        err = abs(ratio - round(ratio))
        if err < 0.005 and (best is None or (err, -rate) < (best[0], -best[1])):
            best = (err, rate)
    if best:
        return best[1]
    if source_fps <= max_fps:
        return Fraction(source_fps).limit_denominator(1001)
    return max(allowed) if allowed else Fraction(max_fps).limit_denominator(1001)


def build_command(ffmpeg: str, src: Path, dst: Path, rate: Fraction,
                  settings: TranscodeSettings) -> list[str]:
    s = settings.max_short_side
    gop = max(1, round(float(rate) * 2))
    vf = ",".join([
        # Constant frame rate first: it also normalises odd source time bases
        # (seen 1/359980000 on social-media clips) that make FFmpeg 7.1's
        # scale filter drop trailing frames.
        f"fps={rate.numerator}/{rate.denominator}",
        # square pixels, even dimensions (rotation was already applied by -autorotate)
        "scale=w='trunc(iw*sar/2)*2':h='trunc(ih/2)*2'",
        "setsar=1",
        # cap the short side, keep the aspect ratio
        f"scale=w='if(gte(iw,ih),-2,min(iw,{s}))':h='if(gte(iw,ih),min(ih,{s}),-2)'",
        "format=yuv420p",
    ])
    return [
        ffmpeg, "-hide_banner", "-nostdin", "-y", "-v", "error",
        "-i", str(src),
        "-map", "0:v:0", "-map", "0:a:0?",
        "-vf", vf,
        "-c:v", "libx264", "-preset", settings.preset, "-crf", str(settings.crf),
        "-profile:v", "high", "-bf", "0", "-g", str(gop),
        "-c:a", "aac", "-b:a", f"{settings.audio_bitrate_k}k", "-ac", "2",
        "-map_metadata", "-1", "-map_chapters", "-1",
        "-movflags", "+faststart",
        "-progress", "pipe:1", "-nostats",
        str(dst),
    ]


@dataclass(frozen=True)
class TranscodeResult:
    path: Path
    frames: int
    rate: Fraction


def transcode(src: Path, dst: Path, settings: TranscodeSettings, source_fps: float | None,
              on_progress: Callable[[float, int], None] | None = None) -> TranscodeResult:
    """Run FFmpeg; `on_progress(out_time_s, frames)` is called about twice a
    second and may raise to cancel (FFmpeg is then killed and the partial
    output removed)."""
    ffmpeg = locate_ffmpeg().path
    if not ffmpeg:
        raise ProbeError("ffmpeg_unavailable", "FFmpeg bulunamadı.")
    rate = choose_frame_rate(source_fps, settings.max_fps)
    cmd = build_command(ffmpeg, src, dst, rate, settings)
    frames = 0
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace") as err:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=err, stdin=subprocess.DEVNULL,
                                text=True, encoding="utf-8", errors="replace")
        try:
            assert proc.stdout is not None
            out_time = 0.0
            for line in proc.stdout:
                key, _, value = line.strip().partition("=")
                if key == "frame" and value.isdigit():
                    frames = int(value)
                elif key == "out_time_us" and value.lstrip("-").isdigit():
                    out_time = max(0.0, int(value) / 1e6)
                elif key == "progress" and on_progress:
                    on_progress(out_time, frames)
            proc.wait()
        except BaseException:
            stop_process(proc)
            dst.unlink(missing_ok=True)
            raise
        if proc.returncode != 0:
            dst.unlink(missing_ok=True)
            err.seek(0)
            tail = err.read()[-600:].strip()
            raise ProbeError("transcode_failed", f"Video dönüştürülemedi: {tail or proc.returncode}")
    return TranscodeResult(path=dst, frames=frames, rate=rate)


def stop_process(proc: subprocess.Popen) -> None:
    # Wait for the exit so Windows releases the half-written output file.
    if proc.poll() is None:
        proc.kill()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass
