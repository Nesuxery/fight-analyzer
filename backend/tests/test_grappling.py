"""Grappling states, their transitions and control (v2 Bölüm 3b), on synthetic skeletons with
known actions.

Acceptance: the per-frame state follows the scene (distance, clinch, who is on top on the
ground); a flicker or a short unmeasured stretch makes no transition; a takedown from the clinch
is told apart from a knockdown and a slip; a takedown the opponent gets up from at once is
"brief"; a level change that brings nobody down is a takedown attempt and a stuffed shot is no
takedown for the opponent; reversals and getting up from underneath are found; a held neck wrap
is a possible submission attempt with low confidence; control is split into ground, clinch and
active control; nothing depends on the frame rate, and the states survive the cache.

These tests check that each rule does what it says on clean skeletons, not that the estimates are
right on real footage.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from fight_analyzer.config import MomentumSettings, MotionSettings
from fight_analyzer.contracts import (
    DamageType,
    EventsSummary,
    EventType,
    EvidenceSignal,
    FighterEventCounts,
    FighterId,
    FightPhase,
    GrapplingState,
    MomentumSource,
    PhaseTimes,
)
from fight_analyzer.motion import events as ev
from fight_analyzer.motion import grappling as gm
from fight_analyzer.motion import kinematics as km
from fight_analyzer.motion import momentum as mm
from fight_analyzer.motion import store
from tests.support.motion_scenes import Fighter, MotionScene, arm_at, crouch, dip, hold, kneel, lean, lie, punch, walk

S = MotionSettings()
M = MomentumSettings()
RED, BLUE = FighterId.fighter_a, FighterId.fighter_b


def analyze(red=(), blue=(), distance: float = 1.0, duration: float = 8.0, fps: float = 30.0, **kw):
    scene = MotionScene((Fighter(x=0.0, facing=1, actions=list(red)),
                         Fighter(x=distance, facing=-1, actions=list(blue))), duration, fps=fps, **kw)
    arrays, state, det, track, camera = scene.render()
    kin = tuple(km.compute(arrays, state, det, track, camera, f, S) for f in (0, 1))
    r = ev.analyze(arrays, camera, kin, S)
    return r, arrays, camera


def of(r, type_: EventType, actor: FighterId | None = None):
    return [e for e in r.events if e.type == type_ and (actor is None or e.actor == actor)]


def state_at(r, arrays, t: float) -> int:
    return int(r.grappling.state[int(np.searchsorted(arrays.timestamp_ms / 1000, t))])


# red walks into a clinch (both hands on blue's torso), blue goes down on his back at 4 s and red kneels over him
CLINCH_IN = [walk(1.0, 2.0, 1.0), hold(1.6, 4.0)]
TAKEDOWN_RED = [*CLINCH_IN, walk(4.0, 4.4, 2.0), kneel(4.2)]
TAKEN_DOWN = [lie(4.0)]


def test_the_state_follows_the_scene_and_a_takedown_from_the_clinch_lands():
    r, arrays, camera = analyze(TAKEDOWN_RED, TAKEN_DOWN, distance=2.0, duration=10.0)
    assert state_at(r, arrays, 0.5) == gm.DISTANCE
    assert state_at(r, arrays, 3.0) == gm.CLINCH
    assert state_at(r, arrays, 7.0) == gm.RED_TOP
    (td,) = of(r, EventType.takedown)
    assert (td.actor, td.target, td.brief) == (RED, BLUE, False)
    assert td.measures["top_s"] >= S.takedown_hold_s and td.measures["from_clinch"] == 1.0
    assert {EvidenceSignal.close_contact, EvidenceSignal.top_position} <= set(td.evidence)
    assert of(r, EventType.knockdown) == [] and of(r, EventType.takedown_attempt) == []
    (gc,) = of(r, EventType.ground_control, RED)
    assert gc.target == BLUE and gc.measures["seconds"] >= 5.0 and gc.measures["active_s"] == 0.0
    # going to his knees over the opponent is part of the position, not a fall of his own
    assert of(r, EventType.stance_change) == []
    assert r.stats[0]["possible_takedowns"] == r.stats[0]["takedown_attempts"] == 1
    assert r.stats[0]["control_s"] == gc.measures["seconds"] and r.stats[1]["control_s"] == 0
    assert r.phases["clinch_s"] >= 2.0 and r.phases["ground_s"] >= 5.0
    ledger = mm.ledger(r.events, r.runs, M)
    assert [c.event_id for c in ledger if c.source == MomentumSource.takedown] == [td.event_id]


def test_a_takedown_the_opponent_gets_up_from_at_once_is_brief():
    r, *_ = analyze([*CLINCH_IN, walk(4.0, 4.4, 2.0), kneel(4.2, 5.4)], [lie(4.0, 5.2)], distance=2.0, duration=9.0)
    (td,) = of(r, EventType.takedown)
    assert td.actor == RED and td.brief is True and td.confidence <= 0.45
    assert td.measures["top_s"] < S.takedown_hold_s
    (up,) = of(r, EventType.get_up)
    assert (up.actor, up.target, up.measures["from_bottom"]) == (BLUE, RED, 1.0)
    # his arms moving while he gets up are no strikes, and standing up from the top is no get-up
    assert [e for e in r.events if e.type in ev.STRIKE_TYPES] == []
    assert r.stats[0]["brief_takedowns"] == 1 and r.stats[1]["get_ups"] == 1 and r.stats[0]["get_ups"] == 0
    assert mm.ledger(r.events, r.runs, M) == [c for c in mm.ledger(r.events, r.runs, M)
                                              if c.source != MomentumSource.takedown]  # too weak to score


def test_knockdown_and_slip_are_not_takedowns():
    # a strike, he goes down, the striker follows him down: a knockdown and top control, no takedown
    r, *_ = analyze([punch(1.0, "r", height=-0.15), walk(1.8, 2.2, 1.0), kneel(2.0)], [lie(1.25)],
                    distance=1.4, duration=7.0)
    assert len(of(r, EventType.knockdown, RED)) == 1 and of(r, EventType.takedown) == []
    assert of(r, EventType.ground_control, RED)
    # down on his own, away from the opponent: a slip, nobody is grappling
    r, arrays, _ = analyze([], [lie(2.0)], distance=2.2, duration=5.0)
    assert of(r, EventType.takedown) == [] and len(of(r, EventType.stance_change, BLUE)) == 1
    assert set(np.unique(r.grappling.state)) == {gm.DISTANCE}


def test_a_flicker_or_a_short_unmeasured_stretch_makes_no_transition():
    # the hips dip deep for a moment in the clinch
    r, *_ = analyze([hold(0.0, 6.0)], [dip(3.0, 1.0, 0.08, 0.08)], distance=1.0, duration=6.0)
    assert set(np.unique(r.grappling.state)) == {gm.CLINCH}
    assert [e.type for e in r.events] == [EventType.clinch]
    # blue is not measured for a second while red is on top: the position holds
    r, arrays, _ = analyze(TAKEDOWN_RED, TAKEN_DOWN, distance=2.0, duration=11.0,
                           uncertain=lambda t, f: f == 1 and 7.0 <= t <= 8.0)
    gap = (arrays.timestamp_ms / 1000 >= 7.2) & (arrays.timestamp_ms / 1000 <= 7.8)
    assert (r.grappling.raw[gap] == gm.UNKNOWN).all() and (r.grappling.state[gap] == gm.RED_TOP).all()
    measured = ~gap & (r.grappling.raw == gm.RED_TOP)
    assert r.grappling.conf[gap].max() < np.median(r.grappling.conf[measured])  # filled: less sure
    assert len(of(r, EventType.ground_control, RED)) == 1 and len(of(r, EventType.takedown)) == 1


def test_a_level_change_that_brings_nobody_down_is_a_takedown_attempt():
    r, *_ = analyze([dip(3.0, 0.4, 0.3, 0.4), lean(3.0, 4.0, 50)], [], distance=1.2, duration=6.0)
    (att,) = of(r, EventType.takedown_attempt)
    assert (att.actor, att.target) == (RED, BLUE) and att.confidence <= 0.5
    assert EvidenceSignal.level_change in att.evidence and of(r, EventType.takedown) == []
    assert r.stats[0]["takedown_attempts"] == 1 and r.stats[0]["possible_takedowns"] == 0
    assert mm.ledger(r.events, r.runs, M) == [] or all(c.event_id != att.event_id
                                                       for c in mm.ledger(r.events, r.runs, M))
    # the same lean far from the opponent is no attempt
    r, *_ = analyze([dip(3.0, 0.4, 0.3, 0.4), lean(3.0, 4.0, 50)], [], distance=2.5, duration=6.0)
    assert of(r, EventType.takedown_attempt) == []


def test_a_stuffed_shot_is_no_takedown_for_the_opponent():
    # blue shoots, red sprawls over him and blue ends up on his knees under red
    r, *_ = analyze([lean(2.4, 6.0, 50)], [lean(2.0, 6.0, 60), kneel(2.5)], distance=1.2, duration=5.5)
    assert of(r, EventType.takedown) == []
    attempts = of(r, EventType.takedown_attempt, BLUE)
    assert len(attempts) == 1 and attempts[0].start_ms < 2500
    assert of(r, EventType.takedown_attempt, RED) == []


def test_a_reversal_and_getting_up_from_underneath():
    r, arrays, _ = analyze([*CLINCH_IN, walk(4.0, 4.4, 2.0), kneel(4.2, 8.0), lie(8.1)],
                           [lie(4.0, 8.0), kneel(8.2)], distance=2.0, duration=13.0)
    (rev,) = of(r, EventType.reversal)
    assert (rev.actor, rev.target) == (BLUE, RED)
    assert {EvidenceSignal.position_change, EvidenceSignal.top_position} <= set(rev.evidence)
    assert state_at(r, arrays, 6.0) == gm.RED_TOP and state_at(r, arrays, 11.0) == gm.BLUE_TOP
    assert len(of(r, EventType.ground_control, RED)) == len(of(r, EventType.ground_control, BLUE)) == 1
    assert r.stats[1]["reversals"] == 1 and r.stats[0]["reversals"] == 0
    # red steps away from blue, who gets up 2.5 s later: a get-up, but no longer from underneath
    r, *_ = analyze([*CLINCH_IN, walk(4.0, 4.4, 2.0), kneel(4.2, 7.0), walk(7.2, 8.0, -3.0)], [lie(4.0, 10.0)],
                    distance=2.0, duration=13.0)
    (up,) = of(r, EventType.get_up)
    assert up.actor == BLUE and up.peak_ms >= 10000 and up.measures["from_bottom"] == 0.0


def test_a_crouch_in_the_clinch_is_no_get_up_and_a_spectator_is_no_opponent():
    # red drops his level deep for two seconds in the clinch (hips low, torso forward) and comes
    # back up: never down on the mat, so no get-up (seen on the grappling recording: a wrestler
    # bent over his opponent at the cage was "getting up" three times)
    r, *_ = analyze([hold(0.0, 7.0), crouch(2.0, 4.0, 0.9), lean(2.0, 4.0, 50)], [], distance=1.0, duration=7.0)
    assert (r.posture[0] == km.GROUNDED).sum() / 30 >= 1.0  # meanwhile he counts as down (3a's definition)
    assert of(r, EventType.get_up) == [] and of(r, EventType.takedown) == []
    assert of(r, EventType.stance_change) == []  # nor did he fall: his hips never reached the mat
    # blue's identity jumps to a far smaller person (a spectator) for two seconds: unknown, not distance
    blue_size = lambda t: 0.35 if 3.0 <= t <= 5.0 else 1.0  # noqa: E731
    scene = MotionScene((Fighter(x=0.0, facing=1), Fighter(x=2.0, facing=-1, size=blue_size)), 8.0)
    arrays, state, det, track, camera = scene.render()
    kin = tuple(km.compute(arrays, state, det, track, camera, f, S) for f in (0, 1))
    r = ev.analyze(arrays, camera, kin, S)
    ts = arrays.timestamp_ms / 1000
    assert (r.grappling.state[(ts >= 3.3) & (ts <= 4.7)] == gm.UNKNOWN).all()
    assert (r.grappling.state[ts <= 2.5] == gm.DISTANCE).all()


# blue bends into red; red's right forearm across his neck (a guillotine), from 2 s to t1
def _guillotine(t1: float):
    neck = arm_at(2.0, t1, "r", (0.25, -0.38), (-0.27, -0.38))
    waist = arm_at(2.0, t1, "l", (0.2, -0.5), (0.5, -0.3))  # the other hand on his back
    return [neck, waist], [lean(2.0, t1, 60)]


def test_a_held_neck_wrap_is_a_possible_submission_attempt_with_low_confidence():
    red, blue = _guillotine(6.0)
    r, *_ = analyze(red, blue, distance=0.9, duration=8.0)
    (sub,) = of(r, EventType.submission_attempt)
    assert (sub.actor, sub.target) == (RED, BLUE) and sub.confidence <= S.sub_max_confidence
    assert sub.evidence == [EvidenceSignal.neck_wrap] and sub.measures["seconds"] >= 3.5
    (danger,) = [d for d in r.damage if d.type == DamageType.submission_danger]
    assert danger.target_fighter == BLUE and danger.by_fighter == RED and danger.linked_event_id == sub.event_id
    assert danger.confidence <= 0.35 and 0.3 <= danger.severity <= 1.0
    assert r.stats[0]["submission_attempts"] == 1
    # a short wrap is nothing, and a clinch with both hands on the torso is nothing
    red, blue = _guillotine(4.5)
    assert of(analyze(red, blue, distance=0.9, duration=6.0)[0], EventType.submission_attempt) == []
    assert of(analyze([hold(0.0, 6.0, reach=0.9)], [], distance=0.9, duration=6.0)[0],
              EventType.submission_attempt) == []


def test_control_is_split_into_ground_clinch_and_active_control():
    # red kneels over blue (down from the start) and strikes twice: active control around the strikes
    hits = [dip(-1.0, 0.8, 0.1, None), punch(1.0, "r", height=1.5), punch(2.0, "l", height=1.5)]
    r, *_ = analyze(hits, [lie(-1.0)], distance=0.5, duration=6.0)
    strikes = [e for e in r.events if e.type in ev.STRIKE_TYPES]
    assert len(strikes) == 2 and all(e.phase == FightPhase.ground for e in strikes)
    (gc,) = of(r, EventType.ground_control, RED)
    assert 2.5 <= gc.measures["active_s"] < gc.measures["seconds"]
    assert r.stats[0]["active_control_s"] == pytest.approx(gc.measures["active_s"], abs=0.05)
    # holding the position without striking is control, but not active control
    r, *_ = analyze([dip(-1.0, 0.8, 0.1, None)], [lie(-1.0)], distance=0.5, duration=6.0)
    assert r.stats[0]["control_s"] >= 5.0 and r.stats[0]["active_control_s"] == 0
    # in the clinch red drives blue back: clinch control is red's, in its own field
    r, *_ = analyze([walk(2.0, 4.0, 0.6), hold(0.0, 6.0)], [walk(2.0, 4.0, 0.6)], distance=1.0, duration=6.0)
    (clinch,) = of(r, EventType.clinch)
    assert clinch.measures["red_control_s"] >= 3.0 and clinch.measures["blue_control_s"] == 0
    assert r.stats[0]["clinch_control_s"] >= 3.0 and r.stats[1]["clinch_control_s"] == 0
    assert r.stats[0]["control_s"] == 0  # clinch control is not ground control


@pytest.mark.parametrize("fps", [25, 30, 60])
def test_states_and_transitions_do_not_depend_on_the_frame_rate(fps):
    r, *_ = analyze(TAKEDOWN_RED, TAKEN_DOWN, distance=2.0, duration=10.0, fps=fps)
    (td,) = of(r, EventType.takedown)
    assert td.peak_ms == pytest.approx(4300, abs=150) and td.brief is False
    assert r.phases["ground_s"] == pytest.approx(5.6, abs=0.25)
    assert r.phases["clinch_s"] == pytest.approx(2.6, abs=0.15)  # from 1.3 torso lengths apart (1.7 s) to 4.3 s


def test_grappling_states_survive_the_cache_and_older_entries_still_open(tmp_path):
    r, arrays, camera = analyze(TAKEDOWN_RED, TAKEN_DOWN, distance=2.0, duration=10.0)
    data = store.events_data(r, arrays.timestamp_ms, camera, S)
    store.write_events(tmp_path, "e", {}, data)
    back = store.read_events(tmp_path, "e")
    assert np.array_equal(back.frames["grappling"], r.grappling.state)
    assert np.array_equal(back.frames["clinch_by"], r.grappling.clinch_by)
    assert back.phases == r.phases
    timeline = store.motion_timeline("0" * 32, back, S)
    assert timeline.phase[5] == GrapplingState.distance and timeline.phase[70] == GrapplingState.ground_red_top
    assert len(timeline.phase) == len(timeline.sample_ms) == len(timeline.fighters[0].facing_away)
    assert all(v is not None for v in timeline.fighters[0].wrists_measured[:20])
    summary = EventsSummary(cache_key="e", cache_hit=False, version=store.EVENTS_VERSION, method="m", events=1,
                            camera_known_share=1.0, phases=PhaseTimes(**back.phases),
                            fighters=[FighterEventCounts(fighter_id=fid, **st) for fid, st in zip(ev.FIGHTERS, r.stats)])
    assert summary.fighters[0].possible_takedowns == 1
    # an entry written before events version 5: no states, no phase, still readable
    entry = tmp_path / "events" / "e"
    manifest = json.loads((entry / "manifest.json").read_text(encoding="utf-8"))
    for name in (*store.NEW_SIGNAL_ARRAYS, *store.FRAME_ARRAYS):
        (entry / f"{name}.npy").unlink()
        manifest["arrays"].remove(name)
    del manifest["phases"]
    (entry / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    old = store.read_events(tmp_path, "e")
    assert old.frames == {} and old.phases == {}
    timeline = store.motion_timeline("0" * 32, old, S)
    assert timeline.phase == [] and timeline.fighters[0].facing_away == []
