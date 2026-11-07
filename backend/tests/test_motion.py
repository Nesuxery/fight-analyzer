"""Motion signals, events and momentum on synthetic skeletons with known actions.

Acceptance: a still picture produces no attempts, one motion is counted once
(at any frame rate), a kick is not also a punch, camera motion is not fighter
motion, nothing is produced while identity is not verified, and every
momentum point can be traced to its source.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from fight_analyzer.config import MomentumSettings, MotionSettings
from fight_analyzer.contracts import EventType, FighterId, MomentumSource
from fight_analyzer.motion import events as ev
from fight_analyzer.motion import kinematics as km
from fight_analyzer.motion import momentum as mm
from tests.support.motion_scenes import Fighter, MotionScene, fall, head_snap, kick, punch, walk

S = MotionSettings()
M = MomentumSettings()


def analyze(scene: MotionScene, *, compensate: bool = True):
    arrays, state, det, track, camera = scene.render()
    if not compensate:
        camera.to_ref[:, 0, 2] = 0.0
    kin = tuple(km.compute(arrays, state, det, track, camera, f, S) for f in (0, 1))
    return ev.analyze(arrays, camera, kin, S)


def of(result, type_: EventType, actor: int | None = None):
    return [e for e in result.events if e.type == type_
            and (actor is None or e.actor == (FighterId.fighter_a, FighterId.fighter_b)[actor])]


def pair(a_actions=(), b_actions=(), distance=2.0, **kw):
    return (Fighter(x=0.0, facing=1, actions=list(a_actions), **kw), Fighter(x=distance, facing=-1, actions=list(b_actions)))


@pytest.mark.parametrize("jitter", [1.0, 3.0])
def test_still_picture_produces_nothing(jitter):
    r = analyze(MotionScene(pair(), 5.0, jitter_px=jitter))
    assert r.events == [] and r.runs == []
    ledger = mm.ledger(r.events, r.runs, M)
    assert ledger == []
    m = mm.totals(ledger, np.arange(0, 5000, 100.0), M.half_life_s)
    assert np.allclose(mm.red_share(m[0], m[1], M.prior), 50.0)


@pytest.mark.parametrize("fps", [25, 30, 50, 60])
def test_one_punch_is_one_attempt_at_any_frame_rate(fps):
    r = analyze(MotionScene(pair([punch(1.0, "l")]), 2.0, fps=fps))
    punches = of(r, EventType.punch, 0)
    assert len(punches) == 1 and len(r.events) == 1
    p = punches[0]
    assert p.start_frame < p.peak_frame <= p.end_frame or p.start_frame <= p.peak_frame < p.end_frame
    assert abs(p.peak_ms - 1050) <= 60  # the fastest moment of the motion (0.1 s out, eased)
    assert p.limb.value == "left_hand" and p.measures["peak_speed"] >= S.punch_peak


def test_peak_speed_does_not_depend_on_frame_rate():
    peaks = [of(analyze(MotionScene(pair([punch(1.0, "r")]), 2.0, fps=fps)), EventType.punch)[0].measures["peak_speed"]
             for fps in (25, 30, 60)]
    assert max(peaks) / min(peaks) < 1.2


def test_combination_counts_each_punch_but_simultaneous_arms_once():
    r = analyze(MotionScene(pair([punch(1.0, "l"), punch(1.4, "r")]), 2.5))
    assert len(of(r, EventType.punch, 0)) == 2
    r = analyze(MotionScene(pair([punch(1.0, "l"), punch(1.0, "r")]), 2.0))
    assert len(of(r, EventType.punch, 0)) == 1


def test_motion_away_or_out_of_reach_is_not_an_attempt():
    assert analyze(MotionScene(pair([punch(1.0, "l", direction=-1)]), 2.0)).events == []
    assert analyze(MotionScene(pair([punch(1.0, "l")], distance=6.0), 2.0)).events == []


def test_low_confidence_joints_are_not_measurements():
    scene = MotionScene(pair([punch(1.0, "l")], wrist_conf=lambda t: 0.2 if 0.9 <= t <= 1.4 else 0.9), 2.0)
    assert analyze(scene).events == []


def test_kick_is_not_also_counted_as_a_punch():
    r = analyze(MotionScene(pair([kick(1.0, "r"), punch(1.05, "l")]), 2.0))
    assert len(of(r, EventType.kick, 0)) == 1
    assert of(r, EventType.punch) == []
    ledger = mm.ledger(r.events, r.runs, M)
    attempts = [c for c in ledger if c.source in (MomentumSource.kick_attempt, MomentumSource.strike_attempt)]
    assert [(c.source, c.points) for c in attempts] == [(MomentumSource.kick_attempt, 1.3)]


def test_camera_pan_is_not_fighter_movement():
    r = analyze(MotionScene(pair(distance=3.0), 4.0, pan_px_per_s=150))
    assert r.runs == [] and r.stats[0]["advance_s"] == r.stats[1]["retreat_s"] == 0
    assert np.nanmax(np.abs(r.approach)) < S.advance_speed
    # without removing the pan both fighters would seem to move
    raw = analyze(MotionScene(pair(distance=3.0), 4.0, pan_px_per_s=150), compensate=False)
    assert raw.runs


def test_walking_toward_the_opponent_is_advance_under_a_moving_camera():
    r = analyze(MotionScene(pair([walk(0.5, 2.5, 1.0)], distance=4.0), 3.0, pan_px_per_s=80))
    assert abs(r.stats[0]["advance_s"] - 2.0) <= 0.3
    assert r.stats[0]["retreat_s"] == 0 and r.stats[1]["advance_s"] == r.stats[1]["retreat_s"] == 0
    ledger = mm.ledger(r.events, r.runs, M)
    adv = [c for c in ledger if c.source == MomentumSource.advance]
    assert len(adv) == 1 and adv[0].fighter_id == FighterId.fighter_a
    assert adv[0].points == pytest.approx(M.advance_per_s * adv[0].quantity, abs=1e-3)


def test_fall_after_a_strike_is_a_possible_knockdown_otherwise_a_stance_change():
    r = analyze(MotionScene(pair([punch(1.0, "r", height=-0.15)], [fall(1.25)], distance=1.4), 3.0))
    kd = of(r, EventType.knockdown, 0)
    assert len(kd) == 1 and kd[0].target == FighterId.fighter_b and kd[0].confidence >= M.min_major_confidence
    assert of(r, EventType.punch, 0)[0].possible_contact  # the fist reached the opponent (2D)
    assert of(r, EventType.kick) == []  # flailing legs of the falling fighter are not attempts
    r = analyze(MotionScene(pair([], [fall(1.25)], distance=1.6), 3.0))
    assert of(r, EventType.knockdown) == [] and len(of(r, EventType.stance_change, 1)) == 1
    assert mm.ledger(r.events, r.runs, M) == []  # a slip earns nobody points


def test_downed_fighter_underneath_scores_nothing_and_following_him_down_is_no_fall():
    # Seen on a real clip: the knocked-down fighter's arms moving on his back were counted as
    # punches, and the winner kneeling over him to strike was taken for a knockdown "by" the
    # fighter on the ground.
    b = [fall(1.0), punch(2.05, "l")]  # down at 1 s (alone), arm motion upward while lying under A
    a = [walk(1.3, 2.0, 2.4), fall(2.2)]  # A comes over and goes down on top of him
    r = analyze(MotionScene(pair(a, b, distance=3.0), 3.5))
    assert of(r, EventType.punch, 1) == []
    assert of(r, EventType.knockdown) == [] and of(r, EventType.takedown) == []
    later = [e for e in of(r, EventType.stance_change, 0)]
    assert len(later) == 1 and "zaten yerdeydi" in later[0].note
    assert not [c for c in mm.ledger(r.events, r.runs, M) if c.fighter_id == FighterId.fighter_b]


def test_fall_after_close_contact_is_a_possible_takedown():
    r = analyze(MotionScene(pair([walk(0.3, 1.0, 1.0)], [fall(2.6)], distance=1.9), 4.0))
    td = of(r, EventType.takedown, 0)
    assert len(td) == 1 and td[0].target == FighterId.fighter_b
    assert of(r, EventType.knockdown) == []


def test_nothing_is_produced_while_identity_is_not_verified():
    lost_a = MotionScene(pair([punch(1.0, "l")]), 2.0, uncertain=lambda t, f: f == 0 and 0.8 <= t <= 1.5)
    assert analyze(lost_a).events == []
    lost_b = MotionScene(pair([punch(1.0, "l")]), 2.0, uncertain=lambda t, f: f == 1 and 0.8 <= t <= 1.5)
    r = analyze(lost_b)
    assert r.events == []
    assert not r.valid[1][30] and r.valid[0][30]  # shown as missing data, not as zero


def test_momentum_ledger_decay_formula_and_explanation():
    r = analyze(MotionScene(pair([punch(1.0, "l")]), 2.0))
    ledger = mm.ledger(r.events, r.runs, M)
    peak = r.events[0].peak_ms
    sources = {c.source for c in ledger}
    assert MomentumSource.strike_attempt in sources and all(c.event_id == r.events[0].event_id for c in ledger)
    m = mm.totals(ledger, np.array([peak, peak + 20000.0]), M.half_life_s)
    total = sum(c.points for c in ledger)
    assert m[0, 0] == pytest.approx(total) and m[0, 1] == pytest.approx(total / 2)  # 20 s half-life
    red = mm.red_share(m[0], m[1], M.prior)
    assert red[0] == pytest.approx(100 * (total + 4) / (total + 8))
    assert np.allclose(red + (100 - red), 100)
    # effect of the event = share with it minus share without it
    without = mm.red_share(m[0] - sum(mm.decayed(c, peak, M.half_life_s) for c in ledger), m[1], M.prior)
    assert red[0] - without[0] == pytest.approx(100 * (total + 4) / (total + 8) - 50)


def test_time_based_points_are_integrated_exactly():
    from fight_analyzer.contracts import MomentumContribution
    c = MomentumContribution(contribution_id="advance-0", fighter_id=FighterId.fighter_b, source=MomentumSource.advance,
                             start_ms=0, end_ms=10000, quantity=10, points=2.0)
    lam = math.log(2) / 20
    assert mm.decayed(c, 10000.0, 20)[()] == pytest.approx(0.2 / lam * (1 - math.exp(-lam * 10)))
    assert mm.decayed(c, 30000.0, 20)[()] == pytest.approx(mm.decayed(c, 10000.0, 20)[()] / 2)
    assert mm.decayed(c, -1.0, 20)[()] == 0


def test_results_round_trip_through_the_cache(tmp_path):
    from fight_analyzer.contracts import MotionTimeline
    from fight_analyzer.motion import store

    scene = MotionScene(pair([walk(0.3, 1.5, 1.0), punch(1.8, "l")], distance=4.0), 3.0)
    arrays, state, det, track, camera = scene.render()
    kin = tuple(km.compute(arrays, state, det, track, camera, f, S) for f in (0, 1))
    r = ev.analyze(arrays, camera, kin, S)
    assert r.runs and r.events
    data = store.events_data(r, arrays.timestamp_ms, camera, S)
    store.write_events(tmp_path, "k", {"x": 1}, data)
    back = store.read_events(tmp_path, "k")
    assert back.events == data.events and back.runs == data.runs and back.stats == data.stats
    assert data.signals["sample_ms"].size == 30 and data.signals["valid"].all()  # 3 s at 10 Hz
    timeline = MotionTimeline.model_validate_json(store.motion_timeline("0" * 32, back, S).model_dump_json())
    assert timeline.fighters[0].movement.count("advancing") >= 9
    mom = store.compute_momentum(back, M)
    store.write_momentum(tmp_path, "m", {}, mom)
    again = store.read_momentum(tmp_path, "m")
    assert again.contributions == mom.contributions and np.allclose(again.red_share, mom.red_share)
    assert np.allclose(again.red_share + (100 - again.red_share), 100) and again.red_share[-1] > 50


def test_weak_major_events_are_shown_but_add_no_points():
    r = analyze(MotionScene(pair([punch(1.0, "r", height=-0.15)], [fall(1.25)], distance=1.4), 3.0))
    strict = MomentumSettings(min_major_confidence=0.99)
    assert not [c for c in mm.ledger(r.events, r.runs, strict) if c.source == MomentumSource.knockdown]
    assert [c for c in mm.ledger(r.events, r.runs, M) if c.source == MomentumSource.knockdown]


@pytest.mark.parametrize("fps", [30, 60])
def test_possible_impact_needs_the_opponents_head_to_snap_after_contact(fps):
    """Contact in 2D is not proof of a landed strike; a head thrown back right after it is a
    (still unverified) sign of impact. The fighter's own head movement before does not count."""
    hit = analyze(MotionScene(pair([punch(1.0, "r", height=-0.15)], [head_snap(1.12)], distance=1.4), 2.5, fps=fps))
    blocked = analyze(MotionScene(pair([punch(1.0, "r", height=-0.15)], distance=1.4), 2.5, fps=fps))
    early = analyze(MotionScene(pair([punch(1.0, "r", height=-0.15)], [head_snap(0.7, back_s=0.15)], distance=1.4),
                                2.5, fps=fps))
    for r, impact in ((hit, 1.0), (blocked, 0.0), (early, 0.0)):
        p = of(r, EventType.punch, 0)
        assert len(p) == 1 and p[0].possible_contact
        assert p[0].measures["impact"] == impact, (impact, p[0].measures)
