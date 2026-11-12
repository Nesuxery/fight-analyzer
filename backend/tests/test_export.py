"""Export: per-frame values equal the browser's, effect timing, files and video writing."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from fight_analyzer.config import TranscodeSettings
from fight_analyzer.contracts import (
    BoundingBox,
    ExportOptions,
    FightEvent,
    FighterFrameState,
    FrameRecord,
    Keypoint,
    PersonDetection,
    VideoInfo,
)
from fight_analyzer.export import files, frames, render, video
from fight_analyzer.export.style import load_style
from fight_analyzer.media.probe import probe_video
from tests.support import frame_fixture
from tests.support.media import make_video


def test_golden_file_matches_the_export_computation():
    # frontend/tests/frame-metrics.test.ts checks the browser against the same file
    stored = json.loads(frame_fixture.FIXTURE.read_text(encoding="utf-8"))
    assert frame_fixture.build() == stored, "regenerate with python -m tests.support.frame_fixture"


def test_values_follow_the_frame_and_round_like_javascript():
    assert frames.js_round(2.5) == 3 and frames.js_round(3.5) == 4 and frames.js_round(-0.5) == 0
    assert frames.js_round(np.array([0.49999, 49.5, 50.5])).tolist() == [0, 50, 51]
    events, motion, momentum = frame_fixture.build_inputs()
    m = frames.compute(frame_fixture.FRAME_COUNT, frame_fixture.FPS, events, motion, momentum)
    assert (m.red_shown >= 0).all() and (m.red_shown <= 100).all()
    # counters never decrease and an event counts from its peak frame on
    for side in frames.SIDES:
        assert (np.diff(m.stats[side]["strike_attempts"]) >= 0).all()
    e = next(x for x in events if x.type == "punch" and x.actor == "fighter_a")
    before = m.stats["red"]["strike_attempts"][e.peak_frame - 1]
    assert m.stats["red"]["strike_attempts"][e.peak_frame] >= before + 1


def _event(kind: str, peak_s: float, **extra) -> FightEvent:
    f = round(peak_s * 30)
    return FightEvent(event_id=f"{kind}-{f}", type=kind, actor="fighter_a", target="fighter_b", start_frame=f,
                      end_frame=f, start_ms=f * 1000 / 30, end_ms=f * 1000 / 30, peak_frame=f, peak_ms=f * 1000 / 30,
                      confidence=0.8, data_origin="measured", **extra)


def test_effects_are_a_function_of_video_time_only():
    style = load_style()
    punch = _event("punch", 1.0, possible_contact=True, location={"x": 10, "y": 20}, limb="left_hand")
    kd = _event("knockdown", 5.0)
    events = [punch, kd]
    at = lambda t: frames.effects_at(events, t, style)  # noqa: E731
    assert not at(1.0 - style.strike_before_s - 0.01).flashes
    assert at(1.0 - style.strike_before_s + 0.001).flashes[0].strength == 1.0  # just before the peak
    assert not at(1.0 - 0.001).rings  # contact is only shown from the peak on
    ring = at(1.1).rings[0]
    assert ring.labelled and 0 < ring.strength < 1
    assert not at(1.0 + style.contact_after_s + 0.01).rings
    assert not at(1.0 + style.strike_after_s + 0.01).flashes
    assert not at(4.99).warnings and at(5.0).warnings[0].strength == 1.0
    assert at(5.0 + style.major_after_s - style.major_fade_s / 2).warnings[0].strength == pytest.approx(0.5)
    assert not at(5.0 + style.major_after_s + 0.01).warnings
    # pausing / rewinding: the same time always gives the same effects
    first = at(1.1)
    for t in (9.0, 0.0, 5.5, 1.05):
        at(t)
    assert at(1.1) == first


def test_csv_has_one_row_per_frame(tmp_path: Path):
    events, motion, momentum = frame_fixture.build_inputs()
    n = frame_fixture.FRAME_COUNT
    m = frames.compute(n, frame_fixture.FPS, events, motion, momentum)
    state = np.zeros((n, 2), dtype=np.int8)
    state[10:20, 1] = 2
    path = tmp_path / "m.csv"
    files.write_csv(path, m, motion, events, state)
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == n and list(rows[0]) == list(files.CSV_COLUMNS)
    assert all(int(r["red_share"]) + int(r["blue_share"]) == 100 for r in rows)
    assert rows[15]["blue_identity"] == "uncertain" and rows[5]["blue_identity"] == "tracked"
    last = rows[-1]
    assert int(last["red_strike_attempts"]) == int(m.stats["red"]["strike_attempts"][-1])
    peaks = {e.peak_frame for e in events if e.peak_frame is not None}
    assert all(rows[f]["events"] for f in peaks)


def _person(x0: float, conf: float = 0.9) -> PersonDetection:
    kps = [Keypoint(x=x0 + (i % 3) * 8, y=40 + i * 9, confidence=conf) for i in range(17)]
    return PersonDetection(detection_id=0, bbox=BoundingBox(x1=x0 - 10, y1=30, x2=x0 + 40, y2=200), confidence=0.9,
                           keypoints=kps)


def test_renderer_draws_overlay_and_always_shows_identity_problems():
    events, motion, momentum = frame_fixture.build_inputs()
    m = frames.compute(10, frame_fixture.FPS, events, motion, momentum)
    red, blue = _person(80), _person(200)
    red.fighter_id, blue.detection_id = "fighter_a", 1
    record = FrameRecord(frame_index=0, timestamp_ms=0, detections=[red, blue], fighters=[
        FighterFrameState(fighter_id="fighter_a", state="tracked", detection_id=0, confidence=0.9),
        FighterFrameState(fighter_id="fighter_b", state="uncertain", detection_id=None, confidence=0.0)])
    names = {"red": "Kırmızı Şöğüç", "blue": "Mavi"}
    style = load_style()
    blank = np.full((360, 640, 3), 90, np.uint8)
    full = blank.copy()
    render.Renderer(640, 360, names, ExportOptions(others=True, distance=True), style).draw(
        full, 0, record, m, frames.Effects([], [], []), 2.0)
    bare = blank.copy()
    render.Renderer(640, 360, names, ExportOptions(skeleton=False, effects=False, momentum=False, counters=False),
                    style).draw(bare, 0, record, m, frames.Effects([], [], []), None)
    assert (full[:40] != blank[:40]).any()  # momentum band
    assert (full[40:220, 60:140] != blank[40:220, 60:140]).any()  # red skeleton
    assert (bare[:40] == blank[:40]).all() and (bare[40:220, 60:140] == blank[40:220, 60:140]).all()
    assert (bare[300:345, :200] != blank[300:345, :200]).any()  # "Mavi: Takip belirsiz" badge stays


def _fighter(cx: float, head_y: float, role: str, label: str) -> render._Person:
    """A standing figure whose face points sit around (cx, head_y)."""
    kp = np.zeros((17, 3))
    kp[0] = (cx, head_y, 0.9)
    kp[1], kp[2] = (cx - 4, head_y - 3, 0.9), (cx + 4, head_y - 3, 0.9)
    kp[3], kp[4] = (cx - 8, head_y, 0.9), (cx + 8, head_y, 0.9)
    for i in range(5, 17):
        kp[i] = (cx + (-10 if i % 2 else 10), head_y + 20 + (i - 5) * 12, 0.9)
    return render._Person(kp, role, "tracked", label)


def test_name_labels_never_overlap_and_stay_in_the_picture_below_the_band():
    names = {"red": "Alexander Volkanovski", "blue": "İlia Topuria"}
    r = render.Renderer(640, 360, names, ExportOptions(momentum=True, counters=True), load_style())
    frame = np.full((360, 640, 3), 90, np.uint8)
    band = r._band_height()
    assert band > 0
    # heads 20 px apart, just under the top band (a clinch near the top of the picture)
    labels = [r._person(frame, _fighter(300, 70, "red", names["red"])),
              r._person(frame, _fighter(320, 74, "blue", names["blue"]))]
    assert all(labels)
    boxes = [(x, y, n.patch.alpha.shape[1], n.patch.alpha.shape[0])
             for n, (x, y) in zip(labels, r.place_name_labels(labels))]
    for x, y, w, h in boxes:
        assert 0 <= x and x + w <= 640 and band <= y and y + h <= 360
    (ax, ay, aw, ah), (bx, by, bw, bh) = boxes
    assert ax + aw <= bx or bx + bw <= ax or ay + ah <= by or by + bh <= ay
    # a fighter at the right edge keeps the whole name in the picture
    edge = [r._person(frame, _fighter(634, 200, "blue", names["red"]))]
    ((x, y),) = r.place_name_labels(edge)
    assert x + edge[0].patch.alpha.shape[1] <= 640


def _info(path: Path) -> VideoInfo:
    p = probe_video(path)
    cap = cv2.VideoCapture(str(path))
    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    return VideoInfo(width=p.width, height=p.height, fps=25.0, fps_num=25, fps_den=1, frame_count=count,
                     duration_ms=count * 40.0, has_audio=p.has_audio)


def test_video_keeps_every_frame_and_the_audio(tmp_path: Path):
    src = make_video(tmp_path / "a.mp4", seconds=1.2, audio=True)
    info = _info(src)
    seen: list[int] = []

    def draw(i: int, img: np.ndarray) -> None:
        seen.append(i)
        img[:10, :10] = 255

    out = tmp_path / "out.partial"
    written = video.render(src, out, info, TranscodeSettings(preset="ultrafast"), draw, lambda done: None)
    assert written == info.frame_count == len(seen) == 30
    probe = probe_video(out)
    assert probe.has_audio and (probe.width, probe.height) == (info.width, info.height)
    cap = cv2.VideoCapture(str(out))
    assert int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) == 30
    ok, frame = cap.read()
    assert ok and frame[:10, :10].mean() > 200  # the drawing is in the file


def test_cancelled_video_leaves_no_file(tmp_path: Path):
    src = make_video(tmp_path / "a.mp4", seconds=1)
    info = _info(src)
    out = tmp_path / "out.partial"

    class Stop(Exception):
        pass

    def stop_at_ten(done: int) -> None:
        if done == 10:
            raise Stop()

    with pytest.raises(Stop):
        video.render(src, out, info, TranscodeSettings(preset="ultrafast"), lambda i, img: None, stop_at_ten)
    assert not out.exists()
