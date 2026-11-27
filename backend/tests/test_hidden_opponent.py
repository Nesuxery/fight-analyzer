"""Hidden-opponent estimate ("gizli rakip çıkarımı", v2 Bölüm 3b decision of 27 November 2026), on
synthetic skeletons in which one fighter's identity is switched off for a stretch.

Acceptance: where one of two tied-up fighters goes unmeasured, a separate low-confidence estimate
says they are still tied up, without saying whether standing or on the ground; a tied-up state
measured right before and after is carried over; it is not made when the fighters were apart, for a
short overlap in an exchange, for a fighter standing long after his opponent was last seen near him,
or after a long stretch with nobody measured without new evidence; a fighter down is evidence on its
own (ground frames only). The measured state never changes, and nothing of the estimate is counted,
credited as control or given momentum points. It survives the cache and does not depend on the
frame rate.

These tests check that each rule does what it says on clean skeletons, not that the estimate is
right on real footage (see NOTES.md for the frame check on the grappling recording).
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from fight_analyzer.config import MomentumSettings, MotionSettings
from fight_analyzer.contracts import (
    EventsSummary,
    EventType,
    EvidenceSignal,
    FighterEventCounts,
    FighterId,
    GrapplingState,
    PhaseTimes,
)
from fight_analyzer.motion import events as ev
from fight_analyzer.motion import grappling as gm
from fight_analyzer.motion import momentum as mm
from fight_analyzer.motion import store
from tests.support.motion_scenes import hold, kneel, lie, walk
from tests.test_grappling import TAKEDOWN_RED, TAKEN_DOWN, analyze, of

S = MotionSettings()
M = MomentumSettings()
RED = FighterId.fighter_a
CLINCH_ALL = [walk(1.0, 2.0, 1.0), hold(1.6, 60.0)]  # red walks into a clinch and keeps it


def hidden_blue(t0: float, t1: float):
    return lambda t, f: f == 1 and t0 <= t < t1


def secs(arrays, mask) -> float:
    return float(mask.sum()) * float(np.median(np.diff(arrays.timestamp_ms))) / 1000


def between(arrays, t0: float, t1: float) -> np.ndarray:
    ts = arrays.timestamp_ms / 1000
    return (ts >= t0) & (ts <= t1)


def nothing_counted(r) -> None:
    hidden = of(r, EventType.hidden_grappling)
    ids = {e.event_id for e in hidden}
    assert all(c.event_id not in ids for c in mm.ledger(r.events, r.runs, M))
    assert all(not e.attribution_uncertain and e.confidence <= S.hidden_max_confidence for e in hidden)
    assert all(e.data_origin.value == "measured" and EvidenceSignal.opponent_hidden in e.evidence for e in hidden)


def test_a_tie_up_with_one_fighter_unmeasured_is_estimated_apart_from_the_measured_state():
    # blue is not measured from 4 s to the end: the clinch goes on, but nothing is measured
    r, arrays, _ = analyze(CLINCH_ALL, [], distance=2.0, duration=10.0, uncertain=hidden_blue(4.0, 99.0))
    gap = between(arrays, 4.2, 9.8)
    assert (r.grappling.state[gap] == gm.UNKNOWN).all()  # the measured state is not filled
    assert (r.hidden.state[gap] == gm.TIED_UP).all() and (r.hidden.seen[gap] == 0).all()
    assert (r.hidden.state[between(arrays, 0.0, 3.8)] == gm.UNKNOWN).all()  # measured frames: no estimate
    assert 0 < r.hidden.conf[gap].max() <= S.hidden_max_confidence
    (e,) = of(r, EventType.hidden_grappling)
    assert e.actor is None and e.target is None and e.peak_frame is None
    assert e.measures["seconds"] == pytest.approx(6.0, abs=0.2) and e.measures["contact_distance"] == 0.0
    assert e.measures["red_seen_s"] == pytest.approx(6.0, abs=0.2) and e.measures["blue_seen_s"] == 0
    assert set(e.evidence) == {EvidenceSignal.opponent_hidden, EvidenceSignal.close_contact}
    assert "Gizli rakip çıkarımı" in e.note
    assert r.phases["hidden_s"] == pytest.approx(6.0, abs=0.2) and r.phases["unknown_s"] >= r.phases["hidden_s"]
    nothing_counted(r)
    assert r.stats[0]["clinch_control_s"] == r.stats[1]["clinch_control_s"] == 0


def test_a_tied_up_state_measured_before_and_after_is_carried_over():
    r, arrays, _ = analyze(CLINCH_ALL, [], distance=2.0, duration=14.0, uncertain=hidden_blue(4.0, 11.0))
    assert (r.hidden.state[between(arrays, 4.2, 10.8)] == gm.CLINCH).all()
    (e,) = of(r, EventType.hidden_grappling)
    assert e.actor is None and "klinç" in e.note
    # red on top before and after: the top position is carried over, but earns no control
    r, arrays, _ = analyze(TAKEDOWN_RED, TAKEN_DOWN, distance=2.0, duration=14.0, uncertain=hidden_blue(6.0, 11.0))
    assert (r.hidden.state[between(arrays, 6.2, 10.8)] == gm.RED_TOP).all()
    (e,) = of(r, EventType.hidden_grappling)
    assert (e.actor, e.target) == (RED, FighterId.fighter_b) and EvidenceSignal.top_position in e.evidence
    measured_control = sum(x.measures["seconds"] for x in of(r, EventType.ground_control, RED))
    assert r.stats[0]["control_s"] == pytest.approx(measured_control) and measured_control < 6.0
    nothing_counted(r)


def test_no_estimate_when_apart_or_for_a_short_overlap():
    r, *_ = analyze([], [], distance=3.0, duration=12.0, uncertain=hidden_blue(3.0, 10.0))  # apart, blue unseen
    assert (r.hidden.state == gm.UNKNOWN).all() and of(r, EventType.hidden_grappling) == []
    # close, but blue is back after 2 s: one fighter hid the other for a moment
    r, *_ = analyze([hold(0.0, 8.0)], [], distance=1.0, duration=8.0, uncertain=hidden_blue(3.0, 5.0))
    assert (r.hidden.state == gm.UNKNOWN).all() and r.phases["hidden_s"] == 0


def test_standing_long_after_the_opponent_was_last_seen_close_is_not_estimated():
    r, arrays, _ = analyze(CLINCH_ALL, [], distance=2.0, duration=50.0, uncertain=hidden_blue(4.0, 99.0))
    (e,) = of(r, EventType.hidden_grappling)
    assert e.end_ms / 1000 == pytest.approx(4.0 + S.hidden_standing_s, abs=0.5)
    assert (r.hidden.state[between(arrays, 4.0 + S.hidden_standing_s + 1, 50.0)] == gm.UNKNOWN).all()


def test_after_a_long_stretch_with_nobody_measured_new_evidence_is_needed():
    # red is not measured either from 10 to 25 s (a close-up): afterwards he stands, which says nothing
    unseen = lambda t, f: (f == 1 and t >= 4.0) or (f == 0 and 10.0 <= t < 25.0)  # noqa: E731
    r, arrays, _ = analyze(CLINCH_ALL, [], distance=2.0, duration=32.0, uncertain=unseen)
    assert (r.hidden.state[between(arrays, 4.2, 9.8)] == gm.TIED_UP).all()
    assert (r.hidden.state[between(arrays, 25.0, 32.0)] == gm.UNKNOWN).all()
    # ... but if he is down then, that is evidence of its own
    r, arrays, _ = analyze([*CLINCH_ALL, kneel(24.0)], [], distance=2.0, duration=32.0, uncertain=unseen)
    assert len(of(r, EventType.hidden_grappling)) == 2
    assert (r.hidden.state[between(arrays, 26.0, 31.5)] == gm.TIED_UP).all()


def test_a_fighter_down_with_nobody_seen_close_counts_for_his_ground_frames_only():
    r, arrays, _ = analyze([lie(2.0)], [], distance=3.0, duration=10.0, uncertain=lambda t, f: f == 1)
    (e,) = of(r, EventType.hidden_grappling)
    assert EvidenceSignal.close_contact not in e.evidence and "contact_distance" not in e.measures
    assert e.measures["seen_down_s"] == pytest.approx(e.measures["seconds"], abs=0.05)
    assert (r.hidden.state[between(arrays, 0.0, 1.9)] == gm.UNKNOWN).all()  # standing before: nothing


@pytest.mark.parametrize("fps", [25, 30, 60])
def test_the_estimate_does_not_depend_on_the_frame_rate(fps):
    r, arrays, _ = analyze(CLINCH_ALL, [], distance=2.0, duration=10.0, fps=fps, uncertain=hidden_blue(4.0, 99.0))
    assert r.phases["hidden_s"] == pytest.approx(6.0, abs=0.2)
    assert secs(arrays, r.hidden.state == gm.TIED_UP) == pytest.approx(6.0, abs=0.2)


def test_the_estimate_survives_the_cache_and_older_entries_still_open(tmp_path):
    r, arrays, camera = analyze(CLINCH_ALL, [], distance=2.0, duration=10.0, uncertain=hidden_blue(4.0, 99.0))
    data = store.events_data(r, arrays.timestamp_ms, camera, S)
    store.write_events(tmp_path, "e", {}, data)
    back = store.read_events(tmp_path, "e")
    assert np.array_equal(back.frames["grappling_hidden"], r.hidden.state)
    assert np.array_equal(back.frames["grappling_hidden_seen"], r.hidden.seen)
    assert back.phases["hidden_s"] == r.phases["hidden_s"]
    timeline = store.motion_timeline("0" * 32, back, S)
    assert timeline.phase[60] is None and timeline.phase_hidden[60] == GrapplingState.tied_up
    assert timeline.phase_hidden[20] is None and timeline.phase[20] == GrapplingState.clinch
    assert len(timeline.phase_hidden) == len(timeline.sample_ms)
    summary = EventsSummary(cache_key="e", cache_hit=False, version=store.EVENTS_VERSION, method="m", events=1,
                            camera_known_share=1.0, phases=PhaseTimes(**back.phases),
                            fighters=[FighterEventCounts(fighter_id=fid, **st) for fid, st in zip(ev.FIGHTERS, r.stats)])
    assert summary.phases.hidden_s == pytest.approx(6.0, abs=0.2)
    # an entry of events version 5: no estimate arrays, still readable, no estimate shown
    entry = tmp_path / "events" / "e"
    manifest = json.loads((entry / "manifest.json").read_text(encoding="utf-8"))
    for name in ("phase_hidden", "grappling_hidden", "grappling_hidden_conf", "grappling_hidden_seen"):
        (entry / f"{name}.npy").unlink()
        manifest["arrays"].remove(name)
    manifest["phases"].pop("hidden_s")
    (entry / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    old = store.read_events(tmp_path, "e")
    assert "grappling_hidden" not in old.frames and "grappling" in old.frames
    assert store.motion_timeline("0" * 32, old, S).phase_hidden == []
    assert PhaseTimes(**old.phases).hidden_s == 0
