"""Low-rate live preview while pose extraction runs: jobs/<id>/preview-<seq>.jpg
plus preview.json (PosePreview). Only the newest two images are kept."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from fight_analyzer.contracts import FrameRecord, PosePreview, VideoInfo
from fight_analyzer.fsutil import write_bytes_atomic, write_json_atomic

PREVIEW_JSON = "preview.json"
MAX_WIDTH = 640


def image_name(seq: int) -> str:
    return f"preview-{seq}.jpg"


def write_preview(job_dir: Path, job_id: str, seq: int, frame_bgr: np.ndarray,
                  record: FrameRecord, video: VideoInfo) -> None:
    job_dir.mkdir(parents=True, exist_ok=True)
    h, w = frame_bgr.shape[:2]
    if w > MAX_WIDTH:
        frame_bgr = cv2.resize(frame_bgr, (MAX_WIDTH, round(h * MAX_WIDTH / w)),
                               interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 80])
    if not ok:
        return
    write_bytes_atomic(job_dir / image_name(seq), buf.tobytes())
    preview = PosePreview(job_id=job_id, seq=seq, frame=record, width=video.width,
                          height=video.height)
    write_json_atomic(job_dir / PREVIEW_JSON, preview.model_dump_json())
    for old in job_dir.glob("preview-*.jpg"):
        try:
            if seq - int(old.stem.split("-", 1)[1]) > 1:
                old.unlink(missing_ok=True)
        except (ValueError, OSError):
            pass


def read_preview(job_dir: Path) -> PosePreview | None:
    path = job_dir / PREVIEW_JSON
    if not path.is_file():
        return None
    try:
        return PosePreview.model_validate_json(path.read_text(encoding="utf-8"))
    except ValueError:
        return None
