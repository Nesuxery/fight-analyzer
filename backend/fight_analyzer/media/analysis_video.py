"""Cached analysis copies: cache/video/<key>/{analysis.mp4, video.json}.

The key covers the source file content (SHA-256) and every transcode
setting, so uploading the same file again reuses the copy instead of
re-encoding it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

import cv2

from fight_analyzer.config import TranscodeSettings
from fight_analyzer.contracts import AnalysisVideo, SourceVideo, TranscodeInfo, VideoInfo
from fight_analyzer.fsutil import cache_key, sha256_file, staging_dir
from fight_analyzer.system.ffmpeg import locate_ffmpeg

from .probe import ProbeError, probe_video
from .transcode import TRANSCODE_VERSION, transcode

VIDEO_FILE = "analysis.mp4"
META_FILE = "video.json"


def video_cache_key(source_sha256: str, settings: TranscodeSettings) -> str:
    return cache_key({
        "kind": "analysis_video",
        "transcode_version": TRANSCODE_VERSION,
        "source_sha256": source_sha256,
        "transcode": asdict(settings),
    })


def entry_dir(cache_root: Path, key: str) -> Path:
    return cache_root / "video" / key


def video_path(cache_root: Path, key: str) -> Path:
    return entry_dir(cache_root, key) / VIDEO_FILE


def load_cached(cache_root: Path, key: str) -> AnalysisVideo | None:
    d = entry_dir(cache_root, key)
    meta, mp4 = d / META_FILE, d / VIDEO_FILE
    if not (meta.is_file() and mp4.is_file()):
        return None
    try:
        av = AnalysisVideo.model_validate_json(meta.read_text(encoding="utf-8"))
    except ValueError:
        return None
    if av.cache_key != key or mp4.stat().st_size != av.size_bytes:
        return None
    return av.model_copy(update={"cache_hit": True})


def _frame_count(path: Path) -> int:
    cap = cv2.VideoCapture(str(path))
    try:
        return int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) if cap.isOpened() else 0
    finally:
        cap.release()


def prepare(cache_root: Path, source_path: Path, source: SourceVideo,
            settings: TranscodeSettings,
            on_progress: Callable[[float, int], None] | None = None) -> AnalysisVideo:
    """Return the analysis copy for `source`, transcoding only on a cache miss."""
    key = video_cache_key(source.sha256, settings)
    if cached := load_cached(cache_root, key):
        return cached
    final = entry_dir(cache_root, key)
    with staging_dir(final) as stage:
        out = stage / VIDEO_FILE
        result = transcode(source_path, out, settings, source.fps, on_progress)
        probe = probe_video(out)
        frames = _frame_count(out) or result.frames
        if frames <= 0:
            raise ProbeError("transcode_failed", "Dönüştürülen videoda kare bulunamadı.")
        rate = result.rate
        info = VideoInfo(
            width=probe.width,
            height=probe.height,
            fps=float(rate),
            fps_num=rate.numerator,
            fps_den=rate.denominator,
            frame_count=frames,
            duration_ms=frames * 1000.0 / float(rate),
            codec=probe.codec,
            rotation_deg=source.rotation_deg,  # type: ignore[arg-type]
            has_audio=probe.has_audio,
        )
        av = AnalysisVideo(
            video=info,
            sha256=sha256_file(out),
            size_bytes=out.stat().st_size,
            cache_key=key,
            cache_hit=False,
            transcode=TranscodeInfo(version=TRANSCODE_VERSION, ffmpeg_version=locate_ffmpeg().version,
                                    **asdict(settings)),
        )
        (stage / META_FILE).write_text(av.model_dump_json(indent=2), encoding="utf-8")
    return av
