"""Three virtual judges scoring rounds under the 10-Point Must System.

Every judge follows the Unified Rules order of criteria:

1. Effective striking / grappling (impact: legal strikes that land, knockdowns,
   takedowns that lead somewhere, ground control). This decides the round
   whenever it shows a clear difference.
2. Effective aggressiveness, only if 1 is even.
3. Fighting area (cage) control, only if 1 and 2 are even.
4. 10-10 only when nothing separates the fighters.

10-8 needs impact plus dominance and/or duration; 10-7 needs overwhelming
dominance, impact and duration together. Attempt counts alone never win a round
on criterion 1: an attempt without possible contact is worth a fraction of one
with it. The judges differ only in how they weigh the measured evidence (within
the rules), so their cards can differ like real judges' do. Momentum is not used.
"""

from __future__ import annotations

from dataclasses import dataclass

from fight_analyzer.contracts import Criterion, CriterionMargin, FighterId, JudgeProfile, JudgeRoundScore

from .evidence import FIGHTERS, RoundEvidence, Tally

CRITERION_TEXT = {
    Criterion.effective_striking_grappling: "Etkili vuruş ve etkili grappling",
    Criterion.effective_aggressiveness: "Etkili agresiflik",
    Criterion.cage_control: "Müsabaka alanı kontrolü",
}


@dataclass(frozen=True)
class Profile:
    judge_id: str
    name: str
    description: str
    # criterion 1: effective striking and grappling
    impact: float  # possible contact + the opponent's head snapped (closest sign of an effective strike)
    contact: float  # possible contact only: 2D overlap, often blocked or grazing
    attempt: float  # no contact at all: not proof of anything effective
    kick: float  # a kick counts this many punches
    knockdown: float
    takedown: float
    takedown_control: float  # extra when the takedown leads to top control
    control_per_s: float
    control_cap_s: float
    c1_abs: float
    c1_rel: float
    # criterion 2: effective aggressiveness (forward pressure with attempts to finish)
    advance_per_s: float
    volume: float
    c2_abs: float
    c2_rel: float
    # criterion 3: fighting area control (net forward movement, top position)
    c3_abs_s: float
    # 10-8 / 10-7
    ten_eight_needs: int  # how many of impact / dominance / duration (impact always required)
    dominance_ratio: float  # loser's criterion-1 score at most this share of the winner's
    duration_share: float  # winner's control or damage time as a share of the round
    allow_ten_seven: bool

    def contract(self) -> JudgeProfile:
        return JudgeProfile(judge_id=self.judge_id, name=self.name, description=self.description)


PROFILES = (
    Profile("A", "Hakem A", "Vuruş etkisine biraz daha fazla ağırlık verir; etki + baskınlık ya da süre varsa 10-8 verir.",
            impact=1.0, contact=0.3, attempt=0.05, kick=1.3, knockdown=5.0, takedown=2.0, takedown_control=1.0,
            control_per_s=0.06, control_cap_s=120, c1_abs=1.0, c1_rel=0.15,
            advance_per_s=0.1, volume=0.15, c2_abs=1.0, c2_rel=0.15, c3_abs_s=3.0,
            ten_eight_needs=2, dominance_ratio=0.35, duration_share=0.3, allow_ten_seven=True),
    Profile("B", "Hakem B", "Takedown ve yer kontrolüne biraz daha fazla ağırlık verir; 10-8 için etki, baskınlık ve süre ister.",
            impact=0.9, contact=0.25, attempt=0.04, kick=1.3, knockdown=4.5, takedown=3.0, takedown_control=1.5,
            control_per_s=0.1, control_cap_s=150, c1_abs=1.0, c1_rel=0.15,
            advance_per_s=0.1, volume=0.15, c2_abs=1.0, c2_rel=0.15, c3_abs_s=3.0,
            ten_eight_needs=3, dominance_ratio=0.35, duration_share=0.3, allow_ten_seven=True),
    Profile("C", "Hakem C", "Dengeli ve temkinli: birinci kriterde daha net fark arar, 10-8 için üç koşulu ve daha güçlü baskınlık ister, 10-7 vermez.",
            impact=1.0, contact=0.3, attempt=0.05, kick=1.3, knockdown=4.5, takedown=2.5, takedown_control=1.0,
            control_per_s=0.08, control_cap_s=120, c1_abs=1.5, c1_rel=0.2,
            advance_per_s=0.1, volume=0.15, c2_abs=1.5, c2_rel=0.2, c3_abs_s=5.0,
            ten_eight_needs=3, dominance_ratio=0.25, duration_share=0.35, allow_ten_seven=False),
)


def striking(t: Tally, p: Profile) -> float:
    impact = t.impact_punches + p.kick * t.impact_kicks
    contact_only = (t.contact_punches - t.impact_punches) + p.kick * (t.contact_kicks - t.impact_kicks)
    no_contact = (t.punches - t.contact_punches) + p.kick * (t.kicks - t.contact_kicks)
    return p.impact * impact + p.contact * contact_only + p.attempt * no_contact + p.knockdown * t.knockdowns


def grappling(t: Tally, p: Profile) -> float:
    return p.takedown * t.takedowns + p.takedown_control * t.takedowns_to_control + \
        p.control_per_s * min(t.control_s, p.control_cap_s)


def effective(t: Tally, p: Profile) -> float:
    return striking(t, p) + grappling(t, p)


def aggressiveness(t: Tally, p: Profile) -> float:
    return p.advance_per_s * t.advance_s + p.volume * (t.punches + t.kicks)


def area_control(t: Tally) -> float:
    return t.advance_s - t.retreat_s + 0.5 * t.control_s


def _decisive(r: float, b: float, abs_t: float, rel_t: float) -> bool:
    d = abs(r - b)
    return d >= abs_t and d >= rel_t * (r + b)


def _fmt(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def score_round(ev: RoundEvidence, p: Profile, names: dict[FighterId, str], scored: bool) -> JudgeRoundScore:
    red, blue = (ev.tally[f] for f in FIGHTERS)
    if not scored:
        return JudgeRoundScore(round=ev.number, scored=False, red=10, blue=10, winner=None, deciding_criterion=None,
                               criteria=[], reasons=["Yetersiz veri: bu raund puanlanmadı ve toplama katılmadı."])
    values = [
        (Criterion.effective_striking_grappling, effective(red, p), effective(blue, p), p.c1_abs, p.c1_rel),
        (Criterion.effective_aggressiveness, aggressiveness(red, p), aggressiveness(blue, p), p.c2_abs, p.c2_rel),
        (Criterion.cage_control, area_control(red), area_control(blue), p.c3_abs_s, 0.0),
    ]
    criteria: list[CriterionMargin] = []
    deciding = None
    winner = None
    reasons: list[str] = []
    for crit, r, b, abs_t, rel_t in values:
        decisive = _decisive(r, b, abs_t, rel_t)
        criteria.append(CriterionMargin(criterion=crit, red=round(r, 2), blue=round(b, 2), decisive=decisive))
        if deciding is not None:
            continue  # lower criteria are only looked at when the higher ones are even
        if decisive:
            deciding, winner = crit, (FIGHTERS[0] if r > b else FIGHTERS[1])
            reasons.append(f"{CRITERION_TEXT[crit]}: {names[FIGHTERS[0]]} {_fmt(r)} – {names[FIGHTERS[1]]} {_fmt(b)}; "
                           f"fark belirleyici → raund {names[winner]}.")
        else:
            reasons.append(f"{CRITERION_TEXT[crit]}: {_fmt(r)} – {_fmt(b)}, belirleyici fark yok"
                           + ("; bir sonraki kritere bakıldı." if crit != Criterion.cage_control else "."))
    if winner is None:
        reasons.append("Hiçbir kriterde fark yok: 10-10.")
        return JudgeRoundScore(round=ev.number, scored=True, red=10, blue=10, winner=None, deciding_criterion=None,
                               criteria=criteria, reasons=reasons)
    w, l = (red, blue) if winner == FIGHTERS[0] else (blue, red)
    loser_points = 9
    if deciding == Criterion.effective_striking_grappling:
        we, le = effective(w, p), effective(l, p)
        hits_w, hits_l = w.impact_punches + w.impact_kicks, l.impact_punches + l.impact_kicks
        impact = w.knockdowns >= 1 or (hits_w >= 5 and hits_w >= 3 * max(1, hits_l))
        dominance = le <= p.dominance_ratio * we
        duration = w.knockdowns >= 2 or w.control_s >= p.duration_share * max(ev.recorded_s, 1)
        met = [name for name, ok in (("etki", impact), ("baskınlık", dominance), ("süre", duration)) if ok]
        if impact and len(met) >= p.ten_eight_needs:
            loser_points = 8
            if (p.allow_ten_seven and impact and dominance and duration and w.knockdowns >= 2
                    and le <= 0.1 * we):
                loser_points = 7
                reasons.append("10-7: ezici üstünlük — etki, baskınlık ve süre birlikte, çoklu olası knockdown.")
            else:
                reasons.append(f"10-8: {', '.join(met)} koşulları sağlandı.")
        elif impact:
            reasons.append(f"10-8 verilmedi: yalnızca {', '.join(met)} sağlandı (bu hakem {p.ten_eight_needs} koşul ister).")
        if hits_w + w.knockdowns + w.takedowns == 0:
            reasons.append("Uyarı: fark etkisi görülmeyen temaslardan/denemelerden ve kontrol süresinden geliyor; "
                           "etkili vuruş kanıtı zayıf.")
    red_pts, blue_pts = (10, loser_points) if winner == FIGHTERS[0] else (loser_points, 10)
    return JudgeRoundScore(round=ev.number, scored=True, red=red_pts, blue=blue_pts, winner=winner,
                           deciding_criterion=deciding, criteria=criteria, reasons=reasons)
