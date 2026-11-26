"""Falls and damage signals (v2 Bölüm 3a), on synthetic skeletons with known actions.

- A knockdown needs a strike of the opponent just before that did not clearly miss; a fall
  after strikes that all missed is a slip; sitting down counts (the posture alone says
  "transition" for a fighter sitting upright).
- A knockdown found only by inferring whose fall it is (the other fighter is followed with
  high confidence and stays on his feet) stays "possible" with low confidence.
- Damage signals follow landed strikes; nothing is derived from strikes that did not land.
"""

from __future__ import annotations

import numpy as np

from fight_analyzer.config import FeatureSettings, MomentumSettings, MotionSettings
from fight_analyzer.contracts import (
    DamageType,
    DataOrigin,
    EventType,
    EvidenceSignal,
    FighterId,
    FightEvent,
    MomentumSource,
    StrikeOutcome,
)
from fight_analyzer.motion import damage as dm
from fight_analyzer.motion import events as ev
from fight_analyzer.motion import kinematics as km
from fight_analyzer.motion import momentum as mm
from fight_analyzer.motion import store
from tests.support.motion_scenes import (
    Fighter,
    MotionScene,
    dip,
    fall,
    head_snap,
    punch,
    sit,
    step,
    walk,
)

S = MotionSettings()
M = MomentumSettings()
F = FeatureSettings()
RED, BLUE = FighterId.fighter_a, FighterId.fighter_b
HIT = [punch(1.0, "r", height=-0.15)]  # red's right hand to blue's head
SNAP = head_snap(1.12)  # blue's head is thrown back right after


def run(red=(), blue=(), distance=1.4, duration=3.5, conf=None, blue_unknown=None):
    """conf(t) -> (red, blue) identity confidence; blue_unknown(t): blue's identity not verified."""
    scene = MotionScene((Fighter(x=0.0, facing=1, actions=list(red)), Fighter(x=distance, facing=-1, actions=list(blue))),
                        duration, uncertain=(lambda t, f: f == 1 and blue_unknown(t)) if blue_unknown else
                        (lambda t, f: False))
    arrays, state, det, track, camera = scene.render()
    kin = tuple(km.compute(arrays, state, det, track, camera, f, S) for f in (0, 1))
    if conf is None:
        return ev.analyze(arrays, camera, kin, S), kin
    c = np.array([conf(i / scene.fps) for i in range(state.shape[0])], np.float32)
    c[state == 2] = 0.0
    inferred = ev.inferred_kinematics(arrays, state, det, c, track, camera, kin, S)
    return ev.analyze(arrays, camera, kin, S, c, inferred=inferred), kin


def of(result, type_):
    return [e for e in result.events if e.type == type_]


def signals(result, type_):
    return [d for d in result.damage if d.type == type_]


def test_a_fall_right_after_a_landed_strike_is_a_knockdown_after_a_miss_a_slip():
    r, _ = run(HIT, [SNAP, fall(1.25)], duration=3.0)
    (kd,) = of(r, EventType.knockdown)
    assert (kd.actor, kd.target) == (RED, BLUE) and kd.confidence >= 0.85
    assert kd.measures["landed_before"] == 1.0 and EvidenceSignal.head_snap in kd.evidence
    (signal,) = signals(r, DamageType.knockdown)
    assert (signal.target_fighter, signal.by_fighter, signal.linked_event_id) == (BLUE, RED, kd.event_id)
    # the same fall after a punch that came nowhere near him: he slipped
    r, _ = run([punch(1.0, "r")], [fall(1.25)], distance=3.0)
    assert of(r, EventType.knockdown) == [] and r.damage == []
    (slip,) = of(r, EventType.stance_change)
    assert slip.actor == BLUE and slip.note == "Yere indi; öncesindeki vuruş isabet etmedi"
    assert mm.ledger(r.events, r.runs, M) == [c for c in mm.ledger(r.events, r.runs, M)
                                              if c.source != MomentumSource.knockdown]


def test_sitting_down_after_a_landed_strike_is_a_knockdown():
    r, kin = run(HIT, [SNAP, sit(1.25)])
    seated = int(2.5 * 30)
    assert kin[1].posture[seated] == km.TRANSITION  # upright torso: the posture alone does not say "down"
    assert r.posture[1, seated] == km.GROUNDED  # the hips came down: grounded in the signals
    (kd,) = of(r, EventType.knockdown)
    assert kd.target == BLUE and kd.measures["hip_share"] <= S.fall_height_share and kd.confidence >= 0.85


def test_a_knockdown_found_by_inferring_who_fell_stays_possible_with_low_confidence():
    # blue is not identified until he is already going down; red is followed with high confidence
    def blue_unknown(t):
        return t < 1.3

    r, _ = run(HIT, [SNAP, sit(1.25)], conf=lambda t: (0.95, 0.45), blue_unknown=blue_unknown)
    (kd,) = of(r, EventType.knockdown)
    assert (kd.actor, kd.target) == (RED, BLUE)
    assert kd.confidence <= S.inferred_confidence_cap and EvidenceSignal.identity_inferred in kd.evidence
    assert kd.note.startswith("Olası; düşen kişi diğer dövüşçü sayıldı")
    (signal,) = signals(r, DamageType.knockdown)
    assert signal.confidence <= S.inferred_confidence_cap and EvidenceSignal.identity_inferred in signal.evidence
    # too weak for momentum points (shown, not scored)
    assert not [c for c in mm.ledger(r.events, r.runs, M) if c.source == MomentumSource.knockdown]
    # the strike before it is listed with its tag, but neither counted nor in the momentum
    (hit,) = [e for e in r.events if e.type == EventType.punch]
    assert hit.actor == RED and EvidenceSignal.identity_inferred in hit.evidence
    assert hit.attribution_uncertain and hit.attribution_confidence <= S.inferred_confidence_cap
    assert not ev.counted(hit) and r.stats[0]["strike_attempts"] == 0
    assert hit.event_id not in {c.event_id for c in mm.ledger(r.events, r.runs, M)}
    # without a confident other fighter, or without the inference, nothing is claimed
    r, _ = run(HIT, [SNAP, sit(1.25)], conf=lambda t: (0.6, 0.45), blue_unknown=blue_unknown)
    assert of(r, EventType.knockdown) == []


def test_damage_signals_follow_landed_strikes_only():
    r, _ = run(HIT, [SNAP], duration=2.5)
    (heavy,) = signals(r, DamageType.heavy_head_strike)
    assert heavy.target_fighter == BLUE and heavy.measures["head_snap"] >= S.heavy_head_snap
    assert heavy.kind.value == "immediate" and heavy.linked_event_id == of(r, EventType.punch)[0].event_id
    # the same punch without a reaction: no damage at all
    r, _ = run(HIT, [], duration=2.5)
    assert of(r, EventType.punch)[0].outcome != StrikeOutcome.landed and r.damage == []


def test_a_wobble_needs_a_deep_dip_of_the_hips_and_one_more_sign():
    r, _ = run(HIT, [SNAP, dip(1.25, 0.6), step(1.3, "r", 0.8)], duration=3.0)
    (w,) = signals(r, DamageType.wobble)
    assert w.target_fighter == BLUE and w.measures["dip"] >= S.wobble_dip
    assert set(w.evidence) == {EvidenceSignal.knee_buckle, EvidenceSignal.base_change, EvidenceSignal.no_offense}
    assert w.confidence <= 0.55
    # a step alone is footwork; a shallow dip is how a fighter bends to punch
    r, _ = run(HIT, [SNAP, step(1.3, "r", 0.8)], duration=3.0)
    assert signals(r, DamageType.wobble) == []
    r, _ = run(HIT, [SNAP, dip(1.25, 0.3), step(1.3, "r", 0.8)], duration=3.0)
    assert signals(r, DamageType.wobble) == []
    # throwing back right away is not a loss of balance either
    r, _ = run(HIT, [SNAP, dip(1.25, 0.6), step(1.3, "r", 0.8), punch(1.8, "l")], duration=3.0)
    assert signals(r, DamageType.wobble) == []


def test_backing_off_without_throwing_after_a_landed_strike_is_a_forced_retreat():
    r, _ = run(HIT, [SNAP, walk(1.3, 4.0, 1.2)], duration=4.5)
    (back,) = signals(r, DamageType.forced_retreat)
    assert back.target_fighter == BLUE and back.measures["retreat_share"] >= S.retreat_share
    assert set(back.evidence) == {EvidenceSignal.retreat, EvidenceSignal.no_offense} and back.confidence <= 0.5
    # throwing back while moving away is not "only defending"
    r, _ = run(HIT, [SNAP, walk(1.3, 4.0, 1.2), punch(2.0, "l")], duration=4.5)
    assert signals(r, DamageType.forced_retreat) == []


def _strike(t_s: float, actor: FighterId, landed: bool = False) -> FightEvent:
    frame = int(t_s * 30)
    return FightEvent(event_id=f"p-{actor.value}-{frame}", type=EventType.punch, actor=actor,
                      target=BLUE if actor == RED else RED, start_frame=frame, end_frame=frame, start_ms=t_s * 1000,
                      end_ms=t_s * 1000, peak_frame=frame, peak_ms=t_s * 1000, confidence=0.8,
                      outcome=StrikeOutcome.landed if landed else StrikeOutcome.unknown, significant=True,
                      data_origin=DataOrigin.measured)


def _output_case(blue_rate_after: float, blue_activity_after: float):
    """A 300 s round: blue throws 12 per minute and moves at 0.6 until red lands his 5th
    significant strike at 100 s, then at the given rate and activity."""
    events = [_strike(t, RED, landed=True) for t in (40, 55, 70, 85, 100)]
    events += [_strike(t, BLUE) for t in np.arange(2.5, 100, 5.0)]
    events += [_strike(t, BLUE) for t in np.arange(102, 300, 60 / blue_rate_after)]
    n = 3000
    sample_ms = np.arange(n) * 100.0
    activity = np.full((2, n), 0.6)
    activity[1, sample_ms >= 100_000] = blue_activity_after
    sig = {"sample_ms": sample_ms, "valid": np.ones((2, n), bool), "activity": activity}
    return events, sig


def test_a_lasting_drop_of_pace_and_mobility_after_damage_is_an_output_drop():
    events, sig = _output_case(blue_rate_after=4, blue_activity_after=0.3)
    (drop,) = dm.output_drop(events, [], sig, 10.0, [(1, 0, 8999)], [], 30.0, F)
    assert (drop.type, drop.kind.value, drop.target_fighter, drop.by_fighter) == (
        DamageType.output_drop, "cumulative", BLUE, RED)
    assert drop.time_ms == 100_000 and drop.linked_event_id == "p-fighter_a-3000" and drop.end_ms == 300_000
    assert drop.measures["pace_before"] > drop.measures["pace_after"] and drop.confidence <= F.output_drop_max_confidence
    # the same pace with the same mobility: no drop; without rounds nothing is claimed
    events, sig = _output_case(blue_rate_after=12, blue_activity_after=0.6)
    assert dm.output_drop(events, [], sig, 10.0, [(1, 0, 8999)], [], 30.0, F) == []
    events, sig = _output_case(blue_rate_after=4, blue_activity_after=0.3)
    assert dm.output_drop(events, [], sig, 10.0, [], [], 30.0, F) == []


def test_damage_signals_survive_the_cache_and_older_entries_read_without_them(tmp_path):
    scene = MotionScene((Fighter(x=0.0, facing=1, actions=list(HIT)), Fighter(x=1.4, facing=-1, actions=[SNAP])), 2.5)
    arrays, state, det, track, camera = scene.render()
    kin = tuple(km.compute(arrays, state, det, track, camera, f, S) for f in (0, 1))
    r = ev.analyze(arrays, camera, kin, S)
    data = store.events_data(r, arrays.timestamp_ms, camera, S)
    store.write_events(tmp_path, "e", {}, data)
    back = store.read_events(tmp_path, "e")
    assert back.damage == data.damage and len(back.damage) == 1
    manifest = tmp_path / "events" / "e" / "manifest.json"
    import json
    stored = json.loads(manifest.read_text(encoding="utf-8"))
    del stored["damage"]  # as written by events version 3
    manifest.write_text(json.dumps(stored), encoding="utf-8")
    assert store.read_events(tmp_path, "e").damage == []
    assert store.events_key("i", "c", S)[1]["version"] == store.EVENTS_VERSION == 5
