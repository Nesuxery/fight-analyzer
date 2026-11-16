"""What a strike attempt did: target zone and outcome, from 2D joints.

Target zone
    The striking surface (the fist a little beyond the wrist, the foot and
    shin, the knee, the elbow) is followed from just before the fastest moment
    until the limb has had time to arrive. The opponent's zones are a circle
    around his head, a band around the line from mid-shoulders to mid-hips, and
    bands around his thighs and shins; his guard is the forearms and gloves.
    The zone the limb came closest to is the target.
    Punches and elbows aim at the head or the body only.
Outcome
    landed   the limb reached the zone in 2D and the opponent reacted right
             after: his head was thrown along the strike against his
             shoulders, his torso was pushed along the strike, or the struck
             leg was displaced (clear reactions only: fighters move all the
             time, and a slipping head moves too)
    blocked  the limb met the guard and there was no such reaction
    missed   the limb came near no zone and not near the guard
    unknown  the opponent could not be measured, the limb overlapped the zone
             in 2D without a clear reaction (depth is not visible: it may have
             passed in front, grazed, or landed lightly), or it came close
             without reaching anything
Reaching a zone in 2D is never proof on its own; "unknown" is not "missed".
Every outcome but "unknown" carries its own confidence. All sizes are torso
lengths of the opponent; the thresholds are starting values (MotionSettings).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from fight_analyzer.config import MotionSettings
from fight_analyzer.contracts import EventType, EvidenceSignal, StrikeOutcome, TargetZone

from .kinematics import LA, LE, LH, LK, LS, LW, RA, RE, RH, RK, RS, RW, FighterKinematics

HEAD = (0, 1, 2, 3, 4)  # nose, eyes, ears
LEG_SEGMENTS = ((LH, LK), (LK, LA), (RH, RK), (RK, RA))  # thighs and shins
FOREARMS = ((LE, LW), (RE, RW))
ARM_STRIKES = (EventType.punch, EventType.ground_strike)
REACTION = {TargetZone.head: EvidenceSignal.head_snap, TargetZone.body: EvidenceSignal.body_push,
            TargetZone.leg: EvidenceSignal.leg_buckle}


@dataclass
class Assessment:
    zone: TargetZone | None = None
    outcome: StrikeOutcome = StrikeOutcome.unknown
    confidence: float | None = None
    evidence: list[EvidenceSignal] = field(default_factory=list)
    contact_frame: int | None = None  # where the limb was closest to the zone
    reaction: float | None = None  # size of the zone's reaction (None: not measurable)
    measures: dict[str, float] = field(default_factory=dict)


def _unit(v: np.ndarray) -> np.ndarray | None:
    n = float(np.linalg.norm(v))
    return v / n if math.isfinite(n) and n > 1e-9 else None


def _segment_distance(p: np.ndarray, a: np.ndarray, b: np.ndarray) -> float:
    ab = b - a
    d = float(ab @ ab)
    if d <= 1e-12:
        return float(np.linalg.norm(p - a))
    u = min(1.0, max(0.0, float((p - a) @ ab) / d))
    return float(np.linalg.norm(p - (a + u * ab)))


def striking_points(k: FighterKinematics, t: int, kind: EventType, joint: int, s: MotionSettings) -> list[np.ndarray]:
    """The striking surface of the attacker at frame t (stabilized pixels)."""
    if not k.ok[t, joint]:
        return []
    p = k.pos[t, joint]
    reach = s.fist_reach * k.scale[t]
    if kind in ARM_STRIKES:
        elbow = LE if joint == LW else RE
        u = _unit(p - k.pos[t, elbow]) if k.ok[t, elbow] else None
        return [p + reach * u] if u is not None else [p]
    if kind == EventType.kick:
        knee = LK if joint == LA else RK
        if k.ok[t, knee]:
            shin = p - k.pos[t, knee]
            u = _unit(shin)
            if u is not None:
                return [p + reach * u, p, p - 0.5 * shin]  # foot, ankle, middle of the shin
    return [p]


def head_centre(k: FighterKinematics, t: int) -> tuple[np.ndarray | None, bool]:
    """Centre of the head, and whether it had to be estimated from the shoulders."""
    ok = k.ok[t, list(HEAD)]
    if ok.any():
        return k.pos[t, list(HEAD)][ok].mean(axis=0), False
    if k.ok[t, [LS, RS, LH, RH]].all():
        sh, hip = (k.pos[t, LS] + k.pos[t, RS]) / 2, (k.pos[t, LH] + k.pos[t, RH]) / 2
        up = _unit(sh - hip)
        if up is not None:
            return sh + 0.4 * k.scale[t] * up, True
    return None, True


ALL_ZONES = frozenset(TargetZone)
UPPER_ZONES = frozenset({TargetZone.head, TargetZone.body})  # punches and elbows do not go to the legs


def zones_for(kind: EventType) -> frozenset[TargetZone]:
    return ALL_ZONES if kind in (EventType.kick, EventType.knee) else UPPER_ZONES


def zone_gaps(opp: FighterKinematics, t: int, points: list[np.ndarray], s: MotionSettings,
              zones: frozenset[TargetZone] = ALL_ZONES) -> tuple[dict[TargetZone, float], float | None, bool] | None:
    """Distance of the striking surface to each measurable zone (of `zones`) and to the guard,
    beyond their radius (<= 0: inside), in the opponent's torso lengths; and whether the head
    position was estimated. None when nothing can be measured."""
    scale = float(opp.scale[t])
    if not points or not opp.present[t] or not math.isfinite(scale) or scale <= 0:
        return None
    pos, ok = opp.pos[t], opp.ok[t]
    gaps: dict[TargetZone, float] = {}
    head, estimated = head_centre(opp, t)
    if head is not None and TargetZone.head in zones:
        gaps[TargetZone.head] = min(float(np.linalg.norm(p - head)) for p in points) / scale - s.head_radius
    if ok[[LS, RS, LH, RH]].all() and TargetZone.body in zones:
        sh, hip = (pos[LS] + pos[RS]) / 2, (pos[LH] + pos[RH]) / 2
        gaps[TargetZone.body] = min(_segment_distance(p, sh, hip) for p in points) / scale - s.body_radius
    legs = [min(_segment_distance(p, pos[a], pos[b]) for p in points) for a, b in LEG_SEGMENTS if ok[a] and ok[b]]
    if legs and TargetZone.leg in zones:
        gaps[TargetZone.leg] = min(legs) / scale - s.leg_radius
    guard: list[float] = []
    for elbow, wrist in FOREARMS:
        if not ok[wrist]:
            continue
        glove = pos[wrist]
        if ok[elbow]:
            u = _unit(pos[wrist] - pos[elbow])
            glove = pos[wrist] + s.fist_reach * scale * u if u is not None else glove
            guard.append(min(_segment_distance(p, pos[elbow], glove) for p in points))
        else:
            guard.append(min(float(np.linalg.norm(p - glove)) for p in points))
    return gaps, (min(guard) / scale - s.guard_radius if guard else None), estimated


def _window(ts: np.ndarray, t: int, before_s: float, after_s: float) -> tuple[int, int]:
    return int(np.searchsorted(ts, ts[t] - before_s)), int(np.searchsorted(ts, ts[t] + after_s, side="right"))


def _jolt(rel: np.ndarray, k: int) -> float | None:
    """How far a point moved after index k beyond how far it moved before (rows are times;
    None when it is not measured on both sides)."""
    ok = np.isfinite(rel).all(axis=1)
    before = np.flatnonzero(ok[:k + 1])
    after = np.flatnonzero(ok[k + 1:]) + k + 1
    if before.size == 0 or after.size == 0:
        return None
    jolt = float(np.linalg.norm(rel[after] - rel[before[-1]], axis=1).max())
    base = float(np.linalg.norm(rel[before] - rel[before[0]], axis=1).max()) if before.size > 1 else 0.0
    return max(0.0, jolt - base)


def _scale(opp: FighterKinematics, lo: int, hi: int) -> float | None:
    values = opp.scale[lo:hi]
    if not np.isfinite(values).any():
        return None
    scale = float(np.nanmedian(values))
    return scale if scale > 0 else None


def _jolt_along(rel: np.ndarray, k: int, u: np.ndarray) -> float | None:
    """`_jolt` counted only along the unit direction u: how far the point was thrown that way."""
    ok = np.isfinite(rel).all(axis=1)
    before = np.flatnonzero(ok[:k + 1])
    after = np.flatnonzero(ok[k + 1:]) + k + 1
    if before.size == 0 or after.size == 0:
        return None
    jolt = float(((rel[after] - rel[before[-1]]) @ u).max())
    base = float(np.abs((rel[before] - rel[before[0]]) @ u).max()) if before.size > 1 else 0.0
    return max(0.0, jolt - base)


def head_snap(opp: FighterKinematics, ts: np.ndarray, t: int, s: MotionSettings,
              direction: np.ndarray | None = None) -> float | None:
    """Movement of the opponent's head against his shoulders right after frame t, beyond his
    movement just before (median over the measured head points). With the strike's direction,
    only the movement that way counts: a head slipping sideways or down is not snapped back."""
    lo, hi = _window(ts, t, s.impact_window_s, s.impact_window_s)
    scale = _scale(opp, lo, hi)
    if scale is None:
        return None
    anchor = opp.mid(LS, RS)[lo:hi]
    rel = [(opp.pos[lo:hi, p] - anchor) / scale for p in HEAD]
    values = [j for j in ((_jolt_along(r, t - lo, direction) if direction is not None else _jolt(r, t - lo))
                          for r in rel) if j is not None]
    return float(np.median(values)) if values else None


def body_push(opp: FighterKinematics, ts: np.ndarray, t: int, direction: np.ndarray | None,
              s: MotionSettings) -> float | None:
    """Change of the opponent's torso velocity right after frame t along the strike
    (torso lengths per second; without a direction, the size of the change)."""
    lo, hi = _window(ts, t, s.impact_window_s, s.impact_window_s)
    scale = _scale(opp, lo, hi)
    if scale is None:
        return None
    vel = opp.ref_vel()[lo:hi]
    k = t - lo
    before, after = vel[:k + 1], vel[k + 1:]
    if not np.isfinite(before).all(axis=1).any() or not np.isfinite(after).all(axis=1).any():
        return None
    change = (np.nanmean(after, axis=0) - np.nanmean(before, axis=0)) / scale
    return max(0.0, float(change @ direction)) if direction is not None else float(np.linalg.norm(change))


LEGS = ((LH, LK, LA), (RH, RK, RA))


def leg_buckle(opp: FighterKinematics, ts: np.ndarray, t: int, at: np.ndarray, s: MotionSettings) -> float | None:
    """Movement of the struck leg (the one nearest to the striking surface at frame t) right after
    t: its knee or ankle against the hips, whichever moved more."""
    pos, ok = opp.pos[t], opp.ok[t]
    near: list[tuple[float, tuple[int, int, int]]] = []
    for leg in LEGS:
        segs = [_segment_distance(at, pos[a], pos[b]) for a, b in zip(leg, leg[1:]) if ok[a] and ok[b]]
        if segs:
            near.append((min(segs), leg))
    if not near:
        return None
    _, (_, knee, ankle) = min(near, key=lambda x: x[0])
    lo, hi = _window(ts, t, s.impact_window_s, s.impact_window_s)
    scale = _scale(opp, lo, hi)
    if scale is None:
        return None
    jolts = [j for j in (_jolt((opp.pos[lo:hi, joint] - opp.center[lo:hi]) / scale, t - lo) for joint in (knee, ankle))
             if j is not None]
    return max(jolts) if jolts else None


def _clip01(x: float) -> float:
    return min(1.0, max(0.0, x))


def assess(att: FighterKinematics, opp: FighterKinematics, ts: np.ndarray, kind: EventType, joint: int, peak: int,
           camera_known: bool, s: MotionSettings) -> Assessment:
    lo, hi = _window(ts, peak, s.contact_before_s, s.contact_window_s)
    best: dict[TargetZone, tuple[float, int]] = {}
    first: dict[TargetZone, int] = {}  # first frame the limb reached the zone: the contact
    guard: tuple[float, int] | None = None
    estimated_at: dict[int, bool] = {}
    zones = zones_for(kind)
    for t in range(lo, hi):
        found = zone_gaps(opp, t, striking_points(att, t, kind, joint, s), s, zones)
        if found is None:
            continue
        gaps, guard_gap, estimated_at[t] = found
        for zone, gap in gaps.items():
            if zone not in best or gap < best[zone][0]:
                best[zone] = (gap, t)
            if gap <= s.zone_reach and zone not in first:
                first[zone] = t
        if guard_gap is not None and (guard is None or guard_gap < guard[0]):
            guard = (guard_gap, t)
    if not best:
        return Assessment(evidence=[EvidenceSignal.target_unmeasured])
    zone, (gap, at) = min(best.items(), key=lambda item: item[1][0])
    # the reaction follows the first contact, not the deepest overlap (a kick is deepest on its way back)
    at = first.get(zone, at)
    out = Assessment(zone=zone, contact_frame=at, measures={"zone_gap": round(gap, 3)})
    if guard is not None:
        out.measures["guard_gap"] = round(guard[0], 3)
    touched_guard = guard is not None and guard[0] <= s.zone_reach
    if gap <= s.zone_reach:
        out.evidence.append(EvidenceSignal.zone_contact)
        direction = _unit(att.vel[peak, joint]) if np.isfinite(att.vel[peak, joint]).all() else None
        if zone == TargetZone.head:
            out.reaction, needed, name = head_snap(opp, ts, at, s, direction), s.head_snap_min, "head_snap"
        elif zone == TargetZone.body:
            out.reaction, needed, name = body_push(opp, ts, at, direction, s), s.body_push_min, "body_push"
        else:
            points = striking_points(att, at, kind, joint, s)
            out.reaction = leg_buckle(opp, ts, at, points[0], s) if points else None
            needed, name = s.leg_buckle_min, "leg_buckle"
        if out.reaction is not None:
            out.measures[name] = round(out.reaction, 3)
        if out.reaction is not None and out.reaction >= needed:
            out.outcome = StrikeOutcome.landed
            out.evidence.append(REACTION[zone])
            quality = (0.85 if estimated_at.get(at, False) else 1.0) * (1.0 if camera_known else 0.85)
            out.confidence = round(min(0.9, (0.5 + 0.35 * _clip01((out.reaction - needed) / needed)) * quality), 3)
        elif touched_guard and zone != TargetZone.leg:
            out.outcome, out.confidence = StrikeOutcome.blocked, 0.5
            out.evidence.append(EvidenceSignal.guard_contact)
        elif out.reaction is None:
            out.evidence.append(EvidenceSignal.target_unmeasured)
    elif touched_guard:
        out.outcome, out.confidence = StrikeOutcome.blocked, 0.65
        out.evidence.append(EvidenceSignal.guard_contact)
    else:
        nearest = min(gap, guard[0]) if guard is not None else gap
        if nearest >= s.miss_near:  # came near nothing; closer than that it may have grazed the glove
            out.outcome = StrikeOutcome.missed
            out.evidence.append(EvidenceSignal.no_reach)
            out.confidence = round(0.5 + 0.35 * _clip01((nearest - s.miss_near) / max(1e-6, s.miss_gap - s.miss_near)),
                                   3)
    return out
