"""Burn the overlay into a copy of the analysis video.

Frames are decoded in order from the analysis copy (the same file and the
same frame numbering the pose engine and the browser use), drawn on and piped
as raw BGR to FFmpeg, which encodes H.264 and copies the audio stream of the
analysis copy unchanged. FFmpeg's own output goes to a temporary file, so its
pipes can never fill up and stall the export.
"""

from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path

import cv2
import numpy as np

from fight_analyzer.config import TranscodeSettings
from fight_analyzer.contracts import VideoInfo
from fight_analyzer.media.transcode import stop_process
from fight_analyzer.system.ffmpeg import locate_ffmpeg


class ExportError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def frame_rate(video: VideoInfo) -> Fraction:
    if video.fps_num and video.fps_den:
        return Fraction(video.fps_num, video.fps_den)
    return Fraction(video.fps).limit_denominator(1001)


def build_command(ffmpeg: str, src: Path, dst: Path, video: VideoInfo, s: TranscodeSettings) -> list[str]:
    rate = frame_rate(video)
    return [
        ffmpeg, "-hide_banner", "-y", "-v", "error",
        "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{video.width}x{video.height}",
        "-framerate", f"{rate.numerator}/{rate.denominator}", "-i", "pipe:0",
        "-i", str(src),
        "-map", "0:v:0", "-map", "1:a:0?",
        "-c:v", "libx264", "-preset", s.preset, "-crf", str(s.crf), "-pix_fmt", "yuv420p",
        "-profile:v", "high", "-g", str(max(1, round(float(rate) * 2))),
        "-c:a", "copy", "-shortest",
        "-map_metadata", "-1", "-movflags", "+faststart", "-f", "mp4",
        str(dst),
    ]


def render(src: Path, dst: Path, video: VideoInfo, s: TranscodeSettings,
           draw: Callable[[int, np.ndarray], None], on_frame: Callable[[int], None]) -> int:
    """Decode `src`, call draw(i, frame) on each frame and encode to `dst`.
    `on_frame(done)` is called after every frame and may raise to cancel; FFmpeg is
    then stopped and the partial file removed. Returns the number of frames written."""
    ffmpeg = locate_ffmpeg().path
    if not ffmpeg:
        raise ExportError("ffmpeg_unavailable", "FFmpeg bulunamadı.")
    cap = cv2.VideoCapture(str(src))
    if not cap.isOpened():
        raise ExportError("decode_failed", "Analiz videosu açılamadı.")
    done = 0
    with tempfile.TemporaryFile() as err:
        proc = subprocess.Popen(build_command(ffmpeg, src, dst, video, s), stdin=subprocess.PIPE,
                                stdout=subprocess.DEVNULL, stderr=err)
        try:
            assert proc.stdin is not None
            while done < video.frame_count:
                ok, frame = cap.read()
                if not ok:
                    break
                if frame.shape[1] != video.width or frame.shape[0] != video.height:
                    frame = cv2.resize(frame, (video.width, video.height), interpolation=cv2.INTER_AREA)
                draw(done, frame)
                try:
                    proc.stdin.write(np.ascontiguousarray(frame).tobytes())
                except OSError:  # FFmpeg stopped; its error message is reported below
                    break
                done += 1
                on_frame(done)
            try:
                proc.stdin.close()
            except OSError:
                pass
            proc.wait()
        except BaseException:
            stop_process(proc)
            dst.unlink(missing_ok=True)
            raise
        finally:
            cap.release()
        if proc.returncode != 0:
            dst.unlink(missing_ok=True)
            err.seek(0)
            tail = err.read()[-600:].decode("utf-8", "replace").strip()
            raise ExportError("encode_failed", f"Video yazılamadı: {tail or proc.returncode}")
    if done == 0:
        dst.unlink(missing_ok=True)
        raise ExportError("decode_failed", "Analiz videosundan kare okunamadı.")
    return done
