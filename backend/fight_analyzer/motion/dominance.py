"""Dominance, duration and the last-resort criteria for any stretch of the bout (v2 Bölüm 3.4).

Computed at request time from the cached analysis (events, 10 Hz signals, the per-frame grappling
states), because the stretch (a round, the whole bout, up to the playback moment) and the excluded
parts can change without processing again. Every measure is a value with its own confidence; none
of them is a score: the judging engine (Bölüm 4) weighs them. Events of uncertain attribution
("Kime ait belirsiz") belong to nobody here, and excluded parts are not fight time.

one_sided_s           time in which the fighter was on offense (an attempt, a takedown or a
                      submission attempt within `offense_before_s`..`offense_after_s`, or active
                      control) while the measured opponent attempted nothing: he only defended.
                      Whether the opponent had an opening cannot be seen in 2D.
offensive_pace        significant strike attempts, takedown and submission attempts
                      (`pace_grappling_weight`) and combinations (`pace_combo_weight`) per measured
                      minute
effective_time_share  share of the fight time in which he imposed effective techniques: active
                      control, one-sided time, and the time around his landed strikes and the damage
                      signals he caused (ABC "duration")
aggressiveness        0..1, steady offensive effort: attempts per minute, combinations started per
                      minute and attacks right after closing the distance, each against a reference
                      rate, weighted (`aggressiveness_weights`)
area_control          0..1, who set the pace, the place and the position: the existing "Baskı"
                      (share of his movement spent advancing) and "İlerleme / geri çekilme", clinch
                      drive (pinning the opponent, presumably against the cage), time on top on the
                      ground and the exchanges he started, weighted over what could be measured
                      (`area_weights`). Holding the octagon centre is not measured (one camera).
Confidences are capped by how much of the stretch was measured and by how many attempts the
detector misses (`detection_confidence`).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np

from fight_analyzer.config import FeatureSettings, MotionSettings
from fight_analyzer.contracts import EventType, ExcludedSegment, FighterId, FightEvent, StrikeOutcome

from . import grappling as grappling_mod
from .series import window_mask

FIGHTERS = (FighterId.fighter_a, FighterId.fighter_b)
STRIKES = frozenset({EventType.punch, EventType.kick, EventType.knee, EventType.elbow, EventType.ground_strike})
TAKEDOWNS = frozenset({EventType.takedown, EventType.takedown_attempt})
OFFENSE = STRIKES | TAKEDOWNS | {EventType.submission_attempt, EventType.reversal}
ADVANCING, RETREATING = 0, 1  # MotionSettings movement codes (events.py)
NOT_MEASURED = ("center_control",)
AREA_COMPONENTS = ("pressure", "advance", "clinch_drive", "top_position", "exchanges_started")


@dataclass
class Scored:
    value: float | None  # None: not measurable in the stretch
    confidence: float  # 0..1


@dataclass
class FighterDominance:
    one_sided_s: Scored
    offensive_pace: Scored
    effective_time_share: Scored
    aggressiveness: Scored
    area_control: Scored
    components: dict[str, float] = field(default_factory=dict)  # what the scores are made of
    not_measured: tuple[str, ...] = NOT_MEASURED


def _clip01(x: float) -> float:
    return min(1.0, max(0.0, x))


def _moment(e: FightEvent) -> int:
    return e.peak_frame if e.peak_frame is not None else e.start_frame


def _excluded_frames(segments: Sequence[ExcludedSegment], first: int, last: int) -> np.ndarray:
    out = np.zeros(last - first + 1, bool)
    for x in segments:
        a, b = max(first, x.start_frame), min(last, x.end_frame)
        if a <= b:
            out[a - first:b - first + 1] = True
    return out


def _sample_values(values: np.ndarray, t_s: np.ndarray, hz: float) -> np.ndarray:
    """The 10 Hz sample covering each time (the last sample past the end)."""
    k = np.clip(np.floor(t_s * hz + 1e-9).astype(np.int64), 0, max(0, values.shape[-1] - 1))
    return values[..., k]


def combinations(moments: np.ndarray, gap_s: float) -> int:
    """Runs of at least two strike attempts with less than gap_s between neighbours."""
    if moments.size < 2:
        return 0
    m = np.sort(moments)
    close = np.diff(m) <= gap_s
    starts = close & np.concatenate(([True], ~close[:-1]))
    return int(starts.sum())


def measure(events: Sequence[FightEvent], frames: dict[str, np.ndarray], signals: dict[str, np.ndarray],
            sample_hz: float, first: int, last: int, segments: Sequence[ExcludedSegment], fps: float,
            f: FeatureSettings, ms: MotionSettings) -> tuple[FighterDominance, FighterDominance]:
    """The 3.4 measures of both fighters over frames first..last (inclusive)."""
    n = max(0, last - first + 1)
    t = (np.arange(first, first + n) / fps).astype(np.float64)  # seconds of video time
    step = 1.0 / fps
    live = ~_excluded_frames(segments, first, last) if n else np.zeros(0, bool)
    valid = _sample_values(np.asarray(signals["valid"], bool), t, sample_hz) if n else np.zeros((2, 0), bool)
    state = (np.asarray(frames["grappling"])[first:last + 1] if "grappling" in frames
             else np.full(n, grappling_mod.UNKNOWN, np.int8))
    clinch_by = np.asarray(frames["clinch_by"])[first:last + 1] if "clinch_by" in frames else np.full(n, -1, np.int8)
    if state.size < n:  # analysis shorter than the stretch (should not happen): pad as unknown
        state = np.concatenate([state, np.full(n - state.size, grappling_mod.UNKNOWN, np.int8)])
        clinch_by = np.concatenate([clinch_by, np.full(n - clinch_by.size, -1, np.int8)])

    def mine(i: int, types: frozenset[EventType]) -> list[FightEvent]:
        return [e for e in events if e.actor == FIGHTERS[i] and e.type in types and not e.attribution_uncertain
                and first <= _moment(e) <= last and live[_moment(e) - first]]

    def secs_of(frame: int) -> float:
        return frame / fps

    offense = np.zeros((2, n), bool)
    strike_moments, holds = [], []
    for i in (0, 1):
        moments = np.array([secs_of(_moment(e)) for e in mine(i, OFFENSE - {EventType.submission_attempt})])
        offense[i] = window_mask(t, moments, f.offense_before_s, f.offense_after_s)
        spans = [(secs_of(e.start_frame), secs_of(e.end_frame)) for e in mine(i, frozenset({EventType.submission_attempt}))]
        for a, b in spans:
            offense[i] |= (t >= a - f.offense_before_s) & (t <= b + f.offense_after_s)
        strike_moments.append(np.array([secs_of(_moment(e)) for e in mine(i, STRIKES)]))
        holds.append(spans)
    active = grappling_mod.active_control(state, clinch_by, t, strike_moments, holds, ms) & live
    both = valid[0] & valid[1] & live
    fight_s = float(live.sum()) * step
    out = []
    exchanges = _exchanges([mine(i, STRIKES | TAKEDOWNS) for i in (0, 1)], f.exchange_gap_s, fps)
    for i in (0, 1):
        j = 1 - i
        measured_s = float((valid[i] & live).sum()) * step
        minutes = measured_s / 60.0
        both_share = float(both.sum()) / max(1, int(live.sum()))
        rate_conf = f.detection_confidence * _clip01(minutes / 1.0)
        # one-sided: on offense (or active control) while the measured opponent attempts nothing
        one_sided = both & (offense[i] | active[i]) & ~offense[j]
        one_sided_s = float(one_sided.sum()) * step
        time_conf = round(f.detection_confidence * _clip01(both_share / 0.8), 3) if fight_s > 0 else 0.0
        # offensive pace
        strikes = mine(i, STRIKES)
        significant = sum(bool(e.significant) for e in strikes)
        grappling = len(mine(i, TAKEDOWNS)) + len(mine(i, frozenset({EventType.submission_attempt})))
        combos = combinations(np.array([secs_of(_moment(e)) for e in strikes]), f.combo_gap_s)
        pace = (significant + f.pace_grappling_weight * grappling + f.pace_combo_weight * combos) / minutes \
            if minutes >= 0.25 else None
        # effective time: active control, one-sided time, landed strikes and the damage he caused
        landed = np.array([secs_of(_moment(e)) for e in strikes if e.outcome == StrikeOutcome.landed])
        effective = active[i] | one_sided | (window_mask(t, landed, f.landed_before_s, f.landed_after_s) & live)
        share = float(effective.sum()) / max(1, int(live.sum())) if fight_s > 0 else None
        # aggressiveness: steady offensive effort
        attempts = len(strikes) + len(mine(i, TAKEDOWNS))
        movement = _sample_values(np.asarray(signals["movement"])[i], t, sample_hz) if n else np.zeros(0)
        closing = 0
        for e in strikes + mine(i, TAKEDOWNS):
            k = _moment(e) - first
            lo = max(0, k - int(round(f.close_attempt_s * fps)))
            if (movement[lo:k + 1] == ADVANCING).any():
                closing += 1
        if minutes >= 0.25:
            parts = (_clip01(attempts / minutes / f.aggressiveness_attempt_ref),
                     _clip01(combos / minutes / f.aggressiveness_combo_ref),
                     _clip01(closing / minutes / f.aggressiveness_close_ref))
            w = np.asarray(f.aggressiveness_weights, float)
            aggressiveness = float(np.dot(parts, w) / max(w.sum(), 1e-9))
        else:
            parts, aggressiveness = (0.0, 0.0, 0.0), None
        # area control
        comp = _area(i, movement, live, state, clinch_by, exchanges, fps)
        weights = dict(zip(AREA_COMPONENTS, f.area_weights))
        present = [c for c in AREA_COMPONENTS if c in comp]
        wsum = sum(weights[c] for c in present)
        area_value = sum(weights[c] * comp[c] for c in present) / wsum if wsum > 0 else None
        area_conf = round(min(f.area_max_confidence, f.area_max_confidence * wsum / max(sum(weights.values()), 1e-9)
                              * _clip01(both_share / 0.8)), 3) if area_value is not None else 0.0
        components = {"offense_s": round(float((offense[i] & live).sum()) * step, 2),
                      "active_control_s": round(float(active[i].sum()) * step, 2),
                      "significant_attempts": float(significant), "grappling_attempts": float(grappling),
                      "combinations": float(combos), "attempts_per_min": round(attempts / minutes, 2) if minutes else 0.0,
                      "closing_attacks": float(closing), "measured_s": round(measured_s, 2),
                      **{f"area_{k}": round(v, 3) for k, v in comp.items()},
                      **{f"aggr_{k}": round(v, 3) for k, v in zip(("attempts", "combinations", "closing"), parts)}}
        out.append(FighterDominance(
            one_sided_s=Scored(round(one_sided_s, 2) if fight_s > 0 else None, time_conf),
            offensive_pace=Scored(None if pace is None else round(pace, 2), round(rate_conf, 3) if pace is not None else 0.0),
            effective_time_share=Scored(None if share is None else round(share, 3), time_conf),
            aggressiveness=Scored(None if aggressiveness is None else round(aggressiveness, 3),
                                  round(rate_conf, 3) if aggressiveness is not None else 0.0),
            area_control=Scored(None if area_value is None else round(area_value, 3), area_conf),
            components=components))
    return out[0], out[1]


def _exchanges(attempts: list[list[FightEvent]], gap_s: float, fps: float) -> list[int]:
    """Who opened each exchange: an attempt with no attempt of either fighter in the gap_s before."""
    moments = sorted((_moment(e) / fps, i) for i in (0, 1) for e in attempts[i])
    out, last = [], None
    for at, i in moments:
        if last is None or at - last > gap_s:
            out.append(i)
        last = at
    return out


def _area(i: int, movement: np.ndarray, live: np.ndarray, state: np.ndarray, clinch_by: np.ndarray,
          exchanges: list[int], fps: float) -> dict[str, float]:
    """Components of area control that could be measured in the stretch (0..1 each, his share)."""
    comp: dict[str, float] = {}
    known = (movement >= 0) & live
    if known.sum() / fps >= 3.0:  # as the side panels: fewer seconds are noise
        adv = int(((movement == ADVANCING) & live).sum())
        ret = int(((movement == RETREATING) & live).sum())
        comp["pressure"] = adv / int(known.sum())
        if adv + ret > 0:
            comp["advance"] = adv / (adv + ret)
    in_clinch = (state == grappling_mod.CLINCH) & live
    if in_clinch.sum() / fps >= 1.0:
        driven = in_clinch & (clinch_by >= 0)
        if driven.any():
            comp["clinch_drive"] = float((in_clinch & (clinch_by == i)).sum()) / float(driven.sum())
    tops = np.isin(state, grappling_mod.TOP) & live
    if tops.sum() / fps >= 1.0:
        comp["top_position"] = float(((state == grappling_mod.TOP[i]) & live).sum()) / float(tops.sum())
    if len(exchanges) >= 2:
        comp["exchanges_started"] = exchanges.count(i) / len(exchanges)
    return comp
