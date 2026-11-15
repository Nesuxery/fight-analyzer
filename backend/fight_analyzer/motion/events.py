"""Motion signals and events of the two verified fighters.

Strike attempts
    The speed of a wrist, ankle or knee relative to the fighter's own hips is
    followed over time. An attempt is one continuous stretch above
    `strike_low` whose fastest moment (the peak) reaches the punch/kick/knee
    threshold; it starts and ends where the speed crosses `strike_low`, so one
    motion is counted once no matter how many frames it spans. It also needs
    the limb to open up (arm/leg extension), to move toward the opponent, and
    the opponent to be within reach. Arm motion during a kick or knee is not a
    second attempt, and two arms peaking together are one motion.
    "Possible contact": at or after the peak the striking joint is inside the
    opponent's box and next to one of his joints - in 2D, so never certain.
Advance / retreat
    Hip-centre velocity (camera motion removed) along the line to the
    opponent, smoothed over `advance_smooth_s`, while both fighters stand.
Clinch, ground control (limited estimate)
    Clinch: both standing and very close for `clinch_min_s`. Ground control:
    one fighter down, the other close and above him for `control_min_s`.
Falls
    A stable standing posture followed by a stable grounded one. It becomes a
    possible knockdown if an attempt of the opponent peaked just before and
    the fall was not in a clinch, a possible takedown if the fighters were in
    close contact before it, and a plain stance change otherwise.
No event is produced while a fighter or (for attempts) the opponent is not
verified: missing data means no event, never an assumed one.

Whose event
    Every event carries `attribution_confidence`: the mean identity confidence
    of its actor over the event's frames (of both fighters for an event without
    an actor). The identity confidence is high on frames followed cleanly or
    verified by appearance and low inside a long overlap that could not be
    verified. Below `attribution_min` an event with an actor is marked
    `attribution_uncertain` ("Kime ait belirsiz").
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from fight_analyzer.config import MotionSettings
from fight_analyzer.contracts import DataOrigin, EventType, FighterId, FightEvent, ImagePoint, Limb
from fight_analyzer.pose.cache import PoseArrays

from .camera import CameraTrack
from .kinematics import (
    ARM_LENGTH,
    GROUNDED,
    LA,
    LE,
    LEG_LENGTH,
    LH,
    LK,
    LS,
    LW,
    NOSE,
    RA,
    RE,
    RH,
    RK,
    RS,
    RW,
    STANDING,
    TRANSITION,
    FighterKinematics,
)

FIGHTERS = (FighterId.fighter_a, FighterId.fighter_b)
SHORT = ("a", "b")
# limb -> (end joint, base joint, opposite foot for kicks)
HANDS = ((Limb.left_hand, LW, LS), (Limb.right_hand, RW, RS))
FEET = ((Limb.left_foot, LA, LH, RA), (Limb.right_foot, RA, RH, LA))
KNEES = ((Limb.left_knee, LK, LH, LA), (Limb.right_knee, RK, RH, RA))
ADVANCING, RETREATING, NEUTRAL, NO_MOVEMENT = 0, 1, 2, -1


@dataclass
class MovementRun:
    fighter: int
    advancing: bool
    start_frame: int
    end_frame: int
    start_ms: float
    end_ms: float
    seconds: float


@dataclass
class Analysis:
    events: list[FightEvent]
    runs: list[MovementRun]
    valid: np.ndarray  # [2, F] bool
    activity: np.ndarray  # [2, F] 0..1 or NaN
    hand_speed: np.ndarray  # [2, F]
    foot_speed: np.ndarray  # [2, F]
    approach: np.ndarray  # [2, F] smoothed, body units/s
    movement: np.ndarray  # [2, F] int8
    posture: np.ndarray  # [2, F] int8
    distance: np.ndarray  # [F] body units
    frame_s: np.ndarray  # [F] seconds each frame stands for
    stats: list[dict[str, float]] = field(default_factory=list)


@dataclass
class _Candidate:
    type: EventType
    limb: Limb
    start: int
    peak: int
    end: int
    strength: float  # peak speed / threshold
    confidence: float
    measures: dict[str, float]
    end_joint: int


def frame_seconds(ts: np.ndarray) -> np.ndarray:
    if ts.size == 0:
        return ts.copy()
    d = np.diff(ts)
    last = float(np.median(d)) if d.size else 0.0
    return np.clip(np.append(d, last), 0.0, 0.5)


def _norm(v: np.ndarray) -> np.ndarray:
    return np.linalg.norm(v, axis=-1)


def _cos(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.sum(a * b, axis=-1) / np.maximum(_norm(a) * _norm(b), 1e-9)


def _runs(mask: np.ndarray, ts: np.ndarray, max_gap_s: float) -> list[tuple[int, int]]:
    """Index ranges of consecutive True frames (a time hole > max_gap_s splits them)."""
    out = []
    start = prev = None
    for t in np.flatnonzero(mask):
        if start is None:
            start = prev = t
        elif t == prev + 1 and ts[t] - ts[prev] <= max_gap_s:
            prev = t
        else:
            out.append((start, prev))
            start = prev = t
    if start is not None:
        out.append((start, prev))
    return out


def _window_mean(ts: np.ndarray, x: np.ndarray, half_s: float) -> np.ndarray:
    out = np.full_like(x, np.nan)
    finite = np.isfinite(x)
    for t in np.flatnonzero(finite):
        lo, hi = np.searchsorted(ts, ts[t] - half_s), np.searchsorted(ts, ts[t] + half_s, side="right")
        seg = x[lo:hi]
        good = np.isfinite(seg)
        if good.mean() >= 0.5:
            out[t] = float(seg[good].mean())
    return out


def _target(k: FighterKinematics, arrays: PoseArrays, camera: CameraTrack, upper: bool = False) -> np.ndarray:
    """Where the opponent is (stabilized): hip centre (shoulder centre for `upper`, the
    target of punches), else the other one, else the box centre."""
    first, second = (k.mid(LS, RS), k.center) if upper else (k.center, k.mid(LS, RS))
    out = first.copy()
    miss = np.isnan(out[:, 0])
    out[miss] = second[miss]
    for t in np.flatnonzero(np.isnan(out[:, 0]) & k.present):
        x1, y1, x2, y2 = arrays.boxes[k.det[t]]
        m = camera.to_ref[t]
        out[t] = np.array([(x1 + x2) / 2, (y1 + y2) / 2]) @ m[:, :2].T + m[:, 2]
    return out


def _box_stab(arrays: PoseArrays, camera: CameraTrack, d: int, t: int) -> np.ndarray:
    x1, y1, x2, y2 = arrays.boxes[d]
    corners = np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]]) @ camera.to_ref[t][:, :2].T + camera.to_ref[t][:, 2]
    return np.array([corners[:, 0].min(), corners[:, 1].min(), corners[:, 0].max(), corners[:, 1].max()])


def _finite_mean(rows: np.ndarray) -> np.ndarray:
    """Mean over the measured (finite) values of each column; NaN where none was measured."""
    ok = np.isfinite(rows)
    count = ok.sum(axis=0)
    total = np.where(ok, rows, 0.0).sum(axis=0)
    return np.where(count > 0, total / np.maximum(count, 1), np.nan)


def _clip01(x: float) -> float:
    return min(1.0, max(0.0, x))


def _strike_confidence(strength: float, toward: float, toward_min: float, ext: float, ext_min: float,
                       joint_conf: float) -> float:
    c = (0.35 + 0.25 * _clip01(strength - 1) + 0.2 * _clip01((toward - toward_min) / (1 - toward_min))
         + 0.2 * _clip01((ext - ext_min) / max(1e-6, 1 - ext_min)))
    return round(min(0.95, max(0.05, c * min(1.0, max(0.5, joint_conf)))), 3)


class _Fighter:
    """Signals of one fighter relative to the other."""

    def __init__(self, k: FighterKinematics, opp: FighterKinematics, opp_target: np.ndarray,
                 opp_upper: np.ndarray):
        self.k, self.opp = k, opp
        self.ref = k.ref_vel()
        self.scale = k.scale
        base = k.center.copy()
        sh = k.mid(LS, RS)
        miss = np.isnan(base[:, 0])
        base[miss] = sh[miss]
        self.base = base
        both = (opp.present & k.present)[:, None]
        self.target = np.where(both, opp_target, np.nan)
        self.upper = np.where(both, opp_upper, np.nan)
        self.dist = _norm(self.target - base) / self.scale

    def reach(self, end: int, base: int, length: float, upper: bool = False) -> np.ndarray:
        """How far the limb reaches toward the opponent, in limb lengths (projection, so a
        limb stretched sideways or backwards does not count as extended)."""
        to_opp = (self.upper if upper else self.target) - self.k.pos[:, base]
        unit = to_opp / np.maximum(_norm(to_opp), 1e-9)[:, None]
        return np.sum((self.k.pos[:, end] - self.k.pos[:, base]) * unit, axis=1) / (length * self.scale)

    def speed(self, j: int) -> tuple[np.ndarray, np.ndarray]:
        rel = self.k.vel[:, j] - self.ref
        return _norm(rel) / self.scale, rel

    def toward(self, j: int, base_joint: int, rel: np.ndarray, upper: bool = False) -> np.ndarray:
        to_opp = (self.upper if upper else self.target) - self.k.pos[:, base_joint]
        cos_vel = _cos(rel, to_opp)
        cos_limb = _cos(self.k.pos[:, j] - self.k.pos[:, base_joint], to_opp)
        return np.where(cos_vel >= 0, np.fmax(cos_vel, cos_limb), cos_vel)


def _max(x: np.ndarray) -> float:
    return float(np.nanmax(x)) if np.isfinite(x).any() else math.nan


def _going_down(k: FighterKinematics, ts: np.ndarray, a: int, b: int) -> bool:
    """The fighter is falling during or right after the motion (limbs fly, no attempt)."""
    end = int(np.searchsorted(ts, ts[b] + 0.3, side="right"))
    return k.posture[a] != GROUNDED and bool((k.posture[a:end] == GROUNDED).any())


def _segments(ts: np.ndarray, speed: np.ndarray, s: MotionSettings) -> list[tuple[int, int, int]]:
    out = []
    for a, b in _runs(np.isfinite(speed) & (speed >= s.strike_low), ts, s.max_gap_s):
        if b == a:  # one sample is not a motion
            continue
        out.append((a, a + int(np.nanargmax(speed[a:b + 1])), b))
    return out


def _arm_candidates(f: _Fighter, ts: np.ndarray, s: MotionSettings) -> list[_Candidate]:
    k = f.k
    out = []
    for limb, w, sh in HANDS:
        speed, rel = f.speed(w)
        toward = f.toward(w, sh, rel, upper=True)
        ext = f.reach(w, sh, ARM_LENGTH, upper=True)
        for a, p, b in _segments(ts, speed, s):
            peak = float(speed[p])
            if peak < s.punch_peak or ts[b] - ts[a] > s.strike_max_duration_s or _going_down(k, ts, a, b):
                continue
            before = np.flatnonzero((ts >= ts[a] - 0.2) & (np.arange(ts.size) <= p))
            low = np.nanmin(ext[before]) if np.isfinite(ext[before]).any() else math.nan
            # the arm must open up during the attempt (largest extension reached)
            e, tw, dist = _max(ext[a:b + 1]), float(toward[p]), float(f.dist[p])
            if not (e >= s.punch_extension and e - low >= s.punch_extension_gain and tw >= s.punch_toward
                    and dist <= s.strike_max_distance):
                continue
            jc = float(np.mean(k.conf[p, [w, LE if w == LW else RE, sh]]))
            out.append(_Candidate(EventType.punch, limb, a, p, b, peak / s.punch_peak,
                                  _strike_confidence(peak / s.punch_peak, tw, s.punch_toward, e, s.punch_extension, jc),
                                  {"peak_speed": round(peak, 2), "extension": round(e, 2), "toward": round(tw, 2),
                                   "distance": round(dist, 2), "duration_s": round(float(ts[b] - ts[a]), 3)}, w))
    return out


def _leg_candidates(f: _Fighter, ts: np.ndarray, s: MotionSettings) -> list[_Candidate]:
    k = f.k
    out = []
    for limb, ank, hip, other in FEET:
        speed, rel = f.speed(ank)
        toward = f.toward(ank, hip, rel)
        ext = f.reach(ank, hip, LEG_LENGTH)
        support = np.where(np.isfinite(k.pos[:, other, 1]), k.pos[:, other, 1], k.center[:, 1] + 1.5 * f.scale)
        raise_ = (support - k.pos[:, ank, 1]) / f.scale
        for a, p, b in _segments(ts, speed, s):
            peak = float(speed[p])
            if (peak < s.kick_peak or ts[b] - ts[a] > s.strike_max_duration_s or k.posture[a] == GROUNDED
                    or _going_down(k, ts, a, b)):
                continue
            e, tw, rs, dist = _max(ext[a:b + 1]), float(toward[p]), _max(raise_[p:b + 1]), float(f.dist[p])
            if not (e >= s.kick_extension and rs >= s.kick_raise and tw >= s.kick_toward
                    and dist <= s.strike_max_distance):
                continue
            jc = float(np.mean(k.conf[p, [ank, LK if ank == LA else RK, hip]]))
            out.append(_Candidate(EventType.kick, limb, a, p, b, peak / s.kick_peak,
                                  _strike_confidence(peak / s.kick_peak, tw, s.kick_toward, e, s.kick_extension, jc),
                                  {"peak_speed": round(peak, 2), "extension": round(e, 2), "toward": round(tw, 2),
                                   "raise": round(rs, 2), "distance": round(dist, 2),
                                   "duration_s": round(float(ts[b] - ts[a]), 3)}, ank))
    for limb, knee, hip, ank in KNEES:
        speed, rel = f.speed(knee)
        toward = f.toward(knee, hip, rel)
        height = (k.center[:, 1] - k.pos[:, knee, 1]) / f.scale
        bend = _norm(k.pos[:, ank] - k.pos[:, hip]) / (LEG_LENGTH * f.scale)
        for a, p, b in _segments(ts, speed, s):
            peak = float(speed[p])
            if (peak < s.knee_peak or ts[b] - ts[a] > s.strike_max_duration_s or k.posture[a] == GROUNDED
                    or _going_down(k, ts, a, b)):
                continue
            rising = rel[p, 1] < 0 and abs(rel[p, 1]) >= 0.4 * float(_norm(rel[p]))
            flexed = not np.isfinite(bend[p]) or bend[p] <= 0.75
            h, tw, dist = float(height[p]), float(toward[p]), float(f.dist[p])
            if not (rising and flexed and h >= -0.3 and tw >= s.kick_toward and dist <= s.knee_max_distance):
                continue
            jc = float(np.mean(k.conf[p, [knee, hip]]))
            out.append(_Candidate(EventType.knee, limb, a, p, b, peak / s.knee_peak,
                                  _strike_confidence(peak / s.knee_peak, tw, s.kick_toward, 1.0, 0.0, jc),
                                  {"peak_speed": round(peak, 2), "knee_height": round(h, 2), "toward": round(tw, 2),
                                   "distance": round(dist, 2), "duration_s": round(float(ts[b] - ts[a]), 3)}, knee))
    return out


def _deduplicate(cands: list[_Candidate], ts: np.ndarray, s: MotionSettings) -> list[_Candidate]:
    """One motion = one attempt: legs hide arms, simultaneous limbs merge, re-triggers merge."""
    legs = [c for c in cands if c.type in (EventType.kick, EventType.knee)]
    arms = [c for c in cands if c.type == EventType.punch
            and not any(abs(ts[c.peak] - ts[g.peak]) <= s.leg_over_punch_s for g in legs)]
    kept: list[_Candidate] = []
    for c in sorted(legs + arms, key=lambda c: -c.strength):
        clash = False
        for other in kept:
            same_kind = (c.type == EventType.punch) == (other.type == EventType.punch)
            overlap = not (ts[c.end] < ts[other.start] - s.same_motion_s or ts[c.start] > ts[other.end] + s.same_motion_s)
            if same_kind and (abs(ts[c.peak] - ts[other.peak]) <= s.same_motion_s
                              or (c.limb == other.limb and overlap)):
                clash = True
                break
        if not clash:
            kept.append(c)
    return sorted(kept, key=lambda c: c.peak)


def _contact(f: _Fighter, c: _Candidate, arrays: PoseArrays, camera: CameraTrack, ts: np.ndarray,
             s: MotionSettings) -> bool:
    k, opp = f.k, f.opp
    # from the fastest moment until the limb has had time to reach full extension
    for t in range(c.peak, int(np.searchsorted(ts, ts[c.peak] + 0.2, side="right"))):
        if not opp.present[t] or not k.ok[t, c.end_joint]:
            continue
        x1, y1, x2, y2 = _box_stab(arrays, camera, opp.det[t], t)
        mx, my = (x2 - x1) * 0.1, (y2 - y1) * 0.1
        px, py = k.pos[t, c.end_joint]
        if not (x1 + mx <= px <= x2 - mx and y1 + my <= py <= y2 - my):
            continue
        joints = opp.pos[t][opp.ok[t]]
        if joints.size and float(_norm(joints - k.pos[t, c.end_joint]).min()) <= s.contact_reach * f.scale[t]:
            return True
    return False


def _head_jolt(opp: FighterKinematics, peak: int, ts: np.ndarray, s: MotionSettings) -> float | None:
    """How far the opponent's head moved relative to his shoulders right after the peak,
    beyond how much it moved just before (torso lengths). None when the head is not measured."""
    lo = int(np.searchsorted(ts, ts[peak] - s.impact_window_s))
    hi = int(np.searchsorted(ts, ts[peak] + s.impact_window_s, side="right"))
    with np.errstate(all="ignore"):
        scale = float(np.nanmedian(opp.scale[lo:hi])) if np.isfinite(opp.scale[lo:hi]).any() else np.nan
    if not np.isfinite(scale) or scale <= 0:
        return None
    rel = (opp.pos[lo:hi, NOSE] - opp.mid(LS, RS)[lo:hi]) / scale
    k = peak - lo
    ok = np.isfinite(rel).all(axis=1)
    before = np.flatnonzero(ok[:k + 1])
    after = np.flatnonzero(ok[k + 1:]) + k + 1
    if before.size == 0 or after.size == 0:
        return None
    ref = rel[before[-1]]
    jolt = float(_norm(rel[after] - ref).max())
    base = float(_norm(rel[before] - rel[before[0]]).max()) if before.size > 1 else 0.0
    return max(0.0, jolt - base)


def _posture_runs(ts: np.ndarray, posture: np.ndarray, s: MotionSettings) -> list[tuple[int, int, int]]:
    """Stable posture stretches (value, first, last frame); short unknown holes are bridged."""
    out = []
    for value in (STANDING, GROUNDED):
        for a, b in _runs(posture == value, ts, 0.3):
            if ts[b] - ts[a] >= s.posture_stable_s:
                out.append((value, a, b))
    return sorted(out, key=lambda r: r[1])


def _event(type_: EventType, actor: int | None, target: int | None, a: int, b: int, peak: int | None,
           ts_ms: np.ndarray, confidence: float, *, limb: Limb | None = None, contact: bool = False,
           location: ImagePoint | None = None, measures: dict[str, float] | None = None,
           note: str | None = None) -> FightEvent:
    who = SHORT[actor] if actor is not None else "x"
    a, b, peak = int(a), int(b), None if peak is None else int(peak)
    return FightEvent(event_id=f"{type_.value}-{who}-{peak if peak is not None else a}", type=type_,
                      actor=FIGHTERS[actor] if actor is not None else None,
                      target=FIGHTERS[target] if target is not None else None,
                      start_frame=a, end_frame=b, start_ms=round(float(ts_ms[a]), 1), end_ms=round(float(ts_ms[b]), 1),
                      peak_frame=peak, peak_ms=round(float(ts_ms[peak]), 1) if peak is not None else None,
                      limb=limb, possible_contact=contact, location=location, measures=measures or {},
                      confidence=confidence, data_origin=DataOrigin.measured, note=note)


def attribute(events: list[FightEvent], kin: tuple[FighterKinematics, FighterKinematics],
              identity_conf: np.ndarray, s: MotionSettings) -> None:
    """Set the attribution confidence of every event from the identity confidence [F, 2]."""
    for e in events:
        frames = slice(e.start_frame, e.end_frame + 1)
        values = []
        for f in ([FIGHTERS.index(e.actor)] if e.actor is not None else [0, 1]):
            conf = identity_conf[frames, f][kin[f].present[frames]]
            values.append(float(conf.mean()) if conf.size else 0.0)
        e.attribution_confidence = round(min(1.0, max(0.0, min(values))), 3)
        e.attribution_uncertain = e.actor is not None and e.attribution_confidence < s.attribution_min


def analyze(arrays: PoseArrays, camera: CameraTrack, kin: tuple[FighterKinematics, FighterKinematics],
            s: MotionSettings, identity_conf: np.ndarray | None = None) -> Analysis:
    ts_ms = arrays.timestamp_ms.astype(np.float64)
    ts = ts_ms / 1000.0
    n = arrays.frame_count
    frame_s = frame_seconds(ts)
    sides = tuple(_Fighter(kin[i], kin[1 - i], _target(kin[1 - i], arrays, camera),
                           _target(kin[1 - i], arrays, camera, upper=True)) for i in range(2))
    events: list[FightEvent] = []
    strikes: list[list[tuple[_Candidate, bool]]] = [[], []]
    posture = np.stack([k.posture for k in kin])
    # Lying under the opponent: arm and leg motion there (covering, framing, being hit)
    # cannot be told apart from attempts in 2D, so none are counted.
    underneath = np.zeros((2, n), bool)
    for i in range(2):
        mine, other = kin[i], kin[1 - i]
        with np.errstate(all="ignore"):
            above = (mine.center[:, 1] - other.center[:, 1]) >= 0.2 * mine.scale
            near = _norm(other.center - mine.center) / mine.scale <= s.control_distance
        underneath[i] = (mine.posture == GROUNDED) & other.valid & above & near

    for i, f in enumerate(sides):
        for c in _deduplicate(_arm_candidates(f, ts, s) + _leg_candidates(f, ts, s), ts, s):
            if underneath[i, c.peak]:
                continue
            contact = _contact(f, c, arrays, camera, ts, s)
            strikes[i].append((c, contact))
            loc = f.k.image[c.peak, c.end_joint]
            measures = dict(c.measures)
            if contact:  # possible impact: the opponent's head snapped right after the contact
                jolt = _head_jolt(f.opp, c.peak, ts, s)
                if jolt is not None:
                    measures["head_jolt"] = round(jolt, 3)
                    measures["impact"] = 1.0 if jolt >= s.impact_head_jolt else 0.0
            events.append(_event(c.type, i, 1 - i, c.start, c.end, c.peak, ts_ms, c.confidence, limb=c.limb,
                                 contact=contact, measures=measures,
                                 location=ImagePoint(x=round(float(loc[0]), 1), y=round(float(loc[1]), 1))
                                 if np.isfinite(loc).all() else None))

    # Per-frame signals
    activity = np.full((2, n), np.nan)
    hand = np.full((2, n), np.nan)
    foot = np.full((2, n), np.nan)
    approach = np.full((2, n), np.nan)
    for i, f in enumerate(sides):
        hs = np.stack([f.speed(j)[0] for j in (LW, RW)])
        fs = np.stack([f.speed(j)[0] for j in (LA, RA)])
        limbs = np.concatenate([hs, fs])
        hand[i] = _finite_mean(hs)
        foot[i] = _finite_mean(fs)
        count = np.isfinite(limbs).sum(axis=0)
        activity[i] = np.where((count >= 2) & f.k.valid, np.clip(_finite_mean(limbs) / s.activity_ref, 0, 1), np.nan)
        hand[i][~f.k.valid] = np.nan
        foot[i][~f.k.valid] = np.nan
        to_opp = f.target - f.base
        raw = np.sum(f.k.center_vel * to_opp, axis=1) / np.maximum(_norm(to_opp), 1e-9) / f.scale
        approach[i] = _window_mean(ts, np.where(f.k.valid & kin[1 - i].valid, raw, np.nan), s.advance_smooth_s / 2)

    both_up = np.isin(posture, (STANDING, TRANSITION)).all(axis=0)
    movement = np.full((2, n), NO_MOVEMENT, np.int8)
    runs: list[MovementRun] = []
    for i in range(2):
        ok = both_up & np.isfinite(approach[i])
        movement[i][ok] = NEUTRAL
        for adv in (True, False):
            mask = ok & ((approach[i] >= s.advance_speed) if adv else (approach[i] <= -s.advance_speed))
            for a, b in _runs(mask, ts, s.max_gap_s):
                secs = float(frame_s[a:b + 1].sum())
                if secs < s.min_run_s:
                    continue
                movement[i][a:b + 1] = ADVANCING if adv else RETREATING
                runs.append(MovementRun(i, adv, int(a), int(b), float(ts_ms[a]),
                                        float(ts_ms[b] + frame_s[b] * 1000), secs))

    with np.errstate(all="ignore"):
        scale = (kin[0].scale + kin[1].scale) / 2
        distance = np.where(kin[0].valid & kin[1].valid, _norm(kin[0].center - kin[1].center) / scale, np.nan)

    # Clinch: both up and very close.
    clinches = []
    for a, b in _runs(both_up & (distance <= s.clinch_distance), ts, 0.3):
        if float(frame_s[a:b + 1].sum()) >= s.clinch_min_s:
            clinches.append((a, b))
            events.append(_event(EventType.clinch, None, None, a, b, None, ts_ms, 0.6,
                                 measures={"seconds": round(float(frame_s[a:b + 1].sum()), 2)}))

    # Ground control: one fighter down, the other close and above him.
    control = np.zeros((2, n), bool)
    for top in range(2):
        bottom = 1 - top
        kt, kb = kin[top], kin[bottom]
        above = (kb.center[:, 1] - kt.center[:, 1]) >= 0.2 * kb.scale
        near = _norm(kt.center - kb.center) / kb.scale <= s.control_distance
        mask = (kb.posture == GROUNDED) & kt.valid & kb.valid & above & near
        for a, b in _runs(mask, ts, 0.3):
            secs = float(frame_s[a:b + 1].sum())
            if secs >= s.control_min_s:
                control[top, a:b + 1] = True
                events.append(_event(EventType.ground_control, top, bottom, a, b, None, ts_ms, 0.5,
                                     measures={"seconds": round(secs, 2)}, note="Tahmini; yakınlık ve duruştan"))

    # Falls and getting up.
    for i, k in enumerate(kin):
        opp = 1 - i
        pr = _posture_runs(ts, k.posture, s)
        for (v1, a1, b1), (v2, a2, b2) in zip(pr, pr[1:]):
            gap = slice(b1, a2 + 1)
            if ts[a2] - ts[b1] > s.fall_max_s or k.present[gap].mean() < 0.5:
                continue
            if v1 == GROUNDED and v2 == STANDING:
                events.append(_event(EventType.stance_change, i, None, b1, a2, a2, ts_ms, 0.6, note="Ayağa kalktı"))
                continue
            if not (v1 == STANDING and v2 == GROUNDED):
                continue
            fall_s = float(ts[a2] - ts[b1])
            start = ts[b1]  # the fall begins where the stable standing ends
            before = [(c, contact) for c, contact in strikes[opp]
                      if start - s.knockdown_window_s <= ts[c.peak] <= ts[a2]]
            in_clinch = any(a <= b1 and b >= max(0, b1 - 1) for a, b in clinches)
            close = np.flatnonzero((ts >= start - s.takedown_window_s) & (ts <= ts[a2])
                                   & (distance <= s.clinch_distance * 1.2))
            close_s = float(frame_s[close].sum()) if close.size else 0.0
            # The other fighter was already down: this is following him down (e.g. to strike
            # on the ground), and a fighter on the ground does not score a knockdown/takedown.
            lo = int(np.searchsorted(ts, start - 0.5))
            opp_down_first = bool((kin[opp].posture[lo:b1 + 1] == GROUNDED).any())
            on_top_after = control[opp, a2:min(n, a2 + int(np.searchsorted(ts[a2:], ts[a2] + 1.5)))].any()
            measures = {"fall_s": round(fall_s, 2)}
            if opp_down_first:
                events.append(_event(EventType.stance_change, i, None, b1, a2, a2, ts_ms, 0.6, measures=measures,
                                     note="Yere indi (rakip zaten yerdeydi)"))
            elif before and not in_clinch:
                contact = any(ct for _, ct in before)
                last = max(before, key=lambda x: x[0].peak)[0]
                measures |= {"strike_before_s": round(float(start - ts[last.peak]), 2),
                             "possible_contact": 1.0 if contact else 0.0}
                conf = 0.45 + 0.25 * contact + 0.15 * (fall_s <= 0.6) + 0.1 * (kin[opp].posture[a2] != GROUNDED)
                events.append(_event(EventType.knockdown, opp, i, b1, a2, a2, ts_ms, round(min(conf, 0.95), 3),
                                     measures=measures,
                                     note="Öncesinde olası temaslı vuruş" if contact else "Öncesinde vuruş denemesi"))
            elif close_s >= 0.5:
                measures |= {"close_s": round(close_s, 2), "on_top_after": 1.0 if on_top_after else 0.0}
                conf = 0.4 + 0.3 * bool(in_clinch or close_s >= 1.0) + 0.2 * on_top_after
                events.append(_event(EventType.takedown, opp, i, b1, a2, a2, ts_ms, round(min(conf, 0.95), 3),
                                     measures=measures, note="Öncesinde yakın temas"))
            else:
                events.append(_event(EventType.stance_change, i, None, b1, a2, a2, ts_ms, 0.6, measures=measures,
                                     note="Yere indi"))

    events.sort(key=lambda e: (e.start_ms, e.event_id))
    seen: dict[str, int] = {}
    for e in events:  # ids are type-actor-frame; make repeats unique
        seen[e.event_id] = seen.get(e.event_id, 0) + 1
        if seen[e.event_id] > 1:
            e.event_id = f"{e.event_id}-{seen[e.event_id]}"
    if identity_conf is not None:
        attribute(events, kin, identity_conf, s)
    valid = np.stack([k.valid for k in kin])
    stats = []
    for i in range(2):
        mine = [e for e in events if e.actor == FIGHTERS[i]]
        stats.append({
            "strike_attempts": sum(e.type in (EventType.punch, EventType.knee) for e in mine),
            "kick_attempts": sum(e.type == EventType.kick for e in mine),
            "possible_contacts": sum(e.possible_contact for e in mine),
            "possible_knockdowns": sum(e.type == EventType.knockdown for e in mine),
            "possible_takedowns": sum(e.type == EventType.takedown for e in mine),
            "control_s": round(float(frame_s[control[i]].sum()), 2),
            "advance_s": round(sum(r.seconds for r in runs if r.fighter == i and r.advancing), 2),
            "retreat_s": round(sum(r.seconds for r in runs if r.fighter == i and not r.advancing), 2),
            "measured_s": round(float(frame_s[valid[i]].sum()), 2),
        })
    return Analysis(events=events, runs=runs, valid=valid, activity=activity, hand_speed=hand, foot_speed=foot,
                    approach=approach, movement=movement, posture=posture, distance=distance, frame_s=frame_s,
                    stats=stats)
