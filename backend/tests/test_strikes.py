"""What a strike did (v2 Bölüm 3a), on synthetic skeletons with known actions: target zone,
outcome (landed / blocked / missed / unknown), significant strikes, elbows and strikes on a
downed opponent.

Outcomes are estimates from 2D joints. These tests check that each rule does what it says
(a reaction is needed for "landed", reaching a zone without one is never "landed", a strike
that reaches nothing is "missed"), not that the estimate is right on real footage.
"""

from __future__ import annotations

import numpy as np

from fight_analyzer.config import MomentumSettings, MotionSettings
from fight_analyzer.contracts import (
    EventType,
    EvidenceSignal,
    FighterId,
    FightEvent,
    FightPhase,
    MomentumSource,
    StrikeOutcome,
    TargetZone,
)
from fight_analyzer.motion import events as ev
from fight_analyzer.motion import kinematics as km
from fight_analyzer.motion import momentum as mm
from tests.support.motion_scenes import (
    Fighter,
    MotionScene,
    arm_at,
    cover,
    dip,
    elbow,
    fall,
    head_snap,
    kick,
    leg_hit,
    punch,
    pushed,
)

S = MotionSettings()
M = MomentumSettings()
RED, BLUE = FighterId.fighter_a, FighterId.fighter_b


def analyze(red=(), blue=(), distance: float = 1.4, duration: float = 2.5, blue_hands: str = "up"):
    scene = MotionScene((Fighter(x=0.0, facing=1, actions=list(red)),
                         Fighter(x=distance, facing=-1, actions=list(blue), hands=blue_hands)), duration)
    arrays, state, det, track, camera = scene.render()
    kin = tuple(km.compute(arrays, state, det, track, camera, f, S) for f in (0, 1))
    return ev.analyze(arrays, camera, kin, S)


def strikes(result, actor=RED):
    return [e for e in result.events if e.type in ev.STRIKE_TYPES and e.actor == actor]


def one(result, actor=RED) -> FightEvent:
    found = strikes(result, actor)
    assert len(found) == 1, [(e.type, e.peak_ms) for e in result.events]
    return found[0]


def test_a_strike_whose_way_back_is_faster_is_still_an_attempt():
    # Seen on the sample's knockout punch: out and back were one fast stretch and the way back
    # was the fastest moment, so the attempt was judged while the fist moved away from him.
    e = one(analyze([punch(1.0, "r", height=-0.15, out_s=0.12, back_s=0.05)], [head_snap(1.12)]))
    assert e.type == EventType.punch and e.peak_ms <= 1150 and e.measures["toward"] >= S.punch_toward


def test_a_head_strike_followed_by_a_head_snap_landed():
    e = one(analyze([punch(1.0, "r", height=-0.15)], [head_snap(1.12)]))
    assert (e.target_zone, e.outcome) == (TargetZone.head, StrikeOutcome.landed)
    assert e.evidence == [EvidenceSignal.zone_contact, EvidenceSignal.head_snap]
    assert 0.5 <= e.outcome_confidence <= 0.9 and e.measures["head_snap"] >= S.head_snap_min
    assert e.possible_contact  # the older 2D measure stays


def test_reaching_the_head_without_a_reaction_is_never_landed():
    # nothing in front of the face: it could have passed in front, grazed or landed lightly
    open_ = one(analyze([punch(1.0, "r", height=-0.15)], blue_hands="low"))
    assert (open_.target_zone, open_.outcome, open_.outcome_confidence) == (TargetZone.head, StrikeOutcome.unknown, None)
    assert open_.evidence == [EvidenceSignal.zone_contact]
    # the forearms are up in front of the face: blocked
    covered = one(analyze([punch(1.0, "r", height=-0.15)], [cover(0.5, 2.0)]))
    assert covered.outcome == StrikeOutcome.blocked and EvidenceSignal.guard_contact in covered.evidence
    # raising the guard at distance is not an elbow strike
    assert strikes(analyze([], [cover(0.5, 2.0)]), BLUE) == []


def test_a_strike_that_reaches_no_zone_missed():
    e = one(analyze([punch(1.0, "r")], distance=3.0))
    assert e.outcome == StrikeOutcome.missed and e.evidence == [EvidenceSignal.no_reach]
    assert e.outcome_confidence >= S.slip_missed_confidence and e.measures["zone_gap"] > S.miss_gap


def test_a_body_shot_lands_when_the_torso_is_pushed_back():
    # a clear push: fighters move all the time, so the threshold is high
    hit = one(analyze([punch(1.0, "r", height=0.6)], [pushed(1.1, 1.4)], distance=1.2, blue_hands="low"))
    assert (hit.target_zone, hit.outcome) == (TargetZone.body, StrikeOutcome.landed)
    assert EvidenceSignal.body_push in hit.evidence
    still = one(analyze([punch(1.0, "r", height=0.6)], distance=1.2, blue_hands="low"))
    assert still.target_zone == TargetZone.body and still.outcome != StrikeOutcome.landed


def test_a_leg_kick_lands_when_the_struck_leg_is_displaced():
    hit = one(analyze([kick(1.0, "r", height=-0.6)], [leg_hit(1.2, "l", amount=0.8)]))
    assert (hit.type, hit.target_zone, hit.outcome) == (EventType.kick, TargetZone.leg, StrikeOutcome.landed)
    assert EvidenceSignal.leg_buckle in hit.evidence
    # a small shift of the leg is footwork, not a landed kick
    small = one(analyze([kick(1.0, "r", height=-0.6)], [leg_hit(1.2, "l", amount=0.3)]))
    assert small.outcome == StrikeOutcome.unknown
    # the reaction is taken after the first contact, not where the kick is deepest on its way back
    still = one(analyze([kick(1.0, "r", height=-0.6)]))
    assert still.target_zone == TargetZone.leg and still.outcome == StrikeOutcome.unknown


def test_significant_strikes_every_one_at_distance_only_power_ones_in_the_clinch():
    far = one(analyze([punch(1.0, "r", height=-0.15)]))
    assert far.phase == FightPhase.distance and far.significant
    # blue holds red behind the neck: a clinch (close range without a grip is an exchange in the pocket)
    collar_tie = arm_at(0.0, 4.5, "l", (0.55, -0.75), (0.1, -0.9))
    close = analyze([punch(2.0, "r", out_s=0.12), punch(3.0, "l", out_s=0.07)], [collar_tie], distance=1.2,
                    duration=4.0)
    weak, strong = strikes(close)
    assert weak.phase == strong.phase == FightPhase.clinch
    assert weak.measures["peak_speed"] / S.punch_peak < S.power_strength and not weak.significant
    assert strong.measures["peak_speed"] / S.punch_peak >= S.power_strength and strong.significant


def test_an_elbow_at_close_range_is_one_elbow_attempt_and_no_punch():
    r = analyze([elbow(1.0, "r")], distance=0.8)
    e = one(r)
    assert e.type == EventType.elbow and e.limb.value == "right_hand" and e.phase == FightPhase.clinch
    assert e.measures["fold"] <= S.elbow_fold
    assert r.stats[0]["strike_attempts"] == 1  # counted with the punches
    ledger = mm.ledger(r.events, r.runs, M)
    attempt = [c.points for c in ledger if c.event_id == e.event_id and c.source == MomentumSource.strike_attempt]
    assert attempt == [M.strike_attempt]  # the same weight as a punch
    # the same motion out of reach is no elbow
    assert strikes(analyze([elbow(1.0, "r")], distance=1.4)) == []


def test_strikes_on_a_downed_opponent_are_ground_strikes():
    # red kneels over blue, who lies on the floor from the start
    r = analyze([dip(-1.0, 0.8, 0.1, None), punch(1.0, "r", height=1.5), punch(2.0, "l", height=1.5, out_s=0.5)],
                [fall(-1.0)], distance=0.5, duration=3.0)
    hard, soft = strikes(r)
    assert hard.type == soft.type == EventType.ground_strike
    assert hard.phase == soft.phase == FightPhase.ground
    assert hard.significant and not soft.significant  # on the ground only power strikes are significant
    assert r.stats[0]["strike_attempts"] == 2 and r.stats[0]["kick_attempts"] == 0
    assert strikes(r, BLUE) == []  # nothing from underneath
    ledger = mm.ledger(r.events, r.runs, M)
    assert sum(c.source == MomentumSource.strike_attempt for c in ledger) == 2


def test_events_of_older_analyses_still_open():
    # an event as stored before schema 1.11.0: the new fields are simply empty
    old = {"event_id": "punch-a-30", "type": "punch", "actor": "fighter_a", "target": "fighter_b", "start_frame": 25,
           "end_frame": 35, "start_ms": 833.3, "end_ms": 1166.7, "peak_frame": 30, "peak_ms": 1000.0,
           "limb": "left_hand", "possible_contact": True, "location": None, "measures": {"impact": 1.0},
           "confidence": 0.7, "attribution_confidence": 0.9, "attribution_uncertain": False,
           "data_origin": "measured", "note": None}
    e = FightEvent.model_validate(old)
    assert (e.outcome, e.target_zone, e.significant, e.phase, e.evidence) == (None, None, None, None, [])


def test_an_elbow_seen_from_behind_is_kept_as_a_punch():
    # from behind, a tight hook and an elbow look the same: the attempt stays, as a punch
    scene = MotionScene((Fighter(x=0.0, facing=1, actions=[elbow(1.0, "r")], head_conf=lambda t: 0.1),
                         Fighter(x=0.8, facing=-1)), 2.5)
    arrays, state, det, track, camera = scene.render()
    kin = tuple(km.compute(arrays, state, det, track, camera, f, S) for f in (0, 1))
    e = one(ev.analyze(arrays, camera, kin, S))
    assert e.type == EventType.punch and e.measures["from_behind"] == 1.0


def test_one_leg_does_not_kick_twice_in_a_moment():
    from fight_analyzer.contracts import Limb
    ts = np.arange(90) / 30.0
    a = ev._Candidate(EventType.kick, Limb.left_foot, 30, 33, 34, 2.0, 0.8, {}, 15)
    b = ev._Candidate(EventType.kick, Limb.left_foot, 40, 41, 43, 1.5, 0.8, {}, 15)  # 0.2 s after the first
    assert [c.peak for c in ev._deduplicate([a, b], ts, S)] == [33]
    later = ev._Candidate(EventType.kick, Limb.left_foot, 60, 62, 64, 1.5, 0.8, {}, 15)  # a second kick
    assert [c.peak for c in ev._deduplicate([a, later], ts, S)] == [33, 62]
    jab = ev._Candidate(EventType.punch, Limb.left_hand, 30, 32, 34, 1.5, 0.8, {}, 9)
    jab2 = ev._Candidate(EventType.punch, Limb.left_hand, 40, 42, 44, 1.5, 0.8, {}, 9)  # a double jab stays two
    assert [c.peak for c in ev._deduplicate([jab, jab2], ts, S)] == [32, 42]
