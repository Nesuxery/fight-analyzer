"""AI judging under the Unified Rules: criteria order, 10-8/10-7/10-10, three judges,
decision types, finishes kept apart from decisions, and honesty about missing data."""

from __future__ import annotations

import numpy as np
import pytest

from fight_analyzer import judging
from fight_analyzer.contracts import (
    Criterion,
    DecisionType,
    ExcludedSegment,
    Fighter,
    FightEvent,
    FinishMethod,
    MatchEnding,
    MatchSetup,
    PointDeduction,
    RoundMark,
    VerdictStatus,
)
from fight_analyzer.judging.evidence import AnalysisInputs
from fight_analyzer.motion.events import MovementRun

FPS = 30.0
HZ = 10.0
RED, BLUE = "fighter_a", "fighter_b"
FIGHTERS = [Fighter(fighter_id=RED, display_name="Kırmızı", color="#ff2e4d"),
            Fighter(fighter_id=BLUE, display_name="Mavi", color="#19d6f0")]
_n = [0]


def strike(t_s: float, actor: str, kind: str = "punch", contact: bool = False, impact: bool = False) -> FightEvent:
    _n[0] += 1
    f = int(t_s * FPS)
    ms = f * 1000 / FPS
    measures = {"head_jolt": 0.5 if impact else 0.0, "impact": 1.0 if impact else 0.0} if contact else {}
    return FightEvent(event_id=f"{kind}-{_n[0]}", type=kind, actor=actor, target=BLUE if actor == RED else RED,
                      start_frame=f, end_frame=f, start_ms=ms, end_ms=ms, peak_frame=f, peak_ms=ms,
                      possible_contact=contact, measures=measures, confidence=0.8, data_origin="measured")


def major(t_s: float, actor: str, kind: str = "knockdown", confidence: float = 0.8) -> FightEvent:
    _n[0] += 1
    f = int(t_s * FPS)
    ms = f * 1000 / FPS
    return FightEvent(event_id=f"{kind}-{_n[0]}", type=kind, actor=actor, target=BLUE if actor == RED else RED,
                      start_frame=f - 10, end_frame=f, start_ms=ms - 333, end_ms=ms, peak_frame=f, peak_ms=ms,
                      confidence=confidence, data_origin="measured")


def control(t0: float, t1: float, actor: str) -> FightEvent:
    _n[0] += 1
    return FightEvent(event_id=f"gc-{_n[0]}", type="ground_control", actor=actor,
                      target=BLUE if actor == RED else RED, start_frame=int(t0 * FPS), end_frame=int(t1 * FPS),
                      start_ms=t0 * 1000, end_ms=t1 * 1000, measures={"seconds": t1 - t0}, confidence=0.5,
                      data_origin="measured")


def run(fighter: int, t0: float, t1: float, advancing: bool = True) -> MovementRun:
    return MovementRun(fighter, advancing, int(t0 * FPS), int(t1 * FPS), t0 * 1000, t1 * 1000, t1 - t0)


def inputs(events=(), runs=(), duration_s: float = 300.0, valid: float = 1.0, exclusions=()) -> AnalysisInputs:
    n = int(duration_s * HZ)
    good = np.zeros((2, n), bool)
    good[:, : int(n * valid)] = True
    signals = {"sample_ms": np.arange(n) * 100.0, "valid": good, "posture": np.zeros((2, n), np.int8),
               "camera_known": np.ones(n, bool)}
    frames = int(duration_s * FPS)
    return AnalysisInputs(events=list(events), runs=list(runs), signals=signals, sample_hz=HZ,
                          ident_state=np.zeros((frames, 2), np.int8), fps=FPS, frame_count=frames,
                          exclusions=list(exclusions), names={f.fighter_id: f.display_name for f in FIGHTERS})


def cards(inp: AnalysisInputs, setup: MatchSetup | None = None):
    return judging.compute("0" * 32, FIGHTERS, setup or MatchSetup(scheduled_rounds=1), inp)


def one_round(inp: AnalysisInputs):
    s = cards(inp, MatchSetup(scheduled_rounds=1, rounds=[RoundMark(number=1, start_frame=0,
                                                                     end_frame=inp.frame_count - 1)],
                              ending=MatchEnding(method=FinishMethod.decision)))
    return s, [j.rounds[0] for j in s.judges]


def test_volume_alone_does_not_beat_effective_strikes():
    red_volume = [strike(5 + i * 3, RED) for i in range(60)]  # 60 attempts that touch nothing
    blue_effect = [strike(10 + i * 40, BLUE, contact=True, impact=True) for i in range(5)]
    s, rounds = one_round(inputs(red_volume + blue_effect, [run(0, 10, 200)]))
    for r in rounds:
        assert r.winner == BLUE and r.deciding_criterion == Criterion.effective_striking_grappling
        assert (r.red, r.blue) == (9, 10)
    assert s.verdict.status == VerdictStatus.decision and s.verdict.winner == BLUE
    assert s.verdict.decision_type == DecisionType.unanimous and s.ai_estimate and "resmi" in s.disclaimer


def test_lower_criteria_only_break_ties_in_order():
    even = [strike(10, RED, contact=True, impact=True), strike(20, BLUE, contact=True, impact=True)]
    # aggressiveness: red presses forward far more -> red, on criterion 2
    _, rounds = one_round(inputs(even, [run(0, 10, 150), run(1, 160, 170)]))
    assert {r.deciding_criterion for r in rounds} == {Criterion.effective_aggressiveness}
    assert {r.winner for r in rounds} == {RED}
    # nothing differs: 10-10
    _, rounds = one_round(inputs(even))
    assert all((r.red, r.blue, r.winner) == (10, 10, None) for r in rounds)
    # a big striking edge for blue is not overturned by red's pressure
    blue_hits = even + [strike(30 + i * 20, BLUE, contact=True, impact=True) for i in range(4)]
    _, rounds = one_round(inputs(blue_hits, [run(0, 10, 290)]))
    assert all(r.winner == BLUE and r.deciding_criterion == Criterion.effective_striking_grappling for r in rounds)


def test_cage_control_is_the_last_criterion():
    even = [strike(10, RED, contact=True, impact=True), strike(20, BLUE, contact=True, impact=True)]
    # same aggressiveness (same forward time and volume), but blue keeps backing up -> red controls the area
    runs = [run(0, 10, 40), run(1, 50, 80), run(1, 100, 140, advancing=False)]
    _, rounds = one_round(inputs(even, runs))
    assert {r.deciding_criterion for r in rounds} == {Criterion.cage_control} and {r.winner for r in rounds} == {RED}


def test_knockdown_with_dominance_is_10_8_and_overwhelming_rounds_10_7():
    ev = [major(60, RED), *[strike(70 + i * 10, RED, contact=True, impact=True) for i in range(6)],
          strike(250, BLUE), control(80, 200, RED)]
    _, rounds = one_round(inputs(ev))
    assert all(r.winner == RED for r in rounds)
    assert sorted(r.blue for r in rounds) == [8, 8, 8]  # impact + dominance + duration: every judge 10-8
    ev2 = ev + [major(220, RED)]
    _, rounds = one_round(inputs(ev2))
    by = {j: r for j, r in zip("ABC", rounds)}
    assert by["A"].blue == 7 and by["B"].blue == 7 and by["C"].blue == 8  # judge C never gives 10-7
    # a knockdown with the opponent fighting back evenly is 10-9 for the stricter judges
    close = [major(60, RED), *[strike(100 + i * 10, BLUE, contact=True, impact=True) for i in range(3)]]
    _, rounds = one_round(inputs(close))
    assert all(r.blue >= 9 or r.red >= 9 for r in rounds)


def test_decision_types():
    dt = judging.decision_type
    assert dt([RED, RED, RED]) == (DecisionType.unanimous, RED)
    assert dt([RED, BLUE, RED]) == (DecisionType.split, RED)
    assert dt([BLUE, None, BLUE]) == (DecisionType.majority, BLUE)
    assert dt([None, None, None]) == (DecisionType.unanimous_draw, None)
    assert dt([None, RED, None]) == (DecisionType.majority_draw, None)
    assert dt([RED, BLUE, None]) == (DecisionType.split_draw, None)


def test_three_rounds_add_up_on_every_card():
    # round 1 blue clearly, round 2 red clearly, round 3 close (only judge-dependent weighting decides)
    ev = [*[strike(10 + i * 20, BLUE, contact=True, impact=True) for i in range(4)],
          *[strike(310 + i * 20, RED, contact=True, impact=True) for i in range(4)],
          strike(610, RED, contact=True, impact=True), major(700, BLUE, "takedown"), control(705, 718, BLUE)]
    setup = MatchSetup(scheduled_rounds=3, rounds=[RoundMark(number=k + 1, start_frame=int(k * 300 * FPS),
                                                             end_frame=int((k + 1) * 300 * FPS) - 1)
                                                   for k in range(3)],
                       ending=MatchEnding(method=FinishMethod.decision))
    s = cards(inputs(ev, duration_s=900), setup)
    assert len(s.rounds) == 3 and all(len(j.rounds) == 3 for j in s.judges)
    assert all(j.total_red + j.total_blue == 57 for j in s.judges)  # three 10-9 rounds per card
    assert s.verdict.status == VerdictStatus.decision and s.verdict.cards and s.verdict.reasons
    assert s.verdict.confidence is not None and s.verdict.confidence_level != "high"  # not validated


def test_finishes_are_not_scorecard_decisions():
    ev = [*[strike(10 + i * 20, BLUE, contact=True, impact=True) for i in range(6)]]
    setup = MatchSetup(scheduled_rounds=3, rounds=[RoundMark(number=1, start_frame=0, end_frame=8999)],
                       ending=MatchEnding(method=FinishMethod.ko, winner=RED, round=1, time_s=290))
    s = cards(inputs(ev), setup)
    assert s.verdict.status == VerdictStatus.finish and s.verdict.winner == RED  # the user's official result
    assert s.verdict.source == "user_input" and s.verdict.decision_type is None
    assert s.judges[0].winner == BLUE  # the card says otherwise: shown, but it does not decide
    with pytest.raises(ValueError):
        MatchEnding(method=FinishMethod.submission)  # a finish needs a winner
    with pytest.raises(ValueError):
        MatchEnding(method=FinishMethod.decision, winner=RED)  # decisions are computed, not entered


def test_incomplete_recording_and_unknown_ending_give_no_decision():
    ev = [strike(10, RED, contact=True, impact=True), major(280, RED)]
    s = cards(inputs(ev), MatchSetup(scheduled_rounds=3))
    assert s.verdict.status == VerdictStatus.not_computed and s.verdict.winner is None
    assert any("knockdown" in n for n in s.verdict.notes)  # hint at a possible finish, nothing decided
    assert not s.rounds[0].marked and any("işaretlenmedi" in w for w in s.warnings)


def test_too_little_data_is_not_scored():
    s = cards(inputs([strike(1, RED, contact=True, impact=True)], duration_s=11), MatchSetup(scheduled_rounds=1))
    a = s.rounds[0]
    assert not a.scorable and "Puanlanmadı" in a.unscorable_reason and a.confidence == 0
    assert all(not j.rounds[0].scored and j.total_red == j.total_blue == 0 for j in s.judges)
    poor = cards(inputs([strike(10, RED, contact=True, impact=True)], valid=0.04), MatchSetup(scheduled_rounds=1))
    assert not poor.rounds[0].scorable  # 12 s measured of 300 s


def test_point_deductions_change_the_round_score():
    ev = [strike(10 + i * 30, RED, contact=True, impact=True) for i in range(2)]
    setup = MatchSetup(scheduled_rounds=1, rounds=[RoundMark(number=1, start_frame=0, end_frame=8999)],
                       ending=MatchEnding(method=FinishMethod.decision),
                       deductions=[PointDeduction(round=1, fighter_id=RED, points=1, note="kafes tutma")])
    s = cards(inputs(ev), setup)
    r = s.judges[0].rounds[0]
    assert (r.red, r.blue, r.winner) == (9, 9, None) and r.deductions == {RED: 1}
    assert s.verdict.decision_type == DecisionType.unanimous_draw


def test_excluded_parts_are_not_judged():
    replay = [strike(100 + i, BLUE, contact=True, impact=True) for i in range(5)]  # a replay of blue's combination
    ex = [ExcludedSegment(start_frame=int(95 * FPS), end_frame=int(110 * FPS))]
    red = [strike(10 + i * 20, RED, contact=True, impact=True) for i in range(3)]
    _, rounds = one_round(inputs([*red, *replay], exclusions=ex))
    assert all(r.winner == RED for r in rounds)


def test_scores_never_use_momentum():
    import inspect

    import fight_analyzer.judging.evidence as e
    import fight_analyzer.judging.judges as j
    for module in (judging, e, j):
        assert "momentum" not in inspect.getsource(module).split('"""', 2)[-1].replace("Momentum kullanılmaz", "") \
            .replace("Momentum puanlamada kullanılmaz", "")
