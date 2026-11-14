"""Replays, stoppages and non-fight parts from broadcast signals (all material synthetic)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from fight_analyzer.broadcast import analyze, clock, ocr, ocr_model, replay
from fight_analyzer.broadcast.clock import ClockRound, Read
from fight_analyzer.broadcast.replay import RUNNING, STOPPED, UNKNOWN, Signals
from fight_analyzer.config import BroadcastSettings, RulesetSettings
from fight_analyzer.contracts import ExclusionReason, ExclusionSignal, VideoInfo
from fight_analyzer.pose.cache import PoseArrays
from tests.support import scorebug

PROJECT_MODELS = Path(__file__).resolve().parents[2] / "data" / "models"
needs_ocr = pytest.mark.skipif(not ocr_model.installed(PROJECT_MODELS),
                               reason="OCR model not installed (python -m fight_analyzer.broadcast.ocr_model)")
S, RS = BroadcastSettings(), RulesetSettings()
FPS = 30.0
HZ = S.sample_hz
MISSING, LABEL, CLOCK, WIPE, SLOW = (ExclusionSignal.scorebug_missing, ExclusionSignal.replay_label,
                                     ExclusionSignal.clock_stopped, ExclusionSignal.wipe, ExclusionSignal.slow_motion)


# ---- the four signals ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,found", [("REPLAY", True), ("instant replay", True), ("UFC REPLAY 2", True),
                                        ("Tekrar", True), ("SLO-MO", True), ("Ağır Çekim", True),
                                        ("REPLAYS", False), ("PLAY", False), ("VOLKANOVSKI", False), ("", False)])
def test_replay_label_words(text, found):
    assert replay.has_replay_label(text, S.replay_words) is found


def running_reads(start_t: float, top: float, seconds: int, number: int = 1) -> list[Read]:
    return [Read(start_t + k, top - k, number, 0.99) for k in range(1, seconds + 1)]


def test_a_frozen_clock_is_a_stall_but_one_repeated_second_is_not():
    reads = running_reads(0, 300, 20)  # 1..20 s: 299..280
    jitter = [*reads, Read(21, 280, 1, 0.99), Read(22, 278, 1, 0.99)]  # the display repeats one second
    assert replay.stalls(jitter, S) == []
    frozen = [*reads, *(Read(20 + k, 280, 1, 0.99) for k in range(1, 9)), Read(29, 279, 1, 0.99)]
    assert replay.stalls(frozen, S) == [(20, 28)]
    # scorebug hidden for 20 s in which the clock lost 18 s: stood still; lost only 5 s: it ran
    assert replay.stalls([*reads, Read(40, 278, 1, 0.99)], S) == [(20, 40)]
    assert replay.stalls([*reads, Read(40, 265, 1, 0.99)], S) == []


def two_rounds() -> list[ClockRound]:
    r1 = ClockRound(index=1, start_t=10, end_t=130, clock_start=120, clock_end=0, partial=False, confidence=0.99,
                    reads=[Read(8, 120, 1, 0.99), Read(9, 120, 1, 0.99), *running_reads(10, 120, 120),
                           Read(131, 0, 1, 0.99), Read(132, 0, 1, 0.99)])
    r2 = ClockRound(index=2, start_t=140, end_t=200, clock_start=120, clock_end=60, partial=True, confidence=0.99,
                    reads=running_reads(140, 120, 60, 2))
    return [r1, r2]


def test_clock_states_running_stopped_and_unknown():
    t = np.arange(0, 220, 0.5)
    state = replay.clock_states(t, two_rounds(), S)
    at = lambda sec: int(state[int(sec * 2)])  # noqa: E731
    assert at(3) == UNKNOWN  # nothing read yet
    assert at(8.5) == STOPPED  # 2:00 shown before the bell
    assert at(10) == RUNNING and at(129.5) == RUNNING
    assert at(131) == STOPPED and at(135) == STOPPED and at(139.5) == STOPPED  # 0:00, then between R1 and R2
    assert at(140) == RUNNING and at(205) == UNKNOWN  # after a round that was cut off nothing is known
    # with a round missing in between, the gap is not known to be a break
    r1, r2 = two_rounds()
    r2.index = 3
    assert int(replay.clock_states(t, [r1, r2], S)[int(135 * 2)]) == UNKNOWN


def test_wipes_are_bursts_of_change_or_very_short_shots():
    step = np.full(3000, 0.004, np.float32)
    step[300] = 0.6  # a hard cut: one frame
    step[900:920] = 0.2  # a logo flying through: many frames in a row
    step[1500], step[1530] = 0.6, 0.6  # two cuts one second apart: the graphic between them
    events = replay.wipe_events(step, [300, 1500, 1530], FPS, S)
    assert events == [(900, 919), (1500, 1530)]
    assert replay.wipe_events(np.full(100, 0.004, np.float32), [], FPS, S) == []


def people(frames: int, wrist_speed: float, moving: tuple[int, int]) -> tuple[PoseArrays, np.ndarray]:
    """One person per frame with a 100 px torso; the right wrist swings at `wrist_speed`
    torso lengths per second during the frames `moving`."""
    kp = np.zeros((frames, 17, 3), np.float32)
    kp[:, :, 2] = 0.9
    for name, xy in ((5, (90, 100)), (6, (110, 100)), (11, (90, 200)), (12, (110, 200)), (9, (60, 150)),
                     (15, (90, 300)), (16, (110, 300))):
        kp[:, name, :2] = xy
    x = 140.0
    for f in range(frames):
        if moving[0] <= f < moving[1]:
            x += wrist_speed * 100 / FPS * (1 if (f // 15) % 2 == 0 else -1)
        kp[f, 10, :2] = (x, 150)
    boxes = np.tile(np.array([50, 80, 180, 320], np.float32), (frames, 1))
    arrays = PoseArrays(frame_index=np.arange(frames), timestamp_ms=np.arange(frames) * 1000 / FPS,
                        det_offsets=np.arange(frames + 1), boxes=boxes, box_conf=np.full(frames, 0.9, np.float32),
                        keypoints=kp)
    return arrays, np.zeros(frames, np.int32)


def test_limb_speed_halves_in_slow_motion():
    arrays, track = people(240, 6.0, (0, 240))
    live = replay.activity(arrays, track, FPS, HZ, 16)
    slow_arrays, _ = people(240, 3.0, (0, 240))
    slow = replay.activity(slow_arrays, track, FPS, HZ, 16)
    assert live[1:].mean() == pytest.approx(6.0, rel=0.05) and slow[1:].mean() == pytest.approx(3.0, rel=0.05)
    untracked = replay.activity(arrays, np.full(240, -1, np.int32), FPS, HZ, 16)
    assert np.isnan(untracked).all()  # no track from frame to frame: not measured, not "slow"


def test_scorebug_strip_template_tells_shown_from_hidden():
    script = scorebug.Script()
    shown = [script.at(t) for t in (20.0, 45.0, 70.0, 95.0, 160.0)]
    area = analyze.roi.ClockArea(clock=analyze.roi.Box(300, int(scorebug.H * 0.86), 60, 30), round=None, confidence=1)
    template = analyze.bug_template(shown, area, lambda crop: ("1:23", 0.99), S)
    assert template is not None
    assert template.match(script.at(33.0)) > 0.8 and template.match(script.at(118.5)) > 0.8  # other digits
    assert template.match(script.at(2.0)) < S.bug_present  # intro: no scorebug
    assert template.match(script.at(script.r1[1] + 4)) < S.bug_present  # break
    # too few frames with a readable clock: no template (and "missing" is then never claimed)
    assert analyze.bug_template(shown, area, lambda crop: ("", 0.0), S) is None


# ---- parts ----------------------------------------------------------------------------------------

def signals(duration: float, rounds: list[ClockRound], *, hidden: list[tuple[float, float]] = (),
            label: list[tuple[float, float]] = (), wipes: list[tuple[float, float]] = (),
            slow: list[tuple[float, float]] = (), bug: bool = True) -> Signals:
    t = np.arange(0, duration, 1 / HZ)
    inside = lambda spans: np.any([(t >= a) & (t < b) for a, b in spans], axis=0) if spans else np.zeros(t.size, bool)  # noqa: E731
    match = np.where(inside(list(hidden)), 0.05, 0.9).astype(np.float32) if bug else np.full(t.size, np.nan, np.float32)
    act = np.where(inside(list(slow)), 2.0, 6.0).astype(np.float32)
    return Signals(t=t, bug=match, label=inside(list(label)), clock=replay.clock_states(t, rounds, S),
                   activity=act, wipes=list(wipes))


def one_round(pause: tuple[float, float] | None = None, length: int = 300) -> ClockRound:
    """Round from 10 s; with `pause` the clock stands still there (visible or not is up to the scorebug)."""
    reads, t, left = [], 10.0, float(length)
    while left > 0:
        t += 1
        if pause is None or not pause[0] < t <= pause[1]:
            left -= 1
        reads.append(Read(t, left, 1, 0.99))
    return ClockRound(index=1, start_t=10, end_t=t, clock_start=length, clock_end=0, partial=False,
                      confidence=0.99, reads=reads)


def detect(sig: Signals, rounds: list[ClockRound], duration: float):
    return replay.detect(sig, rounds, FPS, round(duration * FPS), S)


def spans(parts, reason: ExclusionReason):
    return [(round(p.start_frame / FPS, 1), round((p.end_frame + 1) / FPS, 1)) for p in parts if p.reason == reason]


def test_a_replay_inside_a_round_is_found_with_its_signals():
    r = one_round(pause=(100, 120))
    duration = r.end_t + 5
    # the scorebug leaves with a logo wipe, a slowed copy plays, the wipe brings the fight back
    sig = signals(duration, [r], hidden=[(100, 120), (0, 10), (r.end_t, duration)], wipes=[(99.5, 100.2), (119.6, 120.3)],
                  slow=[(100, 120)])
    parts = detect(sig, [r], duration)
    (rep,) = [p for p in parts if p.reason == ExclusionReason.replay]
    assert rep.source == "auto" and rep.auto_id == f"replay-{rep.start_frame}-{rep.end_frame}"
    assert rep.signals == [MISSING, CLOCK, WIPE, SLOW] and rep.confidence == 0.9
    # where the clock is known to run, it decides the edges (the wipes overlap live seconds)
    assert spans(parts, ExclusionReason.replay) == [(100.0, 120.0)]
    assert spans(parts, ExclusionReason.stoppage) == []  # the stall is the replay, not a second part


def test_two_signals_are_enough_and_one_is_not():
    r = one_round(pause=(100, 120))
    duration = r.end_t + 5
    edges = [(0, 10), (r.end_t, duration)]
    two = detect(signals(duration, [r], hidden=[(100, 120), *edges]), [r], duration)
    assert spans(two, ExclusionReason.replay) == [(100.0, 120.0)]
    (rep,) = [p for p in two if p.reason == ExclusionReason.replay]
    assert rep.signals == [MISSING, CLOCK] and rep.confidence == 0.6
    # a slow, calm stretch of the fight alone is nothing
    assert spans(detect(signals(duration, [one_round()], hidden=edges, slow=[(100, 120)]), [one_round()], duration),
                 ExclusionReason.replay) == []


def test_time_in_which_the_clock_runs_is_never_a_replay():
    r = one_round()
    duration = r.end_t + 5
    # a sponsor graphic covers the scorebug for 20 s while the fight (and its clock) goes on,
    # between two wipes and with slow feet: still live
    sig = signals(duration, [r], hidden=[(100, 120), (0, 10), (r.end_t, duration)], wipes=[(99.5, 100.2), (119.6, 120.3)],
                  slow=[(100, 120)])
    parts = detect(sig, [r], duration)
    assert spans(parts, ExclusionReason.replay) == [] and spans(parts, ExclusionReason.stoppage) == []


def test_a_frozen_clock_on_screen_is_a_stoppage():
    r = one_round(pause=(100, 130))
    duration = r.end_t + 5
    parts = detect(signals(duration, [r], hidden=[(0, 10), (r.end_t, duration)]), [r], duration)
    assert spans(parts, ExclusionReason.stoppage) == [(100.0, 130.0)]
    (stop,) = [p for p in parts if p.reason == ExclusionReason.stoppage]
    assert stop.signals == [CLOCK] and stop.confidence == S.stoppage_confidence
    assert spans(parts, ExclusionReason.replay) == []
    # two seconds are below the limit
    short = one_round(pause=(100, 102))
    assert spans(detect(signals(duration, [short], hidden=[(0, 10)]), [short], duration), ExclusionReason.stoppage) == []


def test_a_replay_label_with_a_stopped_clock():
    r = one_round(pause=(100, 115))
    duration = r.end_t + 5
    parts = detect(signals(duration, [r], label=[(101, 114)], hidden=[(0, 10)]), [r], duration)
    (rep,) = [p for p in parts if p.reason == ExclusionReason.replay]
    assert rep.signals == [LABEL, CLOCK] and rep.confidence == pytest.approx(0.65)
    assert spans(parts, ExclusionReason.replay) == [(101.0, 114.0)]
    # the second of the stall on each side of the labelled part is not a stoppage of its own
    assert spans(parts, ExclusionReason.stoppage) == []
    # a label read once (a word on a sponsor board) is not a signal
    once = detect(signals(duration, [r], label=[(105, 105.5)], hidden=[(0, 10)]), [r], duration)
    assert spans(once, ExclusionReason.replay) == [] and spans(once, ExclusionReason.stoppage) == [(100.0, 115.0)]


def test_before_the_first_and_after_the_last_round():
    rounds = two_rounds()
    duration = 215.0
    parts = detect(signals(duration, rounds, hidden=[(0, 12), (130, 142), (200, duration)]), rounds, duration)
    assert spans(parts, ExclusionReason.intro) == [(0.0, 10.0)]
    assert spans(parts, ExclusionReason.post_fight) == [(200.0, 215.0)]  # R2 stopped early: the bout is over
    # between the rounds: scorebug away and the clock not running; the round's first seconds
    # without a scorebug (the clock already runs) are not part of it
    assert spans(parts, ExclusionReason.replay) == [(130.0, 140.0)]
    intro = next(p for p in parts if p.reason == ExclusionReason.intro)
    assert intro.signals == [MISSING] and intro.confidence == S.edge_confidence
    # after a round that ran out comes a break, not necessarily the end of the bout
    full = one_round(length=120)
    assert spans(detect(signals(140, [full], hidden=[(0, 10), (130, 140)]), [full], 140), ExclusionReason.break_) == \
        [(130.0, 140.0)]
    # the scorebug stays on screen after the last round: nothing is claimed
    shown = detect(signals(duration, rounds, hidden=[(0, 12), (130, 142)]), rounds, duration)
    assert spans(shown, ExclusionReason.post_fight) == []


def test_without_a_scorebug_two_wipes_and_slow_motion_make_a_replay():
    duration = 120.0
    sig = signals(duration, [], wipes=[(40.0, 40.7), (58.0, 58.7)], slow=[(40, 59)], bug=False)
    parts = detect(sig, [], duration)
    assert spans(parts, ExclusionReason.replay) == [(40.0, 58.7)]
    assert parts[0].signals == [WIPE, SLOW] and parts[0].confidence == 0.6
    # wipes alone (a graphic between two live shots) are not enough; neither is an unknown scorebug
    assert detect(signals(duration, [], wipes=[(40.0, 40.7), (58.0, 58.7)], bug=False), [], duration) == []
    assert detect(signals(duration, [], slow=[(40, 59)], bug=False), [], duration) == []


# ---- the whole broadcast analysis -------------------------------------------------------------------

@needs_ocr
def test_end_to_end_replay_on_a_synthetic_broadcast(tmp_path: Path):
    """A labelled replay without scorebug in round 1, while the clock stands still."""
    script = scorebug.Script(replay=(60.0, 14.0))
    path = scorebug.write_video(tmp_path / "bout.mp4", script)
    n = int(round(script.duration * script.fps))
    video = VideoInfo(width=scorebug.W, height=scorebug.H, fps=script.fps, frame_count=n,
                      duration_ms=n * 1000 / script.fps)
    reader = ocr.load(PROJECT_MODELS)
    data = analyze.analyze(path, video, lambda: pytest.fail("poses are not needed"), reader.read, S, RS)
    assert [r.index for r in data.rounds] == [1, 2]
    r1 = data.rounds[0]
    assert r1.video_end_s == pytest.approx(script.r1[1], abs=1.0) and not r1.partial  # 14 s longer than its clock
    (rep,) = [p for p in data.segments if p.reason == ExclusionReason.replay and p.start_frame > r1.start_frame
              and p.end_frame < r1.end_frame]
    assert rep.start_frame / script.fps == pytest.approx(60.0, abs=1.0)
    assert (rep.end_frame + 1) / script.fps == pytest.approx(74.0, abs=1.0)
    assert set(rep.signals) == {MISSING, LABEL, CLOCK}
    reasons = {p.reason for p in data.segments}
    assert ExclusionReason.intro in reasons and ExclusionReason.post_fight in reasons
    assert data.scorebug_frame is not None and r1.start_frame < data.scorebug_frame < r1.end_frame
    found, _ = clock.infer(data.reads, script.duration, S, RS)
    assert len(found) == 2
