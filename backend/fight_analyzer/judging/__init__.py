"""AI round scoring and decision estimate (Unified Rules, 10-Point Must, three virtual judges).

The result is always labelled as an AI estimate. Finishes (KO, TKO,
submission, disqualification, stoppage) come only from the user's input and
are never mixed with the scorecards; without a known ending a decision is only
computed when every scheduled round is in the recording and could be scored.
"""

from __future__ import annotations

from collections import Counter
from statistics import mean

from fight_analyzer.contracts import (
    FINISHES,
    Criterion,
    DataOrigin,
    DecisionType,
    EventType,
    Fighter,
    FighterId,
    FinishMethod,
    JudgeRoundScore,
    JudgeScorecard,
    MatchSetup,
    MatchVerdict,
    RoundAssessment,
    RoundSummary,
    Scorecards,
    VerdictStatus,
)

from . import evidence as ev_mod
from .evidence import FIGHTERS, NOT_MEASURED, AnalysisInputs, RoundEvidence
from .judges import CRITERION_TEXT, PROFILES, score_round

METHOD = ("Unified Rules of MMA, 10-Point Must; kriter sırası: etkili vuruş/grappling > etkili agresiflik > "
          "alan kontrolü; 3 sanal hakem profili (v1). Momentum kullanılmaz.")
METHOD_TEXT = {FinishMethod.ko: "nakavt (KO)", FinishMethod.tko: "teknik nakavt (TKO)",
               FinishMethod.submission: "submission", FinishMethod.disqualification: "diskalifiye",
               FinishMethod.referee_stoppage: "hakem/doktor durdurması", FinishMethod.no_contest: "no contest",
               FinishMethod.decision: "puan kararı", FinishMethod.unknown: "bilinmiyor"}
DECISION_TEXT = {DecisionType.unanimous: "oybirliğiyle karar", DecisionType.split: "bölünmüş karar",
                 DecisionType.majority: "çoğunluk kararı", DecisionType.unanimous_draw: "oybirliğiyle beraberlik",
                 DecisionType.majority_draw: "çoğunluk beraberliği", DecisionType.split_draw: "bölünmüş beraberlik"}


def decision_type(winners: list[FighterId | None]) -> tuple[DecisionType, FighterId | None]:
    c = Counter(winners)
    red, blue, draw = c[FIGHTERS[0]], c[FIGHTERS[1]], c[None]
    if red == 3 or blue == 3:
        return DecisionType.unanimous, FIGHTERS[0] if red == 3 else FIGHTERS[1]
    if red == 2 or blue == 2:
        w = FIGHTERS[0] if red == 2 else FIGHTERS[1]
        return (DecisionType.majority if draw == 1 else DecisionType.split), w
    if draw == 3:
        return DecisionType.unanimous_draw, None
    if draw == 2:
        return DecisionType.majority_draw, None
    return DecisionType.split_draw, None


def _apply_deductions(score: JudgeRoundScore, setup: MatchSetup) -> JudgeRoundScore:
    taken = {f: sum(d.points for d in setup.deductions if d.round == score.round and d.fighter_id == f)
             for f in FIGHTERS}
    if not score.scored or not any(taken.values()):
        return score
    red = max(5, score.red - taken[FIGHTERS[0]])
    blue = max(5, score.blue - taken[FIGHTERS[1]])
    note = f"Puan kesintisi (kullanıcı girdisi): kırmızı −{taken[FIGHTERS[0]]}, mavi −{taken[FIGHTERS[1]]}."
    winner = None if red == blue else FIGHTERS[0] if red > blue else FIGHTERS[1]
    return score.model_copy(update={"red": red, "blue": blue, "winner": winner,
                                    "deductions": {f.value: n for f, n in taken.items() if n},
                                    "reasons": [*score.reasons, note]})


def _summary(ev: RoundEvidence, scores: list[JudgeRoundScore], data_conf: float,
             names: dict[FighterId, str]) -> RoundSummary:
    if not scores[0].scored:
        return RoundSummary(number=ev.number, scored=False, red=10, blue=10, winner=None, judges_agree=0,
                            reason="Yetersiz veri: puanlanmadı.", confidence=0.0,
                            confidence_level=ev_mod.level(0.0))
    winners = Counter(s.winner for s in scores)
    winner, agree = winners.most_common(1)[0]
    if agree == 1:  # all three differ: no majority on the round
        winner = None
    pts = Counter((s.red, s.blue) for s in scores if s.winner == winner).most_common(1)[0][0] if agree > 1 \
        else (10, 10)
    lead = next(s for s in scores if s.winner == winner) if agree > 1 else scores[0]
    factor = {3: 1.0, 2: 0.85}.get(agree, 0.7)
    if lead.deciding_criterion == Criterion.effective_striking_grappling and winner is not None:
        t = ev.tally[winner]
        evidence = t.impact_punches + t.impact_kicks + t.knockdowns + t.takedowns
        factor *= 1.0 if evidence else 0.75
    elif lead.deciding_criterion is not None:
        factor *= 0.7
    else:
        factor *= 0.8
    if winner is None:
        reason = "Hakemler bu raundda ayrıştı ya da fark bulmadı." if agree == 1 else "10-10: belirleyici fark yok."
    else:
        reason = f"{names[winner]}: {CRITERION_TEXT[lead.deciding_criterion]} kriteriyle ({agree}/3 hakem)."
    conf = round(data_conf * factor, 3)
    return RoundSummary(number=ev.number, scored=True, red=pts[0], blue=pts[1], winner=winner, judges_agree=agree,
                        reason=reason, confidence=conf, confidence_level=ev_mod.level(conf))


def _late_knockdown(inputs: AnalysisInputs, names: dict[FighterId, str]) -> str | None:
    """A possible knockdown shortly before the recording ends hints at a finish (not decided here)."""
    end_ms = inputs.frame_count * 1000 / inputs.fps
    late = [e for e in inputs.events if e.type == EventType.knockdown and e.actor is not None
            and end_ms - (e.peak_ms or e.start_ms) <= 30_000]
    if not late:
        return None
    e = late[-1]
    return (f"Kayıt, {names[e.actor]} lehine olası bir knockdown'dan kısa süre sonra bitiyor: maç bitişle "
            "sonuçlanmış olabilir. Bitiş şeklini girerseniz sonuç ona göre gösterilir; sistem bitişi kendisi "
            "belirlemez.")


def compute(job_id: str, fighters: list[Fighter], setup: MatchSetup, inputs: AnalysisInputs) -> Scorecards:
    names = inputs.names
    assessments: list[RoundAssessment] = []
    evidences: list[RoundEvidence] = []
    data_confs: list[float] = []
    for number, start, end, marked in ev_mod.windows(setup, inputs.frame_count):
        ev = ev_mod.round_evidence(inputs, number, start, end, marked, setup.round_length_s)
        ok, why = ev_mod.scorable(ev)
        conf, notes = ev_mod.data_confidence(ev)
        not_measured = list(NOT_MEASURED)
        evidences.append(ev)
        data_confs.append(conf if ok else 0.0)
        assessments.append(RoundAssessment(
            number=number, marked=marked, start_frame=start, end_frame=end, start_s=round(ev.start_ms / 1000, 2),
            end_s=round(ev.end_ms / 1000, 2), recorded_s=ev.recorded_s, partial=ev.partial, scorable=ok,
            unscorable_reason=why, evidence=[ev_mod.contract_evidence(f, ev.tally[f]) for f in FIGHTERS],
            key_moments=ev.key_moments, damage=ev_mod.damage_summary(ev, names),
            grappling=ev_mod.grappling_summary(ev, names), not_measured=not_measured,
            confidence=conf if ok else 0.0, confidence_level=ev_mod.level(conf if ok else 0.0),
            confidence_notes=notes if ok else [why, *notes]))
    cards: list[JudgeScorecard] = []
    per_round: list[list[JudgeRoundScore]] = [[] for _ in evidences]
    for p in PROFILES:
        rounds = []
        for k, (ev, a) in enumerate(zip(evidences, assessments)):
            score = _apply_deductions(score_round(ev, p, names, a.scorable), setup)
            rounds.append(score)
            per_round[k].append(score)
        red = sum(r.red for r in rounds if r.scored)
        blue = sum(r.blue for r in rounds if r.scored)
        cards.append(JudgeScorecard(judge=p.contract(), rounds=rounds, total_red=red, total_blue=blue,
                                    winner=None if red == blue else FIGHTERS[0] if red > blue else FIGHTERS[1]))
    summaries = [_summary(ev, scores, c, names) for ev, scores, c in zip(evidences, per_round, data_confs)]
    verdict = _verdict(setup, assessments, summaries, cards, names, inputs)
    warnings = ["Momentum puanlamada kullanılmaz; deneysel bir göstergedir, kazanma olasılığı ya da hakem puanı değildir."]
    if not setup.rounds:
        warnings.append("Raund sınırları işaretlenmedi: tüm video tek raund olarak değerlendirildi.")
    if setup.ending.method == FinishMethod.unknown:
        warnings.append("Maçın nasıl bittiği girilmedi; sistem KO/TKO/submission gibi bitişleri kendisi belirlemez.")
    if inputs.exclusions:
        warnings.append("Dışlanan bölümler (tekrar vb.) puanlamaya katılmadı.")
    if not any("impact" in e.measures for e in inputs.events if e.possible_contact):
        warnings.append("Bu analizde 'olası etki' ölçümü yok (eski analiz ya da baş ölçülemedi); olası temaslar "
                        "etkisiz sayıldı. Güncel ölçüm için hareket analizini yeniden çalıştırın.")
    if any(t.uncertain_majors for ev in evidences for t in ev.tally.values()):
        warnings.append("Kanıtı zayıf olası knockdown/takedown'lar listede gösterildi ama puanlanmadı.")
    return Scorecards(job_id=job_id, data_origin=DataOrigin.measured, method=METHOD, fighters=fighters, setup=setup,
                      rounds=assessments, round_summaries=summaries, judges=cards, verdict=verdict, warnings=warnings)


def _verdict(setup: MatchSetup, rounds: list[RoundAssessment], summaries: list[RoundSummary],
             cards: list[JudgeScorecard], names: dict[FighterId, str], inputs: AnalysisInputs) -> MatchVerdict:
    end = setup.ending
    card_text = [f"{c.judge.name}: {c.total_red}-{c.total_blue}" for c in cards]
    if end.method == FinishMethod.no_contest:
        return MatchVerdict(status=VerdictStatus.no_contest, method=end.method, decision_type=None, winner=None,
                            cards=card_text, summary="No contest (kullanıcı girdisi). Kazanan yok.", reasons=[],
                            source="user_input", notes=["Skor kartları yalnızca bilgi amaçlıdır."])
    if end.method in FINISHES:
        when = ""
        if end.round:
            when = f", {end.round}. raund" + (f" {int(end.time_s // 60)}:{int(end.time_s % 60):02d}"
                                              if end.time_s is not None else "")
        return MatchVerdict(
            status=VerdictStatus.finish, method=end.method, decision_type=None, winner=end.winner, cards=card_text,
            summary=f"{names[end.winner]} {METHOD_TEXT[end.method]} ile kazandı{when} (kullanıcının girdiği bilgi).",
            reasons=["Maç bitişle sona erdiği için skor kartları kararı belirlemez; kartlar yalnızca bitişe kadarki "
                     "raundların AI değerlendirmesidir."],
            source="user_input", notes=["Bitiş şekli videodan otomatik doğrulanmadı."])
    complete = len(rounds) == setup.scheduled_rounds and all(r.marked for r in rounds)
    all_scored = all(r.scorable for r in rounds)
    if not (complete and all_scored):
        why = []
        if not complete:
            why.append(f"kayıtta işaretli {sum(r.marked for r in rounds)}/{setup.scheduled_rounds} raund var")
        if not all_scored:
            why.append("bazı raundlar yetersiz veri nedeniyle puanlanamadı")
        notes = [n for n in [_late_knockdown(inputs, names)] if n]
        if end.method == FinishMethod.unknown:
            notes.append("Maç puan kararına gittiyse tüm raundları işaretleyip bitiş şeklini 'puan kararı' seçin.")
        return MatchVerdict(status=VerdictStatus.not_computed, method=end.method, decision_type=None, winner=None,
                            cards=card_text, summary="Maç sonucu hesaplanmadı: " + " ve ".join(why) + ".",
                            reasons=[], source="ai_estimate", notes=notes)
    dtype, winner = decision_type([c.winner for c in cards])
    reasons = []
    for s in summaries:
        if s.winner is not None and (winner is None or s.winner == winner):
            reasons.append(f"{s.number}. raund {s.red}-{s.blue}: {s.reason}")
        elif s.winner is not None:
            reasons.append(f"{s.number}. raund rakibin ({names[s.winner]}): {s.reason}")
        else:
            reasons.append(f"{s.number}. raund: {s.reason}")
    agreement = {DecisionType.unanimous: 1.0, DecisionType.majority: 0.85, DecisionType.split: 0.7}.get(dtype, 0.8)
    conf = mean(s.confidence for s in summaries) * agreement
    notes = []
    if end.method == FinishMethod.unknown:
        conf *= 0.85
        notes.append("Bitiş şekli girilmedi; tüm raundlar kayıtta olduğu için puan kararına gidildiği varsayıldı.")
    conf = round(conf, 3)
    who = names[winner] if winner else "Beraberlik"
    summary = (f"AI tahmini: {who} — {DECISION_TEXT[dtype]} ({', '.join(card_text)})." if winner
               else f"AI tahmini: {DECISION_TEXT[dtype]} ({', '.join(card_text)}).")
    return MatchVerdict(status=VerdictStatus.decision, method=FinishMethod.decision, decision_type=dtype,
                        winner=winner, cards=card_text, summary=summary, reasons=reasons, source="ai_estimate",
                        confidence=conf, confidence_level=ev_mod.level(conf), notes=notes)
