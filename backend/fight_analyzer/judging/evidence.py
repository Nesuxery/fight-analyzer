"""What the analysis measured in each round, the input of every judge.

Built from the cached analysis (events, movement runs, 10 Hz signals,
identity states). Parts the user excluded (replays etc.) are left out with the
same rules as the statistics. The experimental momentum is not used.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from fight_analyzer.contracts import (
    ConfidenceLevel,
    EdgeSummary,
    EventType,
    ExcludedSegment,
    FighterId,
    FighterRoundEvidence,
    FightEvent,
    KeyMoment,
    MatchSetup,
)
from fight_analyzer.motion import exclusions as excl
from fight_analyzer.motion.events import MovementRun
from fight_analyzer.motion.kinematics import GROUNDED

FIGHTERS = (FighterId.fighter_a, FighterId.fighter_b)
STRIKES = {EventType.punch, EventType.knee, EventType.kick}
MIN_MAJOR_CONFIDENCE = 0.5  # possible knockdowns/takedowns below this are reported, not scored
TAKEDOWN_CONTROL_S = 3.0  # a takedown followed by top control within this time "leads somewhere"
MIN_RECORDED_S = 30.0  # less fight time than this in a round: not scored
MIN_MEASURED_S = 15.0  # each fighter must be measurable at least this long
CONFIDENCE_CEILING = 0.6  # detection is not validated on independent footage
VALIDATED = False  # with independent validation the "high" level becomes possible

NOT_MEASURED = [
    "Gerçek hasar (sersemleme, kesik, kanama) doğrudan ölçülmüyor; yalnızca dolaylı göstergeler var.",
    "Vuruşların gerçekten isabet edip etmediği bilinmiyor; 2B görüntüde yalnızca olası temas ve olası etki "
    "(temastan hemen sonra rakibin başının savrulması; eşiği doğrulanmadı) var.",
    "Submission girişimleri ve submission tehlikesi tespit edilmiyor.",
    "Yerde pozisyon geliştirme (guard geçişi, mount, sırt alma) tespit edilmiyor.",
    "Kafes/alan konumu ölçülmüyor; alan kontrolü ileri-geri hareketten tahmin ediliyor.",
]


@dataclass
class AnalysisInputs:
    events: list[FightEvent]
    runs: list[MovementRun]
    signals: dict[str, np.ndarray]
    sample_hz: float
    ident_state: np.ndarray | None  # [F, 2]: 0 tracked, 1 occluded, 2 uncertain
    fps: float
    frame_count: int
    exclusions: list[ExcludedSegment]
    names: dict[FighterId, str]


@dataclass
class Tally:
    """One fighter in one round (richer than the contract: judges weigh kicks apart)."""

    punches: int = 0  # punch + knee attempts
    kicks: int = 0
    contact_punches: int = 0
    contact_kicks: int = 0
    impact_punches: int = 0  # possible contact + the opponent's head snapped right after
    impact_kicks: int = 0
    knockdowns: int = 0
    takedowns: int = 0
    takedowns_to_control: int = 0
    control_s: float = 0.0
    advance_s: float = 0.0
    retreat_s: float = 0.0
    measured_s: float = 0.0
    uncertain_s: float = 0.0
    uncertain_majors: int = 0


@dataclass
class RoundEvidence:
    number: int
    marked: bool
    start_frame: int
    end_frame: int
    start_ms: float
    end_ms: float
    recorded_s: float
    round_length_s: float
    tally: dict[FighterId, Tally]
    ground_s: float
    camera_known_share: float
    excluded_s: float
    key_moments: list[KeyMoment] = field(default_factory=list)

    @property
    def partial(self) -> bool:
        return self.recorded_s < self.round_length_s * 0.95


def windows(setup: MatchSetup, frame_count: int) -> list[tuple[int, int, int, bool]]:
    """(number, start_frame, end_frame, marked) of the rounds to judge."""
    if not setup.rounds:
        return [(1, 0, max(0, frame_count - 1), False)]
    return [(r.number, min(r.start_frame, frame_count - 1), min(r.end_frame, frame_count - 1), True)
            for r in sorted(setup.rounds, key=lambda r: r.number) if r.start_frame < frame_count]


def _clip(a: float, b: float, lo: float, hi: float, iv: excl.Intervals) -> float:
    """Seconds of [a, b] inside [lo, hi) and outside excluded parts."""
    return excl.outside_ms(max(a, lo), min(b, hi), iv) / 1000


def _label(e: FightEvent, names: dict[FighterId, str]) -> str:
    who = names.get(e.actor, "?") if e.actor else "?"
    kind = {EventType.punch: "yumruk denemesi", EventType.knee: "diz denemesi", EventType.kick: "tekme denemesi",
            EventType.knockdown: "olası knockdown", EventType.takedown: "olası takedown",
            EventType.ground_control: "tahmini yer kontrolü"}.get(e.type, e.type.value)
    extra = " (olası etki: rakibin başı savruldu)" if e.measures.get("impact", 0) >= 1         else " (olası temas)" if e.possible_contact else ""
    if e.type == EventType.ground_control:
        extra = f" ({e.measures.get('seconds', 0):.0f} sn)"
    return f"{who}: {kind}{extra}"


def _weight(e: FightEvent) -> float:
    if e.type == EventType.knockdown:
        return 10 + e.confidence
    if e.type == EventType.takedown:
        return 6 + e.confidence
    if e.type == EventType.ground_control:
        return 4 + e.measures.get("seconds", 0) / 60
    if e.type in STRIKES:
        impact = e.measures.get("impact", 0) >= 1
        return (7 if impact else 3 if e.possible_contact else 1) + (0.5 if e.type == EventType.kick else 0) + e.confidence
    return 0


def round_evidence(inp: AnalysisInputs, number: int, start: int, end: int, marked: bool,
                   round_length_s: float) -> RoundEvidence:
    iv = excl.intervals(inp.exclusions, inp.fps)
    lo, hi = start * 1000 / inp.fps, (end + 1) * 1000 / inp.fps
    tally = {f: Tally() for f in FIGHTERS}
    in_round: list[FightEvent] = []
    for e in inp.events:
        f = excl.event_frame(e)
        if not (start <= f <= end) or excl.frame_excluded(f, inp.exclusions):
            continue
        in_round.append(e)
        if e.actor is None:
            continue
        t = tally[e.actor]
        impact = e.possible_contact and e.measures.get("impact", 0) >= 1
        if e.type in (EventType.punch, EventType.knee):
            t.punches += 1
            t.contact_punches += e.possible_contact
            t.impact_punches += impact
        elif e.type == EventType.kick:
            t.kicks += 1
            t.contact_kicks += e.possible_contact
            t.impact_kicks += impact
        elif e.type in (EventType.knockdown, EventType.takedown):
            if e.confidence < MIN_MAJOR_CONFIDENCE:
                t.uncertain_majors += 1
            elif e.type == EventType.knockdown:
                t.knockdowns += 1
            else:
                t.takedowns += 1
                peak = e.peak_ms if e.peak_ms is not None else e.start_ms
                followed = e.measures.get("on_top_after", 0) >= 1 or any(
                    c.type == EventType.ground_control and c.actor == e.actor
                    and 0 <= c.start_ms - peak <= TAKEDOWN_CONTROL_S * 1000 for c in inp.events)
                t.takedowns_to_control += followed
    # time-based measures, clipped to the round (control may start before it)
    for e in inp.events:
        if e.type == EventType.ground_control and e.actor is not None:
            tally[e.actor].control_s += _clip(e.start_ms, e.end_ms, lo, hi, iv)
    for r in inp.runs:
        t = tally[FIGHTERS[r.fighter]]
        secs = _clip(r.start_ms, r.end_ms, lo, hi, iv)
        if r.advancing:
            t.advance_s += secs
        else:
            t.retreat_s += secs
    sig = inp.signals
    sample_ms = np.asarray(sig["sample_ms"], dtype=np.float64)
    in_win = (sample_ms >= lo) & (sample_ms < hi)
    if iv:
        in_win &= ~np.array([excl.in_intervals(float(x), iv) for x in sample_ms], dtype=bool)
    for i, f in enumerate(FIGHTERS):
        tally[f].measured_s = float(np.asarray(sig["valid"][i])[in_win].sum()) / inp.sample_hz
    posture = np.asarray(sig["posture"])
    ground = ((posture[0] == GROUNDED) | (posture[1] == GROUNDED)) & in_win
    camera = np.asarray(sig["camera_known"])[in_win]
    if inp.ident_state is not None:
        frames = np.arange(start, min(end + 1, inp.ident_state.shape[0]))
        keep = np.array([not excl.frame_excluded(int(x), inp.exclusions) for x in frames], dtype=bool) \
            if inp.exclusions else np.ones(frames.size, bool)
        for i, f in enumerate(FIGHTERS):
            tally[f].uncertain_s = float((inp.ident_state[frames, i] == 2)[keep].sum()) / inp.fps
    recorded = excl.outside_ms(lo, hi, iv) / 1000
    moments = sorted((e for e in in_round if _weight(e) > 0), key=lambda e: -_weight(e))[:5]
    key = [KeyMoment(event_id=e.event_id, time_s=round((e.peak_ms if e.peak_ms is not None else e.start_ms) / 1000, 2),
                     fighter_id=e.actor, type=e.type, label=_label(e, inp.names), confidence=e.confidence,
                     uncertain=e.confidence < 0.7 or e.type in (EventType.knockdown, EventType.takedown))
           for e in sorted(moments, key=lambda e: e.start_ms)]
    for t in tally.values():
        t.control_s, t.advance_s, t.retreat_s = (round(t.control_s, 2), round(t.advance_s, 2),
                                                 round(t.retreat_s, 2))
    return RoundEvidence(number=number, marked=marked, start_frame=start, end_frame=end, start_ms=lo, end_ms=hi,
                         recorded_s=round(recorded, 2), round_length_s=round_length_s, tally=tally,
                         ground_s=float(ground.sum()) / inp.sample_hz,
                         camera_known_share=float(camera.mean()) if camera.size else 0.0,
                         excluded_s=round((hi - lo) / 1000 - recorded, 2), key_moments=key)


def contract_evidence(f: FighterId, t: Tally) -> FighterRoundEvidence:
    return FighterRoundEvidence(
        fighter_id=f, strike_attempts=t.punches, kick_attempts=t.kicks,
        possible_contact_strikes=t.contact_punches + t.contact_kicks,
        possible_impact_strikes=t.impact_punches + t.impact_kicks, possible_knockdowns=t.knockdowns,
        possible_takedowns=t.takedowns, takedowns_to_control=t.takedowns_to_control, control_s=t.control_s,
        advance_s=t.advance_s, retreat_s=t.retreat_s, measured_s=round(t.measured_s, 1),
        identity_uncertain_s=round(t.uncertain_s, 1), uncertain_events=t.uncertain_majors)


def scorable(ev: RoundEvidence) -> tuple[bool, str | None]:
    low = min(t.measured_s for t in ev.tally.values())
    if ev.recorded_s < MIN_RECORDED_S or low < MIN_MEASURED_S:
        return False, (f"Puanlanmadı: raundun {ev.recorded_s:.0f} sn'si kayıtta ve dövüşçülerden biri yalnızca "
                       f"{low:.0f} sn ölçülebildi (en az {MIN_RECORDED_S:.0f} sn kayıt ve dövüşçü başına "
                       f"{MIN_MEASURED_S:.0f} sn ölçüm gerekir). Veri uydurulmaz.")
    return True, None


def level(value: float) -> ConfidenceLevel:
    lvl = ConfidenceLevel.low if value < 0.3 else ConfidenceLevel.medium if value < 0.6 else ConfidenceLevel.high
    if not VALIDATED and lvl == ConfidenceLevel.high:
        return ConfidenceLevel.medium
    return lvl


def data_confidence(ev: RoundEvidence) -> tuple[float, list[str]]:
    """How much the round's measurements can be trusted (before the judges' decisions)."""
    notes = ["Tespit sistemi bağımsız maç görüntüleriyle doğrulanmadı; güven en fazla 'orta' olabilir."]
    rec = max(ev.recorded_s, 1e-6)
    cov = min(1.0, min(t.measured_s for t in ev.tally.values()) / rec)
    conf = CONFIDENCE_CEILING * (0.35 + 0.65 * cov)
    if cov < 0.6:
        notes.append(f"Dövüşçülerden biri raundun yalnızca %{cov * 100:.0f}'inde ölçülebildi "
                     "(kamera açısı, örtüşme ya da kadraj dışı).")
    unc = sum(t.uncertain_s for t in ev.tally.values()) / 2 / rec
    if unc > 0.1:
        conf *= 1 - 0.5 * min(1.0, unc)
        notes.append(f"Kimlik takibi raundun %{unc * 100:.0f}'inde belirsiz.")
    if ev.partial:
        conf *= 0.5 + 0.5 * min(1.0, ev.recorded_s / ev.round_length_s)
        notes.append(f"Raundun yalnızca {ev.recorded_s:.0f} sn'si kayıtta (raund {ev.round_length_s:.0f} sn).")
    if ev.ground_s > 0.2 * rec:
        conf *= 0.85
        notes.append("Raundun önemli kısmı yerde geçti; yerde üstten vuruşlar büyük ölçüde sayılmıyor.")
    conf *= 0.8 + 0.2 * ev.camera_known_share
    if ev.camera_known_share < 0.6:
        notes.append("Kamera hareketi çoğu yerde kestirilemedi; ilerleme/geri çekilme ölçümleri zayıf.")
    if ev.excluded_s > 0:
        notes.append(f"Raundun {ev.excluded_s:.0f} sn'si dışlandı (tekrar vb.) ve değerlendirilmedi.")
    if not ev.marked:
        notes.append("Raund sınırları işaretlenmedi: tüm video tek raund sayıldı.")
        conf *= 0.8
    return round(min(conf, CONFIDENCE_CEILING), 3), notes


def damage_summary(ev: RoundEvidence, names: dict[FighterId, str]) -> EdgeSummary:
    def ind(t: Tally) -> float:
        return 4 * t.knockdowns + 2 * (t.impact_punches + 1.3 * t.impact_kicks) +             0.3 * (t.contact_punches + 1.3 * t.contact_kicks)

    parts = [f"{names[f]}: {t.knockdowns} olası knockdown, {t.impact_punches + t.impact_kicks} olası etkili vuruş "
             f"(rakibin başı savruldu), {t.contact_punches + t.contact_kicks} olası temaslı vuruş"
             for f, t in ev.tally.items()]
    r, b = ind(ev.tally[FIGHTERS[0]]), ind(ev.tally[FIGHTERS[1]])
    edge = None
    if abs(r - b) >= 2 and abs(r - b) >= 0.3 * (r + b):
        edge = FIGHTERS[0] if r > b else FIGHTERS[1]
    verdict = f"dolaylı göstergelere göre üstünlük {names[edge]} tarafında görünüyor (doğrulanmadı)." if edge \
        else "dolaylı göstergelerde belirgin bir üstünlük yok."
    return EdgeSummary(edge=edge, text="Hasar doğrudan ölçülemiyor. " + "; ".join(parts) + f" — {verdict}")


def grappling_summary(ev: RoundEvidence, names: dict[FighterId, str]) -> EdgeSummary:
    def score(t: Tally) -> float:
        return 2.5 * t.takedowns + 1.0 * t.takedowns_to_control + 0.08 * t.control_s

    parts = [f"{names[f]}: {t.takedowns} olası takedown ({t.takedowns_to_control} kontrole dönüştü), "
             f"{t.control_s:.0f} sn tahmini üst kontrol" for f, t in ev.tally.items()]
    r, b = score(ev.tally[FIGHTERS[0]]), score(ev.tally[FIGHTERS[1]])
    edge = None
    if abs(r - b) >= 1.5:
        edge = FIGHTERS[0] if r > b else FIGHTERS[1]
    verdict = f"üstünlük {names[edge]} tarafında." if edge else "belirgin bir güreş/yer üstünlüğü yok."
    return EdgeSummary(edge=edge, text="; ".join(parts) + f" — {verdict} Submission girişimleri ve pozisyon "
                                                          "geçişleri tespit edilmiyor.")
