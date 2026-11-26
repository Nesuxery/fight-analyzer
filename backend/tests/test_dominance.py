"""Dominance, duration and the last-resort criteria (v2 Bölüm 3.4) on synthetic event lists.

Acceptance: every measure is a value with a confidence; one-sided time needs the measured opponent
to attempt nothing; offensive pace counts significant attempts, grappling attempts and
combinations per measured minute; effective time share stays within 0..1 and grows with active
control, one-sided time and landed strikes; aggressiveness grows with attempts, combinations and
attacks after closing the distance; area control is made of pressure, advance, clinch drive, top
position and exchanges started, with the octagon centre marked as not measured; events of
uncertain attribution and excluded parts count for nobody; a short stretch is not measurable;
older analyses without grappling states still get the measures they can.
"""

from __future__ import annotations

import time

import numpy as np
import pytest

from fight_analyzer.config import FeatureSettings, MotionSettings
from fight_analyzer.contracts import (
    DataOrigin,
    EventType,
    ExcludedSegment,
    ExclusionReason,
    FighterId,
    FightEvent,
    StrikeOutcome,
)
from fight_analyzer.motion import dominance as dm
from fight_analyzer.motion import grappling as gm

F = FeatureSettings()
S = MotionSettings()
FPS = 30.0
HZ = 10.0
RED, BLUE = FighterId.fighter_a, FighterId.fighter_b
ADV, RET, NEUTRAL = 0, 1, 2


def event(actor: FighterId, at_s: float, type_: EventType = EventType.punch, *, significant: bool = True,
          outcome: StrikeOutcome | None = None, uncertain: bool = False, length_s: float = 0.1) -> FightEvent:
    a = int(round(at_s * FPS))
    b = a + max(1, int(round(length_s * FPS)))
    return FightEvent(event_id=f"{type_.value}-{actor.value}-{a}", type=type_, actor=actor,
                      target=BLUE if actor == RED else RED, start_frame=a, end_frame=b, start_ms=a * 1000 / FPS,
                      end_ms=b * 1000 / FPS, peak_frame=a, peak_ms=a * 1000 / FPS, confidence=0.8,
                      significant=significant if type_ in dm.STRIKES else None, outcome=outcome,
                      attribution_uncertain=uncertain, data_origin=DataOrigin.measured)


def bout(seconds: float, *, state: int = gm.DISTANCE):
    frames = int(seconds * FPS)
    samples = int(seconds * HZ)
    signals = {"sample_ms": np.arange(samples) * 1000 / HZ, "valid": np.ones((2, samples), bool),
               "movement": np.full((2, samples), NEUTRAL, np.int8)}
    grappling = {"grappling": np.full(frames, state, np.int8), "clinch_by": np.full(frames, -1, np.int8)}
    return frames, signals, grappling


def measure(events, frames, signals, grappling, segments=(), first=0, last=None):
    last = frames - 1 if last is None else last
    return dm.measure(events, grappling, signals, HZ, first, last, list(segments), FPS, F, S)


def test_one_sided_time_needs_a_measured_opponent_who_attempts_nothing():
    frames, signals, grappling = bout(60)
    red = [event(RED, t) for t in np.arange(10, 31, 2.0)]
    r, b = measure(red, frames, signals, grappling)
    # offense from 0.5 s before the first attempt to 2.5 s after the last one
    assert r.one_sided_s.value == pytest.approx(23.0, abs=0.1) and b.one_sided_s.value == 0
    assert 0 < r.one_sided_s.confidence <= F.detection_confidence
    # blue answers between red's attempts: red no longer imposes anything one-sided
    answers = [event(BLUE, t) for t in np.arange(11, 32, 2.0)]
    r, b = measure(red + answers, frames, signals, grappling)
    assert r.one_sided_s.value <= 1.1 and b.one_sided_s.value <= 2.6
    # blue not measured: nothing can be said about his answers, so no one-sided time either
    signals["valid"][1, :] = False
    r, _ = measure(red, frames, signals, grappling)
    assert r.one_sided_s.value == 0 and r.one_sided_s.confidence == 0


def test_offensive_pace_counts_significant_attempts_grappling_attempts_and_combinations():
    frames, signals, grappling = bout(60)
    combos = [event(RED, t) for t in (5.0, 5.3, 20.0, 20.4, 40.0, 40.5)]  # three pairs
    light = [event(RED, t, significant=False) for t in (30.0, 50.0)]  # in the clinch: not significant
    shot = [event(RED, 45.0, EventType.takedown_attempt)]
    r, b = measure(combos + light + shot, frames, signals, grappling)
    assert r.offensive_pace.value == pytest.approx(6 + F.pace_grappling_weight * 1 + F.pace_combo_weight * 3)
    assert r.components["combinations"] == 3 and r.components["significant_attempts"] == 6
    assert r.offensive_pace.confidence == pytest.approx(F.detection_confidence)
    assert b.offensive_pace.value == 0


def test_effective_time_share_grows_with_active_control_one_sided_time_and_landed_strikes():
    frames, signals, grappling = bout(60, state=gm.RED_TOP)
    quiet = measure([], frames, signals, grappling)[0]
    assert quiet.effective_time_share.value == 0  # holding the position alone imposes nothing
    strikes = [event(RED, t, EventType.ground_strike) for t in (10.0, 12.0, 14.0)]
    working = measure(strikes, frames, signals, grappling)[0]
    landed = [event(RED, t, EventType.ground_strike, outcome=StrikeOutcome.landed) for t in (10.0, 12.0, 14.0)]
    hurting = measure(landed, frames, signals, grappling)[0]
    assert 0 < working.effective_time_share.value <= hurting.effective_time_share.value <= 1
    assert working.components["active_control_s"] == pytest.approx(7.0, abs=0.1)  # 9..16 s
    # excluded time is not fight time: the same work over half the time is a larger share
    half = ExcludedSegment(start_frame=int(30 * FPS), end_frame=frames - 1, reason=ExclusionReason.replay)
    shorter = measure(strikes, frames, signals, grappling, [half])[0]
    assert shorter.effective_time_share.value == pytest.approx(2 * working.effective_time_share.value, abs=0.01)


def test_aggressiveness_grows_with_attempts_combinations_and_closing_the_distance():
    frames, signals, grappling = bout(60)
    few = [event(RED, t) for t in (10.0, 30.0)]
    many = [event(RED, t) for t in np.arange(2, 58, 4.0)] + [event(RED, t + 0.3) for t in np.arange(2, 58, 8.0)]
    low, high = measure(few, frames, signals, grappling)[0], measure(many, frames, signals, grappling)[0]
    assert 0 <= low.aggressiveness.value < high.aggressiveness.value <= 1
    # moving in right before attacking counts as closing the distance to attack
    for t in np.arange(2, 58, 4.0):
        k = int(t * HZ)
        signals["movement"][0, k - 5:k] = ADV
    closing = measure(many, frames, signals, grappling)[0]
    assert closing.components["closing_attacks"] >= 14 and closing.aggressiveness.value > high.aggressiveness.value


def test_area_control_is_made_of_pressure_position_clinch_drive_and_exchanges_and_misses_the_centre():
    frames, signals, grappling = bout(60)
    signals["movement"][0, :] = np.where(np.arange(signals["movement"].shape[1]) % 5 == 0, NEUTRAL, ADV)
    signals["movement"][1, :] = RET
    state = grappling["grappling"]
    state[int(20 * FPS):int(30 * FPS)] = gm.CLINCH
    grappling["clinch_by"][int(20 * FPS):int(30 * FPS)] = 0  # red drives
    state[int(40 * FPS):int(55 * FPS)] = gm.RED_TOP
    events = [event(RED, t) for t in (5.0, 12.0, 35.0)] + [event(BLUE, 5.5)]
    r, b = measure(events, frames, signals, grappling)
    assert r.area_control.value > 0.7 > 0.3 > b.area_control.value
    assert r.components["area_pressure"] == pytest.approx(0.8, abs=0.01) and b.components["area_pressure"] == 0
    assert r.components["area_top_position"] == 1 and r.components["area_clinch_drive"] == 1
    assert r.components["area_exchanges_started"] == 1  # blue only answered inside red's exchange
    assert "center_control" in r.not_measured
    assert 0 < r.area_control.confidence <= F.area_max_confidence


def test_uncertain_attribution_and_excluded_parts_count_for_nobody():
    frames, signals, grappling = bout(60)
    replay = ExcludedSegment(start_frame=int(40 * FPS), end_frame=int(50 * FPS), reason=ExclusionReason.replay)
    events = [event(RED, 10.0, uncertain=True), event(RED, 45.0), event(RED, 20.0)]
    r, _ = measure(events, frames, signals, grappling, [replay])
    assert r.components["significant_attempts"] == 1  # only the attributed one outside the replay
    assert r.components["measured_s"] == pytest.approx(60 - 10.033, abs=0.05)


def test_a_short_stretch_is_not_measurable_and_older_analyses_still_get_what_they_can():
    frames, signals, grappling = bout(60)
    r, _ = measure([event(RED, 1.0)], frames, signals, grappling, last=int(5 * FPS))
    assert r.offensive_pace.value is None and r.offensive_pace.confidence == 0
    assert r.aggressiveness.value is None and r.aggressiveness.confidence == 0
    # analysed before events version 5: no grappling states
    signals["movement"][0, :] = ADV
    r, _ = measure([event(RED, t) for t in (5.0, 6.0)], frames, signals, {})
    assert r.area_control.value is not None and "area_top_position" not in r.components
    assert r.components["active_control_s"] == 0


def test_a_round_is_measured_well_under_a_second():
    frames, signals, grappling = bout(300, state=gm.CLINCH)
    grappling["clinch_by"][:] = 0
    events = [event(RED if k % 2 else BLUE, 1.0 + k * 1.4) for k in range(200)]
    start = time.perf_counter()
    measure(events, frames, signals, grappling)
    assert time.perf_counter() - start < 1.0
