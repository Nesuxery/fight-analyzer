"""Small preview frame of an analysis for the history list.

jobs/<id>/thumb-<video key>-<frame>.jpg, made from the analysis copy on the
first request and reused afterwards; a new selection (another frame) or a new
analysis copy writes a new file and removes the old one.
"""

from __future__ import annotations

from pathlib import Path

import cv2

from fight_analyzer.fsutil import write_bytes_atomic

WIDTH = 320
QUALITY = 82
PATTERN = "thumb-*.jpg"


def thumbnail_frame(frame_count: int, anchor_frame: int | None) -> int:
    """The frame the user chose the fighters on, if any (both are in the picture);
    otherwise 10 % into the video, past intros and black frames."""
    last = max(0, frame_count - 1)
    if anchor_frame is not None:
        return min(max(anchor_frame, 0), last)
    return min(last, int(frame_count * 0.1))


def thumbnail_path(job_dir: Path, video_key: str, frame: int) -> Path:
    return job_dir / f"thumb-{video_key[:16]}-{frame}.jpg"


def ensure_thumbnail(job_dir: Path, video: Path, video_key: str, frame: int) -> Path | None:
    """Path of the JPEG (written when missing); None when the frame cannot be decoded."""
    path = thumbnail_path(job_dir, video_key, frame)
    if path.is_file():
        return path
    cap = cv2.VideoCapture(str(video))
    try:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame)
        ok, image = cap.read()
    finally:
        cap.release()
    if not ok or image is None:
        return None
    h, w = image.shape[:2]
    if w > WIDTH:
        image = cv2.resize(image, (WIDTH, max(1, round(h * WIDTH / w))), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, QUALITY])
    if not ok:
        return None
    job_dir.mkdir(parents=True, exist_ok=True)
    write_bytes_atomic(path, buf.tobytes())
    for old in job_dir.glob(PATTERN):
        if old != path:
            old.unlink(missing_ok=True)
    return path
