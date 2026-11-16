"""Motion signals and events of the two verified fighters.

Strike attempts
    The speed of a wrist, ankle, knee or elbow relative to the fighter's own
    hips is followed over time. An attempt is one continuous stretch above
    `strike_low` whose fastest moment (the peak) reaches the threshold of its
    kind; it starts and ends where the speed crosses `strike_low`, so one motion
    is counted once no matter how many frames it spans.
    - punch: the arm opens up (extension), moves toward the opponent's upper
      body, and the opponent is within reach;
    - elbow: the elbow leads while the arm stays folded, at close range;
    - kick, knee: the leg extends and rises / the knee rises toward him;
    - ground strike: an arm strike from above on an opponent who is down (no
      reach is needed, a lower speed is enough).
    Arm motion during a kick or knee is not a second attempt (also when the
    kick itself was not found: a leg moving fast and high is enough), a hand
    below the standing opponent's hips is catching or blocking a kick, two arms
    peaking together are one motion, and an elbow inside a punch of the same
    arm is the punch. The fastest moment is taken while the limb moves toward
    the opponent (the way back of a strike can be faster). What an attempt did (target zone; landed, blocked, missed or
    unknown) is estimated in strikes.py. Significant strikes: every strike at
    distance; in the clinch and on the ground only power strikes.
    "Possible contact": at or after the peak the striking joint is inside the
    opponent's box and next to one of his joints - in 2D, so never certain.
Down
    Lying, sitting or on hands and knees: the posture says grounded, or the hips
    came down to `fall_height_share` of their height above the feet when the
    fighter last stood (a fighter sitting against the cage after a knockdown
    looks upright in 2D).
Advance / retreat
    Hip-centre velocity (camera motion removed) along the line to the
    opponent, smoothed over `advance_smooth_s`, while both fighters stand.
Clinch, ground control (limited estimate)
    Clinch: both standing and very close for `clinch_min_s`. Ground control:
    one fighter down, the other close and above him for `control_min_s`.
Falls
    A stable standing stretch followed by a stable down one. A possible
    knockdown when a strike of the opponent peaked just before (not in a
    clinch) and the strikes did not all clearly miss; a possible takedown after
    close contact; otherwise a slip (stance change).
    When the falling fighter's identity is not verified around the fall but the
    other fighter is followed with high confidence and stays on his feet, the
    person on the same tracker id is taken to be the falling fighter
    (`infer_presence`). A knockdown found only this way stays "possible", gets
    a low confidence and carries `identity_inferred`.
Damage signals: damage.py.
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
from fight_analyzer.contracts import (
    DamageSignal,
    DataOrigin,
    EventType,
    EvidenceSignal,
    FighterId,
    FightEvent,
    FightPhase,
    ImagePoint,
    Limb,
    StrikeOutcome,
    TargetZone,
)
from fight_analyzer.pose.cache import PoseArrays

from . import damage as damage_mod
from . import strikes as strikes_mod
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
    compute,
    hip_height,
)

FIGHTERS = (FighterId.fighter_a, FighterId.fighter_b)
SHORT = ("a", "b")
# limb -> (end joint, base joint, opposite foot for kicks)
HANDS = ((Limb.left_hand, LW, LS), (Limb.right_hand, RW, RS))
FEET = ((Limb.left_foot, LA, LH, RA), (Limb.right_foot, RA, RH, LA))
KNEES = ((Limb.left_knee, LK, LH, LA), (Limb.right_knee, RK, RH, RA))
ARM_TYPES = frozenset({EventType.punch, EventType.elbow, EventType.ground_strike})
STRIKE_TYPES = ARM_TYPES | {EventType.kick, EventType.knee}
HAND_STRIKES = frozenset({EventType.punch, EventType.knee, EventType.elbow, EventType.ground_strike})
REACTIONS = (EvidenceSignal.head_snap, EvidenceSignal.body_push, EvidenceSignal.leg_buckle)
UPPER_ARM = 0.62  # shoulder to elbow, torso lengths (kinematics.SEGMENTS)
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
    posture: np.ndarray  # [2, F] int8 (grounded wherever the fighter is down)
    distance: np.ndarray  # [F] body units
    frame_s: np.ndarray  # [F] seconds each frame stands for
    stats: list[dict[str, float]] = field(default_factory=list)
    damage: list[DamageSignal] = field(default_factory=list)


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


@dataclass
class _Strike:
    cand: _Candidate
    contact: bool  # possible contact (2D overlap)
    result: strikes_mod.Assessment
    event: FightEvent | None = None  # None: found only against an inferred opponent, not listed


@dataclass
class _Fall:
    fighter: int  # the fighter who went down (or got up)
    kind: EventType  # knockdown, takedown or stance_change
    a1: int  # standing (down for a get-up) stretch: first and last frame
    b1: int
    a2: int  # down (standing) stretch after it
    b2: int
    confidence: float
    measures: dict[str, float]
    evidence: list[EvidenceSignal]
    note: str
    strikes: list[_Strike]  # the opponent's strikes just before


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


def _close_holes(mask: np.ndarray, ts: np.ndarray, gap_s: float) -> np.ndarray:
    """Short False stretches between True frames become True."""
    out = mask.copy()
    idx = np.flatnonzero(mask)
    for a, b in zip(idx[:-1], idx[1:]):
        if b > a + 1 and ts[b] - ts[a] <= gap_s:
            out[a + 1:b] = True
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


def _fighter(k: FighterKinematics, opp: FighterKinematics, arrays: PoseArrays, camera: CameraTrack) -> _Fighter:
    return _Fighter(k, opp, _target(opp, arrays, camera), _target(opp, arrays, camera, upper=True))


def _max(x: np.ndarray) -> float:
    return float(np.nanmax(x)) if np.isfinite(x).any() else math.nan


# ---- down, standing reference ---------------------------------------------------

def standing_reference(k: FighterKinematics, ts: np.ndarray, s: MotionSettings,
                       height: np.ndarray | None = None) -> np.ndarray:
    """Hip height above the feet while the fighter last stood upright (median over the
    `fall_reference_s` up to that moment), kept `fall_hold_s`; NaN without one."""
    height = hip_height(k) if height is None else height
    n = ts.size
    ref = np.full(n, np.nan)
    with np.errstate(invalid="ignore"):
        ok = k.present & (k.posture == STANDING) & np.isfinite(height) & (height >= s.fall_upright)
    idx = np.flatnonzero(ok)
    if idx.size == 0:
        return ref
    values = height[idx]
    lo = np.searchsorted(ts[idx], ts[idx] - s.fall_reference_s)
    at_ok = np.array([float(np.median(values[a:j + 1])) for j, a in enumerate(lo)])
    pos = np.searchsorted(idx, np.arange(n), side="right") - 1
    last = idx[np.maximum(pos, 0)]
    fresh = (pos >= 0) & (ts - ts[last] <= s.fall_hold_s)
    ref[fresh] = at_ok[pos[fresh]]
    return ref


def down_mask(k: FighterKinematics, ts: np.ndarray, s: MotionSettings) -> tuple[np.ndarray, np.ndarray]:
    """Frames on which the fighter is down, and his hip height as a share of the standing one."""
    height = hip_height(k)
    with np.errstate(all="ignore"):
        share = height / standing_reference(k, ts, s, height)
        low = np.isfinite(share) & (share <= s.fall_height_share) & (k.posture != STANDING)
    return k.present & ((k.posture == GROUNDED) | low), share


def _going_down(down: np.ndarray, ts: np.ndarray, a: int, b: int) -> bool:
    """The fighter is falling during or right after the motion (limbs fly, no attempt)."""
    end = int(np.searchsorted(ts, ts[b] + 0.3, side="right"))
    return not down[a] and bool(down[a:end].any())


def _underneath(mine: FighterKinematics, other: FighterKinematics, mine_down: np.ndarray,
                s: MotionSettings) -> np.ndarray:
    """Down under the opponent: arm and leg motion there (covering, framing, being hit) cannot
    be told apart from attempts in 2D, so none are counted."""
    with np.errstate(all="ignore"):
        lower = (mine.center[:, 1] - other.center[:, 1]) >= 0.2 * mine.scale
        near = _norm(other.center - mine.center) / mine.scale <= s.control_distance
    return mine_down & other.valid & lower & near


def _distance(kin: tuple[FighterKinematics, FighterKinematics]) -> np.ndarray:
    with np.errstate(all="ignore"):
        scale = (kin[0].scale + kin[1].scale) / 2
        return np.where(kin[0].valid & kin[1].valid, _norm(kin[0].center - kin[1].center) / scale, np.nan)


def _both_up(posture: np.ndarray, down: np.ndarray) -> np.ndarray:
    return np.isin(posture, (STANDING, TRANSITION)).all(axis=0) & ~down.any(axis=0)


def _clinch_runs(ts: np.ndarray, both_up: np.ndarray, distance: np.ndarray, frame_s: np.ndarray,
                 s: MotionSettings) -> list[tuple[int, int]]:
    with np.errstate(invalid="ignore"):
        close = both_up & (distance <= s.clinch_distance)
    return [(a, b) for a, b in _runs(close, ts, 0.3) if float(frame_s[a:b + 1].sum()) >= s.clinch_min_s]


# ---- strike attempts --------------------------------------------------------------

def _segments(ts: np.ndarray, speed: np.ndarray, s: MotionSettings) -> list[tuple[int, int, int]]:
    out = []
    for a, b in _runs(np.isfinite(speed) & (speed >= s.strike_low), ts, s.max_gap_s):
        if b == a:  # one sample is not a motion
            continue
        out.append((a, a + int(np.nanargmax(speed[a:b + 1])), b))
    return out


def _toward_peak(speed: np.ndarray, toward: np.ndarray, a: int, b: int) -> int | None:
    """The fastest moment of a motion while the limb moves toward the opponent. A strike and
    its way back are often one stretch above `strike_low`, and the way back can be faster:
    judged there, a real strike would look like a motion away from him. None: never toward him."""
    sp, tw = speed[a:b + 1], toward[a:b + 1]
    ok = np.isfinite(sp) & np.isfinite(tw) & (tw > 0)
    return a + int(np.argmax(np.where(ok, sp, -np.inf))) if ok.any() else None


def _elbow_near(f: _Fighter, el: int, a: int, b: int, s: MotionSettings) -> bool:
    """The elbow came close to the opponent's head or body zone between frames a and b."""
    for t in range(a, b):
        if not f.k.ok[t, el]:
            continue
        found = strikes_mod.zone_gaps(f.opp, t, [f.k.pos[t, el]], s)
        if found is None:
            continue
        gaps = [g for z, g in found[0].items() if z != TargetZone.leg]
        if gaps and min(gaps) <= s.elbow_near:
            return True
    return False


def _arm_candidates(f: _Fighter, ts: np.ndarray, s: MotionSettings, own_down: np.ndarray,
                    opp_down: np.ndarray) -> list[_Candidate]:
    k = f.k
    out = []
    for limb, w, sh in HANDS:
        el = LE if w == LW else RE
        speed, rel = f.speed(w)
        toward = f.toward(w, sh, rel, upper=True)
        ext = f.reach(w, sh, ARM_LENGTH, upper=True)
        for a, _, b in _segments(ts, speed, s):
            p = _toward_peak(speed, toward, a, b)
            if p is None or ts[b] - ts[a] > s.strike_max_duration_s or _going_down(own_down, ts, a, b):
                continue
            peak = float(speed[p])
            tw, dist = float(toward[p]), float(f.dist[p])
            jc = float(np.mean(k.conf[p, [w, el, sh]]))
            if opp_down[p]:  # from above on a downed opponent: no reach needed
                if not (peak >= s.ground_strike_peak and tw >= s.ground_strike_toward and dist <= s.control_distance):
                    continue
                strength = peak / s.ground_strike_peak
                out.append(_Candidate(EventType.ground_strike, limb, a, p, b, strength,
                                      _strike_confidence(strength, tw, s.ground_strike_toward, 1.0, 0.0, jc),
                                      {"peak_speed": round(peak, 2), "toward": round(tw, 2), "distance": round(dist, 2),
                                       "duration_s": round(float(ts[b] - ts[a]), 3)}, w))
                continue
            if peak < s.punch_peak:
                continue
            before = np.flatnonzero((ts >= ts[a] - 0.2) & (np.arange(ts.size) <= p))
            low = np.nanmin(ext[before]) if np.isfinite(ext[before]).any() else math.nan
            # the arm must open up during the attempt (largest extension reached)
            e = _max(ext[a:b + 1])
            if not (e >= s.punch_extension and e - low >= s.punch_extension_gain and tw >= s.punch_toward
                    and dist <= s.strike_max_distance):
                continue
            out.append(_Candidate(EventType.punch, limb, a, p, b, peak / s.punch_peak,
                                  _strike_confidence(peak / s.punch_peak, tw, s.punch_toward, e, s.punch_extension, jc),
                                  {"peak_speed": round(peak, 2), "extension": round(e, 2), "toward": round(tw, 2),
                                   "distance": round(dist, 2), "duration_s": round(float(ts[b] - ts[a]), 3)}, w))
        # Elbows: the elbow joint leads toward the opponent, the arm stays folded through the motion.
        espeed, erel = f.speed(el)
        etoward = f.toward(el, sh, erel, upper=True)
        ereach = f.reach(el, sh, UPPER_ARM, upper=True)
        with np.errstate(all="ignore"):
            fold = _norm(k.pos[:, w] - k.pos[:, sh]) / (ARM_LENGTH * f.scale)
            rise = (k.pos[:, sh, 1] - k.pos[:, el, 1]) / f.scale  # > 0: elbow above the shoulder
        for a, _, b in _segments(ts, espeed, s):
            p = _toward_peak(espeed, etoward, a, b)
            if p is None:
                continue
            peak = float(espeed[p])
            if (peak < s.elbow_peak or ts[b] - ts[a] > s.strike_max_duration_s or opp_down[p]
                    or _going_down(own_down, ts, a, b)):
                continue
            after = int(np.searchsorted(ts, ts[b] + 0.15, side="right"))
            widest, tw, dist = _max(fold[a:after]), float(etoward[p]), float(f.dist[p])
            leads = not np.isfinite(speed[p]) or peak >= s.elbow_lead * float(speed[p])
            if not (widest <= s.elbow_fold and tw >= s.elbow_toward and dist <= s.elbow_max_distance and leads
                    and _max(ereach[a:after]) >= s.elbow_reach and _max(rise[a:after]) >= -s.elbow_height
                    and _elbow_near(f, el, p, after, s)):
                continue
            jc = float(np.mean(k.conf[p, [w, el, sh]]))
            strength = peak / s.elbow_peak
            out.append(_Candidate(EventType.elbow, limb, a, p, b, strength,
                                  _strike_confidence(strength, tw, s.elbow_toward, 1 - widest, 1 - s.elbow_fold, jc),
                                  {"peak_speed": round(peak, 2), "fold": round(widest, 2), "toward": round(tw, 2),
                                   "distance": round(dist, 2), "duration_s": round(float(ts[b] - ts[a]), 3)}, el))
    return out


def _leg_candidates(f: _Fighter, ts: np.ndarray, s: MotionSettings, own_down: np.ndarray) -> list[_Candidate]:
    k = f.k
    out = []
    for limb, ank, hip, other in FEET:
        speed, rel = f.speed(ank)
        toward = f.toward(ank, hip, rel)
        ext = f.reach(ank, hip, LEG_LENGTH)
        support = np.where(np.isfinite(k.pos[:, other, 1]), k.pos[:, other, 1], k.center[:, 1] + 1.5 * f.scale)
        raise_ = (support - k.pos[:, ank, 1]) / f.scale
        for a, _, b in _segments(ts, speed, s):
            p = _toward_peak(speed, toward, a, b)
            if p is None:
                continue
            peak = float(speed[p])
            if (peak < s.kick_peak or ts[b] - ts[a] > s.strike_max_duration_s or own_down[a]
                    or _going_down(own_down, ts, a, b)):
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
        for a, _, b in _segments(ts, speed, s):
            p = _toward_peak(speed, toward, a, b)
            if p is None:
                continue
            peak = float(speed[p])
            if (peak < s.knee_peak or ts[b] - ts[a] > s.strike_max_duration_s or own_down[a]
                    or _going_down(own_down, ts, a, b)):
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


def _overlap(a: _Candidate, b: _Candidate, ts: np.ndarray, pad_s: float) -> bool:
    return not (ts[a.end] < ts[b.start] - pad_s or ts[a.start] > ts[b.end] + pad_s)


def _deduplicate(cands: list[_Candidate], ts: np.ndarray, s: MotionSettings) -> list[_Candidate]:
    """One motion = one attempt: legs hide arms, an elbow inside a punch of the same arm is the
    punch, simultaneous limbs merge, re-triggers merge."""
    legs = [c for c in cands if c.type not in ARM_TYPES]
    arms = [c for c in cands if c.type in ARM_TYPES
            and not any(abs(ts[c.peak] - ts[g.peak]) <= s.leg_over_punch_s for g in legs)]
    arms = [c for c in arms if not (c.type == EventType.elbow and any(
        o.type == EventType.punch and o.limb == c.limb and _overlap(c, o, ts, 0.0) for o in arms))]
    kept: list[_Candidate] = []
    for c in sorted(legs + arms, key=lambda c: -c.strength):
        clash = False
        for other in kept:
            same_kind = (c.type in ARM_TYPES) == (other.type in ARM_TYPES)
            if same_kind and (abs(ts[c.peak] - ts[other.peak]) <= s.same_motion_s
                              or (c.limb == other.limb and _overlap(c, other, ts, s.same_motion_s))):
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


def _kicking(f: _Fighter, s: MotionSettings) -> np.ndarray:
    """Frames on which a leg moves like a kick (fast and raised), whether it was found as a kick or not."""
    k = f.k
    out = np.zeros(k.present.size, bool)
    for _, ank, _, other in FEET:
        speed, _ = f.speed(ank)
        support = np.where(np.isfinite(k.pos[:, other, 1]), k.pos[:, other, 1], k.center[:, 1] + 1.5 * f.scale)
        with np.errstate(invalid="ignore"):
            raised = (support - k.pos[:, ank, 1]) / f.scale >= s.kick_raise
            out |= (speed >= s.kick_motion * s.kick_peak) & raised
    return out


def _arm_motion_is_a_strike(f: _Fighter, c: _Candidate, ts: np.ndarray, kicking: np.ndarray,
                            s: MotionSettings) -> bool:
    """Arm motion of a punch or elbow that is not one: the arms swing during the fighter's own
    kick, and a hand below the opponent's hips catches or blocks a kick (standing opponent)."""
    if c.type not in (EventType.punch, EventType.elbow):
        return True
    lo = int(np.searchsorted(ts, ts[c.peak] - s.leg_over_punch_s))
    hi = int(np.searchsorted(ts, ts[c.peak] + s.leg_over_punch_s, side="right"))
    if kicking[lo:hi].any():
        return False
    y, hip, scale = f.k.pos[c.peak, c.end_joint, 1], f.opp.center[c.peak, 1], f.opp.scale[c.peak]
    return not (np.isfinite(y) and np.isfinite(hip) and np.isfinite(scale) and y > hip + s.punch_below_hips * scale)


def _strikes(f: _Fighter, ts: np.ndarray, s: MotionSettings, own_down: np.ndarray, opp_down: np.ndarray,
             underneath: np.ndarray, arrays: PoseArrays, camera: CameraTrack) -> list[_Strike]:
    kicking = _kicking(f, s)
    found = _arm_candidates(f, ts, s, own_down, opp_down) + _leg_candidates(f, ts, s, own_down)
    cands = _deduplicate([c for c in found if _arm_motion_is_a_strike(f, c, ts, kicking, s)], ts, s)
    out = []
    for c in cands:
        if underneath[c.peak]:
            continue
        result = strikes_mod.assess(f.k, f.opp, ts, c.type, c.end_joint, c.peak, bool(camera.known[c.peak]), s)
        out.append(_Strike(c, _contact(f, c, arrays, camera, ts, s), result))
    return out


def _phase(t: int, down: np.ndarray, in_clinch: np.ndarray) -> FightPhase:
    if down[0, t] or down[1, t]:
        return FightPhase.ground
    return FightPhase.clinch if in_clinch[t] else FightPhase.distance


# ---- falls ----------------------------------------------------------------------

def _level_runs(ts: np.ndarray, up: np.ndarray, down: np.ndarray, s: MotionSettings) -> list[tuple[int, int, int]]:
    """Stable standing and down stretches (value, first, last frame); short holes are closed."""
    d = _close_holes(down, ts, s.fall_close_s)
    u = _close_holes(up & ~d, ts, s.fall_close_s) & ~d
    out = []
    for value, mask in ((STANDING, u), (GROUNDED, d)):
        for a, b in _runs(mask, ts, 0.3):
            if ts[b] - ts[a] >= s.posture_stable_s:
                out.append((value, a, b))
    return sorted(out, key=lambda r: r[1])


def _falls(i: int, kin: tuple[FighterKinematics, FighterKinematics], down: np.ndarray, up: np.ndarray,
           share: np.ndarray, ts: np.ndarray, frame_s: np.ndarray, strikes: list[list[_Strike]],
           clinches: list[tuple[int, int]], distance: np.ndarray, control: np.ndarray,
           s: MotionSettings) -> list[_Fall]:
    """Falls of fighter i and his getting up; `strikes[opp]` are the opponent's strikes."""
    k, opp = kin[i], 1 - i
    out: list[_Fall] = []
    runs = _level_runs(ts, up[i], down[i], s)
    for (v1, a1, b1), (v2, a2, b2) in zip(runs, runs[1:]):
        gap = slice(b1, a2 + 1)
        if ts[a2] - ts[b1] > s.fall_max_s or k.present[gap].mean() < 0.5:
            continue
        if v1 == GROUNDED and v2 == STANDING:
            out.append(_Fall(i, EventType.stance_change, a1, b1, a2, b2, 0.6, {}, [], "Ayağa kalktı", []))
            continue
        if not (v1 == STANDING and v2 == GROUNDED):
            continue
        fall_s = float(ts[a2] - ts[b1])
        start = ts[b1]  # the fall begins where the stable standing ends
        measures = {"fall_s": round(fall_s, 2), "down_s": round(float(ts[b2] - ts[a2] + frame_s[b2]), 2)}
        low = share[i, a2:b2 + 1]
        if np.isfinite(low).any():
            measures["hip_share"] = round(float(np.nanmin(low)), 3)
        before = [x for x in strikes[opp] if start - s.knockdown_window_s <= ts[x.cand.peak] <= ts[a2]]
        in_clinch = any(a <= b1 and b >= max(0, b1 - 1) for a, b in clinches)
        with np.errstate(invalid="ignore"):
            close = np.flatnonzero((ts >= start - s.takedown_window_s) & (ts <= ts[a2])
                                   & (distance <= s.clinch_distance * 1.2))
        close_s = float(frame_s[close].sum()) if close.size else 0.0
        # The other fighter was already down: this is following him down (e.g. to strike
        # on the ground), and a fighter on the ground does not score a knockdown/takedown.
        lo = int(np.searchsorted(ts, start - 0.5))
        opp_down_first = bool(down[opp, lo:b1 + 1].any())
        hi = int(np.searchsorted(ts, ts[a2] + 1.5, side="right"))
        on_top_after = bool(control[opp, a2:hi].any())
        drop = [EvidenceSignal.hip_drop]
        if opp_down_first:
            out.append(_Fall(i, EventType.stance_change, a1, b1, a2, b2, 0.6, measures, drop,
                             "Yere indi (rakip zaten yerdeydi)", []))
        elif before and not in_clinch:
            landed = [x for x in before if x.result.outcome == StrikeOutcome.landed]
            touched = [x for x in before if x.contact or EvidenceSignal.zone_contact in x.result.evidence]
            if all(x.result.outcome == StrikeOutcome.missed and (x.result.confidence or 0) >= s.slip_missed_confidence
                   for x in before):
                out.append(_Fall(i, EventType.stance_change, a1, b1, a2, b2, 0.6, measures, drop,
                                 "Yere indi; öncesindeki vuruş isabet etmedi", before))
                continue
            last = max(before, key=lambda x: x.cand.peak)
            measures |= {"strike_before_s": round(float(start - ts[last.cand.peak]), 2),
                         "possible_contact": 1.0 if touched else 0.0, "landed_before": 1.0 if landed else 0.0}
            conf = (0.4 + 0.25 * bool(landed) + 0.1 * bool(touched and not landed) + 0.15 * (fall_s <= 0.6)
                    + 0.1 * (not down[opp, a2]))
            evidence = [EvidenceSignal.strike_before, *drop]
            if touched:
                evidence.append(EvidenceSignal.zone_contact)
            for x in landed:
                evidence += [sig for sig in x.result.evidence if sig in REACTIONS and sig not in evidence]
            note = ("Öncesinde isabetli vuruş (tahmini)" if landed
                    else "Öncesinde olası temaslı vuruş" if touched else "Öncesinde vuruş denemesi")
            out.append(_Fall(i, EventType.knockdown, a1, b1, a2, b2, round(min(conf, 0.95), 3), measures, evidence,
                             note, before))
        elif close_s >= 0.5:
            measures |= {"close_s": round(close_s, 2), "on_top_after": 1.0 if on_top_after else 0.0}
            conf = 0.4 + 0.3 * bool(in_clinch or close_s >= 1.0) + 0.2 * on_top_after
            out.append(_Fall(i, EventType.takedown, a1, b1, a2, b2, round(min(conf, 0.95), 3), measures, drop,
                             "Öncesinde yakın temas", []))
        else:
            out.append(_Fall(i, EventType.stance_change, a1, b1, a2, b2, 0.6, measures, drop, "Yere indi", []))
    return out


def _fall_event(fl: _Fall, ts_ms: np.ndarray) -> FightEvent:
    i = fl.fighter
    if fl.kind in (EventType.knockdown, EventType.takedown):  # credited to the other fighter
        return _event(fl.kind, 1 - i, i, fl.b1, fl.a2, fl.a2, ts_ms, fl.confidence, measures=fl.measures,
                      note=fl.note, evidence=fl.evidence)
    return _event(EventType.stance_change, i, None, fl.b1, fl.a2, fl.a2, ts_ms, fl.confidence,
                  measures=fl.measures, note=fl.note, evidence=fl.evidence)


# ---- identity inferred from the other fighter ------------------------------------

def infer_presence(arrays: PoseArrays, state: np.ndarray, det: np.ndarray, conf: np.ndarray, track_id: np.ndarray,
                   s: MotionSettings) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Copies of the identity state and detection arrays [F, 2] in which a fighter is taken to
    be the person on his tracker id next to a stretch where he is identified, while the other
    fighter is followed with high confidence on another detection; and the mask of those
    frames. Used for falls only (a knockdown found this way is marked as inferred)."""
    n = state.shape[0]
    st, dt = state.copy(), det.copy()
    mask = np.zeros((n, 2), bool)
    if n == 0 or track_id.size == 0:
        return st, dt, mask
    ts = arrays.timestamp_ms.astype(np.float64) / 1000.0
    offsets = arrays.det_offsets
    identified = (state <= 1) & (det >= 0)

    def find(t: int, tid: int) -> int:
        a, b = int(offsets[t]), int(offsets[t + 1])
        hit = np.flatnonzero(track_id[a:b] == tid)
        return a + int(hit[0]) if hit.size else -1

    for f in (0, 1):
        g = 1 - f
        other_ok = identified[:, g] & (conf[:, g] >= s.infer_min_confidence)
        idx = np.flatnonzero(identified[:, f])
        if idx.size == 0:
            continue
        breaks = np.flatnonzero(np.diff(idx) > 1)
        firsts = np.concatenate(([idx[0]], idx[breaks + 1]))
        lasts = np.concatenate((idx[breaks], [idx[-1]]))
        for edges, step in ((firsts, -1), (lasts, 1)):
            for t0 in edges.tolist():
                tid = int(track_id[det[t0, f]])
                if tid < 0:
                    continue
                t, misses = t0 + step, 0
                while 0 <= t < n and abs(ts[t] - ts[t0]) <= s.infer_window_s and not identified[t, f]:
                    d = find(t, tid) if other_ok[t] else -1
                    if d >= 0 and d != det[t, g]:
                        st[t, f], dt[t, f], mask[t, f] = 1, d, True
                        misses = 0
                    else:
                        misses += 1
                        if misses > s.infer_max_gap_frames:
                            break
                    t += step
    return st, dt, mask


def _around(mask: np.ndarray, ts: np.ndarray, pad_s: float) -> np.ndarray:
    """Frames within pad_s of a True frame."""
    idx = np.flatnonzero(mask)
    d = np.zeros(ts.size + 1, np.int64)
    np.add.at(d, np.searchsorted(ts, ts[idx] - pad_s), 1)
    np.add.at(d, np.searchsorted(ts, ts[idx] + pad_s, side="right"), -1)
    return np.cumsum(d[:-1]) > 0


def inferred_kinematics(arrays: PoseArrays, state: np.ndarray, det: np.ndarray, conf: np.ndarray,
                        track_id: np.ndarray, camera: CameraTrack, kin: tuple[FighterKinematics, FighterKinematics],
                        s: MotionSettings) -> tuple[tuple[FighterKinematics, FighterKinematics], np.ndarray]:
    """Kinematics with the presence of `infer_presence` and its mask, for `analyze(inferred=...)`.
    Computed only within `infer_context_s` of the inferred frames: they are needed for falls
    there, and for the whole video they would double the time of the stage."""
    state_x, det_x, mask = infer_presence(arrays, state, det, conf, track_id, s)
    ts = arrays.timestamp_ms.astype(np.float64) / 1000.0
    out = list(kin)
    for f in (0, 1):
        if not mask[:, f].any():
            continue
        keep = _around(mask[:, f], ts, s.infer_context_s)
        st, dt = state_x.copy(), det_x.copy()
        st[~keep, f], dt[~keep, f] = 2, -1
        out[f] = compute(arrays, st, dt, track_id, camera, f, s)
    return (out[0], out[1]), mask


def _inferred_knockdowns(arrays: PoseArrays, camera: CameraTrack, kin: tuple[FighterKinematics, FighterKinematics],
                         kin_x: tuple[FighterKinematics, FighterKinematics], inferred: np.ndarray,
                         identity_conf: np.ndarray, down: np.ndarray, ts: np.ndarray, frame_s: np.ndarray,
                         s: MotionSettings) -> list[_Fall]:
    """Knockdowns of a fighter whose identity is inferred around the fall (`infer_presence`),
    while the other fighter is followed with high confidence and stays on his feet."""
    n = ts.size
    out: list[_Fall] = []
    for i in (0, 1):
        if not inferred[:, i].any():
            continue
        g = 1 - i
        pair = (kin_x[0], kin[1]) if i == 0 else (kin[0], kin_x[1])
        dn_i, sh_i = down_mask(kin_x[i], ts, s)
        dn, share = down.copy(), np.full((2, n), np.nan)
        dn[i], share[i] = dn_i, sh_i
        posture = np.stack([k.posture for k in pair])
        up = np.stack([k.present & (k.posture == STANDING) for k in pair]) & ~dn
        dist = _distance(pair)
        clinches = _clinch_runs(ts, _both_up(posture, dn), dist, frame_s, s)
        pool: list[list[_Strike]] = [[], []]
        attacker = _fighter(pair[g], pair[i], arrays, camera)
        pool[g] = _strikes(attacker, ts, s, dn[g], dn[i], _underneath(pair[g], pair[i], dn[g], s), arrays, camera)
        for fl in _falls(i, pair, dn, up, share, ts, frame_s, pool, clinches, dist, np.zeros((2, n), bool), s):
            if fl.kind != EventType.knockdown:
                continue
            uses = inferred[fl.a1:fl.b2 + 1, i].any() or any(inferred[x.cand.peak, i] for x in fl.strikes)
            watch = slice(fl.b1, fl.a2 + 1)
            seen = kin[g].present[watch]
            confident = (seen.mean() >= 0.8 and float(np.median(identity_conf[watch, g][seen])) >= s.infer_min_confidence
                         and not dn[g, watch].any()) if seen.any() else False
            if not (uses and confident):
                continue
            fl.confidence = round(min(fl.confidence, s.inferred_confidence_cap), 3)
            fl.evidence.append(EvidenceSignal.identity_inferred)
            fl.note = f"Olası; düşen kişi diğer dövüşçü sayıldı (rakibi yüksek güvenle ayaktaydı). {fl.note}"
            out.append(fl)
    return out


# ---- events -----------------------------------------------------------------------

def _event(type_: EventType, actor: int | None, target: int | None, a: int, b: int, peak: int | None,
           ts_ms: np.ndarray, confidence: float, *, limb: Limb | None = None, contact: bool = False,
           location: ImagePoint | None = None, measures: dict[str, float] | None = None,
           note: str | None = None, evidence: list[EvidenceSignal] | None = None, zone: TargetZone | None = None,
           outcome: StrikeOutcome | None = None, outcome_confidence: float | None = None,
           significant: bool | None = None, phase: FightPhase | None = None) -> FightEvent:
    who = SHORT[actor] if actor is not None else "x"
    a, b, peak = int(a), int(b), None if peak is None else int(peak)
    return FightEvent(event_id=f"{type_.value}-{who}-{peak if peak is not None else a}", type=type_,
                      actor=FIGHTERS[actor] if actor is not None else None,
                      target=FIGHTERS[target] if target is not None else None,
                      start_frame=a, end_frame=b, start_ms=round(float(ts_ms[a]), 1), end_ms=round(float(ts_ms[b]), 1),
                      peak_frame=peak, peak_ms=round(float(ts_ms[peak]), 1) if peak is not None else None,
                      limb=limb, possible_contact=contact, location=location, measures=measures or {},
                      confidence=confidence, target_zone=zone, outcome=outcome, outcome_confidence=outcome_confidence,
                      significant=significant, phase=phase, evidence=list(evidence or []),
                      data_origin=DataOrigin.measured, note=note)


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


def _same_fall(e: FightEvent, fl: _Fall, ts_ms: np.ndarray) -> bool:
    """A fall event of the same fighter within a second of the fall."""
    who = FIGHTERS[fl.fighter]
    mine = e.target == who if e.type in (EventType.knockdown, EventType.takedown) else (
        e.type == EventType.stance_change and e.actor == who and (e.note or "").startswith("Yere indi"))
    return mine and abs((e.peak_ms if e.peak_ms is not None else e.start_ms) - float(ts_ms[fl.a2])) <= 1000.0


def analyze(arrays: PoseArrays, camera: CameraTrack, kin: tuple[FighterKinematics, FighterKinematics],
            s: MotionSettings, identity_conf: np.ndarray | None = None,
            inferred: tuple[tuple[FighterKinematics, FighterKinematics], np.ndarray] | None = None) -> Analysis:
    """`inferred`: kinematics with the presence of `infer_presence` and its mask, for falls of a
    fighter whose identity is not verified around the fall (needs `identity_conf`)."""
    ts_ms = arrays.timestamp_ms.astype(np.float64)
    ts = ts_ms / 1000.0
    n = arrays.frame_count
    frame_s = frame_seconds(ts)
    sides = tuple(_fighter(kin[i], kin[1 - i], arrays, camera) for i in range(2))
    posture = np.stack([k.posture for k in kin])
    downs = [down_mask(k, ts, s) for k in kin]
    down = np.stack([d for d, _ in downs])
    share = np.stack([sh for _, sh in downs])
    up = np.stack([k.present & (k.posture == STANDING) for k in kin]) & ~down
    distance = _distance(kin)
    both_up = _both_up(posture, down)
    clinches = _clinch_runs(ts, both_up, distance, frame_s, s)
    in_clinch = np.zeros(n, bool)
    for a, b in clinches:
        in_clinch[a:b + 1] = True
    events: list[FightEvent] = []

    # Strike attempts and what they did.
    strikes: list[list[_Strike]] = [[], []]
    for i, f in enumerate(sides):
        under = _underneath(kin[i], kin[1 - i], down[i], s)
        strikes[i] = _strikes(f, ts, s, down[i], down[1 - i], under, arrays, camera)
        for x in strikes[i]:
            c, r = x.cand, x.result
            loc = f.k.image[c.peak, c.end_joint]
            measures = dict(c.measures)
            if x.contact:  # possible impact: the opponent's head snapped right after the contact
                jolt = _head_jolt(f.opp, c.peak, ts, s)
                if jolt is not None:
                    measures["head_jolt"] = round(jolt, 3)
                    measures["impact"] = 1.0 if jolt >= s.impact_head_jolt else 0.0
            measures.update(r.measures)
            phase = _phase(c.peak, down, in_clinch)
            x.event = _event(c.type, i, 1 - i, c.start, c.end, c.peak, ts_ms, c.confidence, limb=c.limb,
                             contact=x.contact, measures=measures,
                             location=ImagePoint(x=round(float(loc[0]), 1), y=round(float(loc[1]), 1))
                             if np.isfinite(loc).all() else None,
                             zone=r.zone, outcome=r.outcome, outcome_confidence=r.confidence,
                             significant=phase == FightPhase.distance or c.strength >= s.power_strength,
                             phase=phase, evidence=r.evidence)
            events.append(x.event)

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

    for a, b in clinches:
        events.append(_event(EventType.clinch, None, None, a, b, None, ts_ms, 0.6,
                             measures={"seconds": round(float(frame_s[a:b + 1].sum()), 2)}))

    # Ground control: one fighter down, the other close and above him.
    control = np.zeros((2, n), bool)
    for top in range(2):
        bottom = 1 - top
        kt, kb = kin[top], kin[bottom]
        with np.errstate(all="ignore"):
            above = (kb.center[:, 1] - kt.center[:, 1]) >= 0.2 * kb.scale
            near = _norm(kt.center - kb.center) / kb.scale <= s.control_distance
        mask = down[bottom] & kt.valid & kb.valid & above & near
        for a, b in _runs(mask, ts, 0.3):
            secs = float(frame_s[a:b + 1].sum())
            if secs >= s.control_min_s:
                control[top, a:b + 1] = True
                events.append(_event(EventType.ground_control, top, bottom, a, b, None, ts_ms, 0.5,
                                     measures={"seconds": round(secs, 2)}, note="Tahmini; yakınlık ve duruştan"))

    # Falls and getting up.
    falls = [fl for i in range(2) for fl in _falls(i, kin, down, up, share, ts, frame_s, strikes, clinches, distance,
                                                    control, s)]
    fall_events = [_fall_event(fl, ts_ms) for fl in falls]
    if inferred is not None and identity_conf is not None:
        kin_x, mask = inferred
        for fl in _inferred_knockdowns(arrays, camera, kin, kin_x, mask, identity_conf, down, ts, frame_s, s):
            same = [e for e in fall_events if _same_fall(e, fl, ts_ms)]
            if any(e.type in (EventType.knockdown, EventType.takedown) for e in same):
                continue  # found without the inference
            # a "slip" whose strike could not be seen without the inference gives way to it
            fall_events = [e for e in fall_events if all(e is not x for x in same)]
            fall_events.append(_fall_event(fl, ts_ms))
    events += fall_events

    events.sort(key=lambda e: (e.start_ms, e.event_id))
    seen: dict[str, int] = {}
    for e in events:  # ids are type-actor-frame; make repeats unique
        seen[e.event_id] = seen.get(e.event_id, 0) + 1
        if seen[e.event_id] > 1:
            e.event_id = f"{e.event_id}-{seen[e.event_id]}"
    if identity_conf is not None:
        attribute(events, kin, identity_conf, s)
    damage = damage_mod.detect(ts_ms, kin, approach,
                               [(x.event, x.result, i) for i in range(2) for x in strikes[i] if x.event is not None],
                               events, s)
    valid = np.stack([k.valid for k in kin])
    stats = []
    for i in range(2):
        mine = [e for e in events if e.actor == FIGHTERS[i]]
        hits = [e for e in mine if e.type in STRIKE_TYPES]
        stats.append({
            "strike_attempts": sum(e.type in HAND_STRIKES for e in mine),
            "kick_attempts": sum(e.type == EventType.kick for e in mine),
            "possible_contacts": sum(e.possible_contact for e in mine),
            "landed_strikes": sum(e.outcome == StrikeOutcome.landed for e in hits),
            "significant_attempts": sum(bool(e.significant) for e in hits),
            "significant_landed": sum(bool(e.significant) and e.outcome == StrikeOutcome.landed for e in hits),
            "possible_knockdowns": sum(e.type == EventType.knockdown for e in mine),
            "possible_takedowns": sum(e.type == EventType.takedown for e in mine),
            "control_s": round(float(frame_s[control[i]].sum()), 2),
            "advance_s": round(sum(r.seconds for r in runs if r.fighter == i and r.advancing), 2),
            "retreat_s": round(sum(r.seconds for r in runs if r.fighter == i and not r.advancing), 2),
            "measured_s": round(float(frame_s[valid[i]].sum()), 2),
        })
    return Analysis(events=events, runs=runs, valid=valid, activity=activity, hand_speed=hand, foot_speed=foot,
                    approach=approach, movement=movement, posture=np.where(down, GROUNDED, posture).astype(np.int8),
                    distance=distance, frame_s=frame_s, stats=stats, damage=damage)
