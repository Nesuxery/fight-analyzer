"""Whose event (v2 Bölüm 2c): every event carries an attribution confidence from the
identity confidence; below the threshold it is "Kime ait belirsiz" and stays out of
the momentum (formula and weights unchanged)."""

from __future__ import annotations

import numpy as np

from fight_analyzer.config import MomentumSettings, MotionSettings
from fight_analyzer.contracts import EventType, ExcludedSegment, MomentumTimeline
from fight_analyzer.motion import events as ev
from fight_analyzer.motion import kinematics as km
from fight_analyzer.motion import momentum as mm
from fight_analyzer.motion import store
from tests.support.motion_scenes import Fighter, MotionScene, punch

S = MotionSettings()
M = MomentumSettings()


def scene() -> MotionScene:
    """Red throws at 1.0 s and at 3.0 s, blue at 2.0 s."""
    return MotionScene((Fighter(x=0.0, facing=1, actions=[punch(1.0, "l"), punch(3.0, "r")]),
                        Fighter(x=2.0, facing=-1, actions=[punch(2.0, "l")])), 4.0)


def analyze(conf_of=None):
    arrays, state, det, track, camera = scene().render()
    kin = tuple(km.compute(arrays, state, det, track, camera, f, S) for f in (0, 1))
    conf = None
    if conf_of is not None:
        conf = np.ones(state.shape, np.float32)
        for t in range(conf.shape[0]):
            conf[t] = conf_of(t / 30.0)
    return ev.analyze(arrays, camera, kin, S, conf), arrays, camera


def punches(result):
    return [e for e in result.events if e.type == EventType.punch]


def test_events_of_a_surely_known_fighter_are_attributed():
    result, _, _ = analyze(lambda t: (1.0, 1.0))
    assert len(punches(result)) == 3
    assert all(e.attribution_confidence == 1.0 and not e.attribution_uncertain for e in result.events)
    assert mm.unattributed(result.events) == []


def test_an_event_in_an_unverified_overlap_is_of_uncertain_attribution_and_earns_nothing():
    # around 3 s the red corner's identity rests on tracker continuity only (0.45)
    result, _, _ = analyze(lambda t: (0.45 if 2.6 <= t <= 3.4 else 1.0, 1.0))
    first, blue, late = punches(result)
    assert (first.attribution_confidence, blue.attribution_confidence) == (1.0, 1.0)
    assert late.attribution_confidence == 0.45 and late.attribution_uncertain
    assert not first.attribution_uncertain and not blue.attribution_uncertain
    # the same formula and weights; the uncertain event is simply not in the ledger
    sure, _, _ = analyze(lambda t: (1.0, 1.0))
    full = mm.ledger(sure.events, sure.runs, M)
    ledger = mm.ledger(result.events, result.runs, M)
    assert late.event_id not in {c.event_id for c in ledger}
    kept = [c for c in full if c.event_id != late.event_id]
    assert [(c.event_id, c.source, c.points) for c in ledger] == [(c.event_id, c.source, c.points) for c in kept]
    assert mm.unattributed(result.events) == [late.event_id]
    # in an excluded part the event is out anyway and not reported a second time
    replay = [ExcludedSegment(start_frame=80, end_frame=110)]
    assert mm.unattributed(result.events, replay) == []
    # just above the threshold it counts
    close, _, _ = analyze(lambda t: (S.attribution_min + 0.01 if 2.6 <= t <= 3.4 else 1.0, 1.0))
    assert not punches(close)[2].attribution_uncertain


def test_the_opponents_identity_does_not_decide_whose_the_event_is():
    result, _, _ = analyze(lambda t: (1.0, 0.45))
    first, blue, late = punches(result)
    assert not first.attribution_uncertain and not late.attribution_uncertain and blue.attribution_uncertain


def test_without_identity_confidence_nothing_is_marked():
    # analyses made before identities carried a confidence
    result, _, _ = analyze()
    assert all(e.attribution_confidence is None and not e.attribution_uncertain for e in result.events)


def test_the_left_out_events_survive_the_cache_and_reach_the_browser(tmp_path):
    result, arrays, camera = analyze(lambda t: (0.45 if 2.6 <= t <= 3.4 else 1.0, 1.0))
    data = store.events_data(result, arrays.timestamp_ms, camera, S)
    store.write_events(tmp_path, "e", {}, data)
    back = store.read_events(tmp_path, "e")
    assert [e.attribution_uncertain for e in punches(back)] == [False, False, True]
    mom = store.compute_momentum(back, M)
    late = punches(back)[2].event_id
    assert mom.unattributed == [late]
    store.write_momentum(tmp_path, "m", {}, mom)
    again = store.read_momentum(tmp_path, "m")
    assert again.unattributed == [late]
    timeline = MomentumTimeline.model_validate_json(
        store.momentum_timeline("0" * 32, mm.parameters(M), again, S.sample_hz).model_dump_json())
    assert timeline.unattributed_event_ids == [late]
    # the key of the momentum cache changed with the rule
    assert store.momentum_key("e", M)[1]["version"] == store.MOMENTUM_VERSION == 3
