"""History-list preview frame (media/thumbnail.py)."""

from __future__ import annotations

from pathlib import Path

import cv2

from fight_analyzer.media.thumbnail import ensure_thumbnail, thumbnail_frame, thumbnail_path
from tests.support.media import make_video


def test_frame_choice_prefers_the_selection_frame():
    assert thumbnail_frame(300, None) == 30  # 10 % into the video
    assert thumbnail_frame(300, 120) == 120  # where the fighters were chosen
    assert thumbnail_frame(300, 999) == 299  # clamped to the video
    assert thumbnail_frame(1, None) == 0
    assert thumbnail_frame(0, None) == 0


def test_thumbnail_is_written_once_small_and_replaced(tmp_path: Path):
    video = make_video(tmp_path / "v.mp4", seconds=2, size="640x360", rate="25")
    job_dir = tmp_path / "job"
    first = ensure_thumbnail(job_dir, video, "a" * 64, 10)
    assert first == thumbnail_path(job_dir, "a" * 64, 10) and first.is_file()
    image = cv2.imread(str(first))
    assert image.shape[1] == 320 and image.shape[0] == 180  # 16:9 kept, 320 px wide
    mtime = first.stat().st_mtime_ns
    assert ensure_thumbnail(job_dir, video, "a" * 64, 10) == first
    assert first.stat().st_mtime_ns == mtime  # reused, not rewritten
    second = ensure_thumbnail(job_dir, video, "a" * 64, 20)
    assert second is not None and second.is_file() and not first.exists()
    assert [p.name for p in job_dir.glob("thumb-*.jpg")] == [second.name]


def test_unreadable_video_gives_no_thumbnail(tmp_path: Path):
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"not a video")
    assert ensure_thumbnail(tmp_path / "job", bad, "b" * 64, 0) is None
    assert not (tmp_path / "job").exists()  # nothing written
