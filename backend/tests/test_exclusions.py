"""Excluded parts (replays etc.): not fight time, no counting, no points, frozen momentum."""

from __future__ import annotations

import numpy as np

from fight_analyzer.config import MomentumSettings
from fight_analyzer.contracts import ExcludedSegment, FightEvent
from fight_analyzer.motion import exclusions as excl
from fight_analyzer.motion import momentum
from fight_analyzer.motion.events import MovementRun

FPS = 30.0


def seg(a: int, b: int, reason: str = "replay") -> ExcludedSegment:
    return ExcludedSegment(start_frame=a, end_frame=b, reason=reason)


def punch(frame: int, actor: str = "fighter_a") -> FightEvent:
    ms = frame * 1000 / FPS
    return FightEvent(event_id=f"p{frame}", type="punch", actor=actor, start_frame=frame, end_frame=frame,
                      start_ms=ms, end_ms=ms, peak_frame=frame, peak_ms=ms, confidence=0.8, data_origin="measured")


def test_parts_are_clipped_sorted_and_merged():
    parts = excl.normalize([seg(500, 900), seg(10, 20), seg(21, 30, "slow_motion"), seg(1200, 1300)], 1000)
    assert [(p.start_frame, p.end_frame) for p in parts] == [(10, 30), (500, 900)]  # past the end: dropped
    assert parts[0].reason == "replay"  # touching parts merge, the first reason wins


def test_fight_time_skips_excluded_time():
    iv = excl.intervals([seg(30, 59)], FPS)  # 1000..2000 ms
    assert iv == [(1000.0, 2000.0)]
    assert excl.fight_ms(500, iv) == 500 and excl.fight_ms(1500, iv) == 1000 and excl.fight_ms(3000, iv) == 2000
    assert excl.outside_ms(500, 3000, iv) == 1500 and excl.outside_ms(1200, 1800, iv) == 0
    assert excl.outside_parts(500, 3000, iv) == [(500, 1000.0), (2000.0, 3000)]
    t = np.array([0, 999, 1000, 1500, 2000, 2500])
    assert excl.fight_ms_array(t, iv).tolist() == [excl.fight_ms(float(x), iv) for x in t]


def test_excluded_events_earn_nothing_and_time_based_points_are_split():
    s = MomentumSettings()
    parts = [seg(60, 119)]  # 2000..4000 ms is a replay
    events = [punch(30), punch(90), punch(150, "fighter_b")]
    runs = [MovementRun(fighter=0, start_frame=0, end_frame=179, start_ms=1000, end_ms=5000, seconds=4.0,
                        advancing=True)]
    full = momentum.ledger(events, runs, s)
    cut = momentum.ledger(events, runs, s, parts, FPS)
    assert {c.event_id for c in full if c.event_id} == {"p30", "p90", "p150"}
    assert {c.event_id for c in cut if c.event_id} == {"p30", "p150"}  # the replayed punch is not scored
    adv = [c for c in cut if c.source == "advance"]
    assert [(c.start_ms, c.end_ms) for c in adv] == [(1000, 2000), (4000, 5000)]
    assert sum(c.points for c in adv) == round(s.advance_per_s * 2.0, 4)  # 2 of the 4 s are fight time


def test_momentum_holds_through_an_excluded_part():
    s = MomentumSettings()
    parts = [seg(60, 119)]
    iv = excl.intervals(parts, FPS)
    contribs = momentum.ledger([punch(30)], [], s, parts, FPS)
    m = momentum.totals(contribs, np.array([2000.0, 2500.0, 3999.0, 6000.0]), s.half_life_s, iv)[0]
    assert m[0] == m[1] == m[2]  # frozen during the replay
    plain = momentum.totals(contribs, np.array([4000.0]), s.half_life_s)[0]
    assert m[3] < m[0] and abs(m[3] - plain[0]) < 1e-12  # decays again afterwards: 6 s video = 4 s fight time
