"""Damage signals: signs that a fighter's ability or will to fight was reduced.

They follow the ABC definition of damage (2025 judging criteria) and are
estimates from 2D joints, each with a severity and its own confidence:

knockdown          a possible knockdown event (events.py): down after a strike
heavy_head_strike  a landed head strike with a strong head snap
wobble             loss of balance right after a landed strike, while he throws
                   nothing himself: the hips dip and come back, the stance width
                   jumps, several quick steps, a glove at floor level. A deep dip
                   with one more sign, or a glove on the floor alone (footwork
                   alone is not a wobble).
forced_retreat     after a landed strike the fighter only backs off for the
                   next seconds and throws nothing himself

output_drop        cumulative: after enough damage inside a round the fighter's
                   pace and mobility stay lower for the rest of the round. It
                   needs the rounds and the excluded parts, which the user can
                   edit without processing again, so it is derived from the
                   cached events at request time (`with_output_drop`).

submission_danger comes with the grappling states, visible_injury is only ever
a flag set by the user.

Nothing here scores anything: the signals are inputs of the judging engine.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from fight_analyzer.config import FeatureSettings, MotionSettings
from fight_analyzer.contracts import (
    DamageKind,
    DamageSignal,
    DamageType,
    DataOrigin,
    EventType,
    EvidenceSignal,
    ExcludedSegment,
    FighterId,
    FightEvent,
    StrikeOutcome,
    TargetZone,
)

from . import exclusions as excl
from .kinematics import GROUNDED, LA, LW, RA, RW, FighterKinematics, hip_height
from .strikes import Assessment

FIGHTERS = (FighterId.fighter_a, FighterId.fighter_b)
SHORT = ("a", "b")
STRIKES = frozenset({EventType.punch, EventType.kick, EventType.knee, EventType.elbow, EventType.ground_strike})


def _clip01(x: float) -> float:
    return min(1.0, max(0.0, x))


def _signal(type_: DamageType, frame: int, ts_ms: np.ndarray, target: int, severity: float, confidence: float,
            source: FightEvent | None, evidence: Sequence[EvidenceSignal], measures: dict[str, float],
            end_ms: float | None = None, note: str | None = None) -> DamageSignal:
    return DamageSignal(
        signal_id=f"{type_.value}-{SHORT[target]}-{frame}", type=type_, kind=DamageKind.immediate, frame=int(frame),
        time_ms=round(float(ts_ms[frame]), 1), end_ms=None if end_ms is None else round(end_ms, 1),
        target_fighter=FIGHTERS[target], by_fighter=FIGHTERS[1 - target], severity=round(_clip01(severity), 3),
        confidence=round(_clip01(confidence), 3),
        attribution_confidence=source.attribution_confidence if source else None,
        attribution_uncertain=source.attribution_uncertain if source else False,
        linked_event_id=source.event_id if source else None, evidence=list(evidence), measures=measures,
        data_origin=DataOrigin.measured, note=note)


def _wobble(k: FighterKinematics, ts: np.ndarray, at: int, s: MotionSettings
            ) -> tuple[list[EvidenceSignal], dict[str, float]] | None:
    """Signs of lost balance in the window after frame `at` (None: not measurable or none)."""
    hi = int(np.searchsorted(ts, ts[at] + s.wobble_window_s, side="right"))
    ref = int(np.searchsorted(ts, ts[at] - s.wobble_base_s))
    if hi - at < 4:
        return None
    signs: list[EvidenceSignal] = []
    measures: dict[str, float] = {}
    height = hip_height(k)
    before, after = height[ref:at + 1], height[at + 1:hi]
    if np.isfinite(before).any() and np.isfinite(after).sum() >= 3:
        standing = float(np.nanmedian(before))
        tail = after[-max(2, after.size // 4):]
        if standing >= 0.8 * s.fall_upright and np.isfinite(tail).any():
            dip = (standing - float(np.nanmin(after))) / standing
            came_back = float(np.nanmedian(tail)) >= 0.9 * standing
            # a deeper dip that lasts is a fall (and then no wobble is claimed); a brief one counts
            if s.wobble_dip <= dip < 0.6 and came_back:
                signs.append(EvidenceSignal.knee_buckle)
                measures["dip"] = round(dip, 3)
    with np.errstate(all="ignore"):
        width = np.linalg.norm(k.pos[:, LA] - k.pos[:, RA], axis=1) / k.scale
    change = 0.0
    for t in range(at + 1, hi):
        earlier = int(np.searchsorted(ts, ts[t] - s.wobble_base_s))
        if np.isfinite(width[t]) and np.isfinite(width[earlier]):
            change = max(change, abs(float(width[t] - width[earlier])))
    if change >= s.wobble_base_change:
        signs.append(EvidenceSignal.base_change)
        measures["base_change"] = round(change, 3)
    steps = 0
    body = k.ref_vel()
    for ankle in (LA, RA):
        with np.errstate(all="ignore"):
            speed = np.linalg.norm(k.vel[at + 1:hi, ankle] - body[at + 1:hi], axis=1) / k.scale[at + 1:hi]
        fast = np.isfinite(speed) & (speed >= s.strike_low)
        steps += int((fast[1:] & ~fast[:-1]).sum()) + int(fast[0]) if fast.size else 0
    if steps >= s.wobble_steps:
        signs.append(EvidenceSignal.unsteady_steps)
        measures["steps"] = float(steps)
    # a glove at floor level while still on his feet (the floor: the lower foot)
    floor = np.fmax(k.pos[at + 1:hi, LA, 1], k.pos[at + 1:hi, RA, 1])
    with np.errstate(all="ignore"):
        level = floor - 0.2 * k.scale[at + 1:hi]
        on_feet = (k.posture[at + 1:hi] != GROUNDED) & (height[at + 1:hi] >= 0.5)
        hands = k.pos[at + 1:hi, [LW, RW], 1]
        touching = np.isfinite(level)[:, None] & np.isfinite(hands) & (hands >= level[:, None]) & on_feet[:, None]
    if touching.any():
        signs.append(EvidenceSignal.hand_on_floor)
    # Footwork alone (a step that changes the stance, quick steps) is not a loss of balance:
    # a dip of the hips or a glove on the floor is needed, the glove is enough on its own.
    if EvidenceSignal.hand_on_floor in signs:
        return signs, measures
    if EvidenceSignal.knee_buckle in signs and len(signs) >= 2:
        return signs, measures
    return None


def _retreat(approach: np.ndarray, ts: np.ndarray, at: int, own_strikes: np.ndarray, s: MotionSettings
             ) -> tuple[int, dict[str, float]] | None:
    """The fighter only backs off after frame `at`: (last frame, measures) or None."""
    hi = int(np.searchsorted(ts, ts[at] + s.retreat_window_s, side="right"))
    window = approach[at + 1:hi]
    if window.size < 5 or ts[hi - 1] - ts[at] < 0.8 * s.retreat_window_s:
        return None
    ok = np.isfinite(window)
    if ok.mean() < s.retreat_measured_share:
        return None
    away = window[ok] <= -s.advance_speed
    share = float(away.mean())
    if share < s.retreat_share or ((own_strikes > at) & (own_strikes < hi)).any():
        return None
    return hi - 1, {"retreat_share": round(share, 3), "retreat_speed": round(float(-window[ok][away].mean()), 3)}


def detect(ts_ms: np.ndarray, kin: tuple[FighterKinematics, FighterKinematics], approach: np.ndarray,
           strikes: Sequence[tuple[FightEvent, Assessment, int]], events: Sequence[FightEvent],
           s: MotionSettings) -> list[DamageSignal]:
    """Damage signals from the events (after their attribution is set) and the fighters' motion.
    `strikes` are the strike events with their assessment and the actor's index."""
    ts = ts_ms / 1000.0
    out: list[DamageSignal] = []
    downs: list[list[int]] = [[], []]  # frames at which a fighter went down
    for e in events:
        if e.type == EventType.knockdown and e.target is not None:
            target = FIGHTERS.index(e.target)
            frame = e.peak_frame if e.peak_frame is not None else e.start_frame
            downs[target].append(e.start_frame)
            long_down = e.measures.get("down_s", 0.0) >= s.knockdown_long_s
            out.append(_signal(DamageType.knockdown, frame, ts_ms, target, 0.8 + 0.2 * long_down, e.confidence, e,
                               e.evidence, {k: v for k, v in e.measures.items() if k in ("fall_s", "down_s")},
                               note=e.note))
    attempts = [np.array(sorted(e.peak_frame if e.peak_frame is not None else e.start_frame
                                for e in events if e.type in STRIKES and e.actor == f), dtype=np.int64)
                for f in FIGHTERS]
    busy_until = {DamageType.wobble: [-1, -1], DamageType.forced_retreat: [-1, -1]}
    for e, result, actor in sorted(strikes, key=lambda x: x[1].contact_frame or 0):
        # Only after a landed strike: on the sample broadcast, signs that followed mere contact were
        # all ordinary movement after an exchange (a tuning set, see NOTES.md).
        if result.outcome != StrikeOutcome.landed or result.contact_frame is None:
            continue
        target, at = 1 - actor, result.contact_frame
        heavy = result.zone == TargetZone.head and (result.reaction or 0.0) >= s.heavy_head_snap
        if heavy:
            snap = float(result.reaction)
            out.append(_signal(DamageType.heavy_head_strike, at, ts_ms, target,
                               0.5 + 0.5 * (snap - s.heavy_head_snap) / s.heavy_head_snap, result.confidence or 0.5, e,
                               [EvidenceSignal.zone_contact, EvidenceSignal.head_snap], {"head_snap": round(snap, 3)}))
        end = int(np.searchsorted(ts, ts[at] + s.wobble_window_s, side="right"))
        went_down = any(at <= f <= end for f in downs[target])
        # his own strikes bend the knees and change the stance too: not a loss of balance
        throwing = bool(((attempts[target] > at) & (attempts[target] < end)).any())
        if not went_down and not throwing and at > busy_until[DamageType.wobble][target]:
            found = _wobble(kin[target], ts, at, s)
            if found is not None:
                signs, measures = found
                hand = EvidenceSignal.hand_on_floor in signs
                out.append(_signal(DamageType.wobble, at, ts_ms, target,
                                   min(0.8, 0.3 + 0.15 * len(signs) + measures.get("dip", 0.0)),
                                   min(0.55, 0.25 + 0.1 * len(signs) + 0.1 * hand), e, [*signs, EvidenceSignal.no_offense],
                                   measures, end_ms=float(ts_ms[end - 1])))
                busy_until[DamageType.wobble][target] = end - 1
        if not went_down and at > busy_until[DamageType.forced_retreat][target]:
            found = _retreat(approach[target], ts, at, attempts[target], s)
            if found is not None:
                last, measures = found
                out.append(_signal(DamageType.forced_retreat, at, ts_ms, target,
                                   min(0.7, 0.3 + 0.2 * _clip01(measures["retreat_speed"] / 2) + 0.1 * heavy),
                                   min(0.5, 0.3 + 0.2 * _clip01((measures["retreat_share"] - s.retreat_share)
                                                                / max(1e-6, 1 - s.retreat_share))),
                                   e, [EvidenceSignal.retreat, EvidenceSignal.no_offense], measures,
                                   end_ms=float(ts_ms[last])))
                busy_until[DamageType.forced_retreat][target] = last
    out.sort(key=lambda d: (d.time_ms, d.signal_id))
    seen: dict[str, int] = {}
    for d in out:
        seen[d.signal_id] = seen.get(d.signal_id, 0) + 1
        if seen[d.signal_id] > 1:
            d.signal_id = f"{d.signal_id}-{seen[d.signal_id]}"
    return out


HEAVY = frozenset({DamageType.knockdown, DamageType.heavy_head_strike, DamageType.wobble})
Window = tuple[int, int, int]  # (round number, first frame, last frame)


def output_drop(events: Sequence[FightEvent], damage: Sequence[DamageSignal], signals: dict[str, np.ndarray],
                sample_hz: float, windows: Sequence[Window], segments: Sequence[ExcludedSegment], fps: float,
                f: FeatureSettings) -> list[DamageSignal]:
    """Cumulative damage inside each round: once a fighter has taken `output_drop_landed`
    landed significant strikes, or one knockdown / heavy head strike / wobble, his pace
    (attempts per measured minute) and mobility (mean hand and foot activity) over the rest of
    the round are compared with the part of the round before. Both must drop. Excluded parts
    are not fight time and events of uncertain attribution are left out. Low confidence:
    fatigue and tactics lower the output too."""
    iv = excl.intervals(segments, fps)
    sample_ms = np.asarray(signals["sample_ms"], dtype=np.float64)
    valid = np.asarray(signals["valid"], dtype=bool)
    activity = np.asarray(signals["activity"], dtype=np.float64)
    live = np.array([not excl.in_intervals(float(t), iv) for t in sample_ms], dtype=bool)

    def counted(e: FightEvent) -> bool:
        return not e.attribution_uncertain and not excl.frame_excluded(excl.event_frame(e), segments)

    def moment(e: FightEvent) -> float:
        return e.peak_ms if e.peak_ms is not None else e.start_ms

    out: list[DamageSignal] = []
    for number, first, last in windows:
        lo, hi = first * 1000 / fps, (last + 1) * 1000 / fps
        for x in (0, 1):
            opp = 1 - x
            landed = sorted((moment(e), e.event_id) for e in events
                            if e.actor == FIGHTERS[opp] and e.type in STRIKES and e.outcome == StrikeOutcome.landed
                            and e.significant and counted(e) and lo <= moment(e) < hi)
            heavy = sorted((d.time_ms, d.signal_id) for d in damage
                           if d.target_fighter == FIGHTERS[x] and d.type in HEAVY and not d.attribution_uncertain
                           and not excl.frame_excluded(d.frame, segments) and lo <= d.time_ms < hi)
            starts = ([landed[f.output_drop_landed - 1]] if len(landed) >= f.output_drop_landed else []) + heavy[:1]
            if not starts:
                continue
            at, cause = min(starts)
            before = valid[x] & live & (sample_ms >= lo) & (sample_ms < at)
            after = valid[x] & live & (sample_ms >= at) & (sample_ms < hi)
            before_s, after_s = before.sum() / sample_hz, after.sum() / sample_hz
            if min(before_s, after_s) < f.output_drop_min_s:
                continue
            own = [moment(e) for e in events if e.actor == FIGHTERS[x] and e.type in STRIKES and counted(e)]
            pace_before = sum(lo <= t < at for t in own) / (before_s / 60)
            pace_after = sum(at <= t < hi for t in own) / (after_s / 60)
            act_b, act_a = activity[x][before], activity[x][after]
            if pace_before <= 0 or not np.isfinite(act_b).any() or not np.isfinite(act_a).any():
                continue
            mob_before, mob_after = float(np.nanmean(act_b)), float(np.nanmean(act_a))
            if mob_before <= 0:
                continue
            pace_drop, mob_drop = 1 - pace_after / pace_before, 1 - mob_after / mob_before
            if pace_drop < f.output_drop_pace or mob_drop < f.output_drop_mobility:
                continue
            frame = min(last, max(first, int(round(at * fps / 1000))))
            mean_drop = (pace_drop + mob_drop) / 2
            out.append(DamageSignal(
                signal_id=f"output_drop-{SHORT[x]}-r{number}", type=DamageType.output_drop, kind=DamageKind.cumulative,
                frame=frame, time_ms=round(at, 1), end_ms=round(hi, 1), target_fighter=FIGHTERS[x],
                by_fighter=FIGHTERS[opp], severity=round(_clip01(0.3 + 0.5 * mean_drop), 3),
                confidence=round(min(f.output_drop_max_confidence,
                                     0.2 + 0.1 * _clip01(min(before_s, after_s) / 120) + 0.1 * _clip01(mean_drop)), 3),
                linked_event_id=cause, evidence=[EvidenceSignal.pace_drop, EvidenceSignal.mobility_drop],
                measures={"pace_before": round(pace_before, 2), "pace_after": round(pace_after, 2),
                          "mobility_before": round(mob_before, 3), "mobility_after": round(mob_after, 3),
                          "measured_before_s": round(float(before_s), 1), "measured_after_s": round(float(after_s), 1),
                          "round": float(number)},
                data_origin=DataOrigin.measured))
    return out


def with_output_drop(events: Sequence[FightEvent], damage: Sequence[DamageSignal], signals: dict[str, np.ndarray],
                     sample_hz: float, windows: Sequence[Window], segments: Sequence[ExcludedSegment], fps: float,
                     f: FeatureSettings) -> list[DamageSignal]:
    """The cached damage signals and the output drops for these rounds, in time order."""
    found = output_drop(events, damage, signals, sample_hz, windows, segments, fps, f)
    return sorted([*damage, *found], key=lambda d: (d.time_ms, d.signal_id))
