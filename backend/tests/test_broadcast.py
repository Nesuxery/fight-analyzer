"""Scorebug clock reading and round boundaries (all footage synthetic)."""

from __future__ import annotations

import math
import socket
import urllib.request
from pathlib import Path

import pytest

from fight_analyzer.broadcast import analyze, clock, ocr, ocr_model, roi
from fight_analyzer.broadcast.clock import Read
from fight_analyzer.broadcast.text import clean_name, parse_clock, parse_round, title_case
from fight_analyzer.config import BroadcastSettings, RulesetSettings
from fight_analyzer.contracts import BroadcastNoteCode, RoundSource, VideoInfo
from tests.support import scorebug

PROJECT_MODELS = Path(__file__).resolve().parents[2] / "data" / "models"
needs_ocr = pytest.mark.skipif(not ocr_model.installed(PROJECT_MODELS),
                               reason="OCR model not installed (python -m fight_analyzer.broadcast.ocr_model)")
S, RS = BroadcastSettings(), RulesetSettings()


# ---- text -------------------------------------------------------------------------

@pytest.mark.parametrize("text,value", [("4:56", 296), ("0:04", 4), ("UFC 4:26", 266), ("O:O4", 4), ("10:00", 600),
                                        ("4:76", None), ("12:34", None), ("456", None), ("VOLKANOVSKI", None)])
def test_clock_text(text, value):
    assert parse_clock(text) == value


def test_bare_clock_only_inside_the_clock_area():
    assert parse_clock("456") is None and parse_clock("456", bare=True) == 296
    assert parse_clock("9.5", bare=True) == 9.5


@pytest.mark.parametrize("text,value", [("R1", 1), ("RI", 1), ("|R2", 2), ("IR2", 2), ("R1III", 1), ("4:48 |R2|||", 2),
                                        ("ROUND 3", 3), ("2ND", 2), ("R12", None), ("R7", None), ("RR", None)])
def test_round_text(text, value):
    assert parse_round(text) == value


def test_names_and_locale_independent_title_case():
    assert [clean_name(t) for t in ("3 TOPURIA", "BLACK", "-115", "UFC", "DE LA ROSA")] == \
        ["TOPURIA", None, None, None, "DE LA ROSA"]
    assert title_case("ILIA") == "Ilia"  # never the Turkish dotless "Ilıa"
    assert title_case("ST-PIERRE") == "St-Pierre" and title_case("O'MALLEY") == "O'Malley"


# ---- clock runs and rounds ------------------------------------------------------------

def reads_for(script: scorebug.Script, hz: float = 1.0) -> list[Read]:
    """What a perfect reader sees once per second."""
    out = []
    t = 0.0
    while t < script.duration:
        (a1, b1), (a2, b2) = script.r1, script.r2
        if a1 <= t < b1:
            out.append(Read(t, float(_secs(script.length - (t - a1))), 1, 0.99))
        elif a2 <= t < b2:
            out.append(Read(t, float(_secs(script.length - (t - a2))), 2, 0.99))
        elif b2 <= t < b2 + script.frozen:
            out.append(Read(t, float(_secs(script.r2_stop_left)), 2, 0.99))
        t = round(t + 1 / hz, 6)
    return out


def _secs(left: float) -> int:
    return max(0, math.ceil(left - 1e-9))


def test_two_rounds_with_a_finish_in_the_second():
    script = scorebug.Script()
    rounds, notes = clock.infer(reads_for(script), script.duration, S, RS)
    assert notes == [] and [r.index for r in rounds] == [1, 2]
    r1, r2 = rounds
    assert r1.start_t == pytest.approx(script.r1[0], abs=1.0) and r1.end_t == pytest.approx(script.r1[1], abs=1.0)
    assert (r1.clock_start, r1.clock_end, r1.partial) == (120, 0, False)
    assert r2.start_t == pytest.approx(script.r2[0], abs=1.0) and r2.end_t == pytest.approx(script.r2[1], abs=1.0)
    assert (r2.clock_end, r2.partial) == (70, True)  # stopped with 1:10 left: a finish
    assert r1.confidence > 0.9 and r2.confidence > 0.9


def test_misreads_do_not_split_or_move_a_round():
    script = scorebug.Script()
    reads = reads_for(script)
    bad = {20: 4.0, 21: 299.0, 60: 118.0}  # wild jumps an OCR can produce
    noisy = [Read(r.t, bad.get(i, r.clock), r.round if i != 40 else 2, r.conf) for i, r in enumerate(reads)]
    rounds, _ = clock.infer(noisy, script.duration, S, RS)
    assert [r.index for r in rounds] == [1, 2]
    assert rounds[0].start_t == pytest.approx(script.r1[0], abs=1.0)
    assert rounds[0].end_t == pytest.approx(script.r1[1], abs=1.0)


def test_frozen_clock_before_the_bell_and_a_pause_inside_the_round():
    reads = [Read(float(t), 120.0, 1, 0.99) for t in range(0, 8)]  # 2:00 shown before the start
    left, t = 120.0, 8.0
    while left > 0:
        if 40 <= t < 60:  # timeout: clock stopped for 20 s
            reads.append(Read(t, float(_secs(left)), 1, 0.99))
        else:
            left -= 1
            reads.append(Read(t, float(_secs(left)), 1, 0.99))
        t += 1
    rounds, _ = clock.infer(reads, t + 5, S, RS)
    assert len(rounds) == 1
    assert rounds[0].start_t == pytest.approx(7.5, abs=1.0)  # the clock left 2:00 at about 7-8 s
    assert rounds[0].end_t == pytest.approx(t, abs=1.5) and not rounds[0].partial


def test_recording_that_starts_inside_a_round_is_partial():
    reads = [Read(float(t), 200.0 - t, 2, 0.99) for t in range(0, 120)]
    rounds, _ = clock.infer(reads, 125, S, RS)
    assert len(rounds) == 1 and rounds[0].partial and rounds[0].start_t == 0.0 and rounds[0].clock_start == 200
    # a misread first read (no neighbour before it) must not turn it into a full round
    rounds, _ = clock.infer([Read(0.0, 299.0, 2, 0.99), *reads[1:]], 125, S, RS)
    assert len(rounds) == 1 and rounds[0].partial and rounds[0].clock_start == 199


def test_unreadable_round_numbers_are_inferred_and_noted():
    script = scorebug.Script()
    reads = [Read(r.t, r.clock, None, r.conf) for r in reads_for(script)]
    rounds, notes = clock.infer(reads, script.duration, S, RS)
    assert [r.index for r in rounds] == [1, 2]
    assert {n.code for n in notes} == {BroadcastNoteCode.round_number_inferred}
    assert all(r.confidence <= 0.6 for r in rounds)


def test_short_runs_are_not_rounds():
    reads = [Read(float(t), 300.0 - t, 1, 0.99) for t in range(0, 10)]
    assert clock.infer(reads, 10, S, RS)[0] == []


def test_fight_clock_timeline_follows_the_reads():
    script = scorebug.Script()
    rounds, _ = clock.infer(reads_for(script), script.duration, S, RS)
    ts, rnd, rem, conf = clock.timeline(rounds, script.duration, 1.0, S.max_interpolate_s)
    assert rnd[0] is None and rem[0] is None  # intro: no clock
    i = ts.index(30.0)
    assert rnd[i] == 1 and rem[i] == pytest.approx(script.length - (30 - script.r1[0]), abs=1.0)
    assert all(c == 0 for c, r in zip(conf, rnd) if r is None)


# ---- clock area on screen -------------------------------------------------------------

def test_persistent_text_boxes_skip_the_moving_arena_clock():
    script = scorebug.Script()
    times = [10.0 + 2.5 * i for i in range(40)]
    per_frame = [roi.text_boxes(script.at(t), S) for t in times]
    tracks = roi.persistent(per_frame, S.min_presence)
    y_bug = int(scorebug.H * 0.86)
    assert any(abs(tr.box.y - y_bug) < 20 and 290 <= tr.box.x <= 330 for tr in tracks)  # the clock
    assert all(tr.box.y > 120 for tr in tracks)  # nothing from the moving top-band clock


@needs_ocr
def test_end_to_end_on_a_synthetic_broadcast(tmp_path: Path):
    script = scorebug.Script()
    path = scorebug.write_video(tmp_path / "bout.mp4", script)
    n = int(round(script.duration * script.fps))
    video = VideoInfo(width=scorebug.W, height=scorebug.H, fps=script.fps, frame_count=n,
                      duration_ms=n * 1000 / script.fps)
    reader = ocr.load(PROJECT_MODELS)
    data = analyze.analyze(path, video, lambda: pytest.fail("poses are not needed with a clock"), reader.read, S, RS)
    assert data.roi is not None and data.roi.source == "auto"
    assert [r.index for r in data.rounds] == [1, 2] and all(r.source == RoundSource.ocr for r in data.rounds)
    r1, r2 = data.rounds
    assert r1.video_start_s == pytest.approx(script.r1[0], abs=1.0)
    assert r1.video_end_s == pytest.approx(script.r1[1], abs=1.0) and not r1.partial
    assert r2.video_start_s == pytest.approx(script.r2[0], abs=1.0)
    assert r2.video_end_s == pytest.approx(script.r2[1], abs=1.0) and r2.partial and r2.clock_end == 70
    assert data.names is not None and (data.names.red, data.names.blue) == ("Volkanovski", "Topuria")


def test_without_the_model_nothing_is_read_or_downloaded(tmp_path: Path, monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError("network access during analysis")

    monkeypatch.setattr(urllib.request, "urlopen", no_network)
    monkeypatch.setattr(socket.socket, "connect", no_network)
    assert ocr.load(tmp_path / "models") is None
    script = scorebug.Script()
    path = scorebug.write_video(tmp_path / "bout.mp4", script)
    n = int(round(script.duration * script.fps))
    video = VideoInfo(width=scorebug.W, height=scorebug.H, fps=script.fps, frame_count=n,
                      duration_ms=n * 1000 / script.fps)

    class NoPeople:  # stand-in for the pose arrays: nobody detected, so no breaks
        frame_count = n
        det_offsets = [0] * (n + 1)

    data = analyze.analyze(path, video, lambda: NoPeople(), None, S, RS)
    assert data.rounds == [] and data.roi is None and data.names is None
    assert [x.code for x in data.notes] == [BroadcastNoteCode.ocr_unavailable]


@needs_ocr
def test_ocr_makes_no_network_connection(monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError("network access during OCR")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket, "getaddrinfo", no_network)
    reader = ocr.load(PROJECT_MODELS)
    bug = scorebug.frame(0, scorebug.Bug(296, 1))
    area = roi.Box(300, int(scorebug.H * 0.86) - 4, 60, 38)
    text, conf = reader.read(area.crop(bug))
    assert parse_clock(text) == 296 and conf > 0.6
