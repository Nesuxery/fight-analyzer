"""Grappling states of the two verified fighters, frame by frame, and what their
transitions say (v2 Bölüm 3b). Estimates from 2D joints, never facts.

States (`state`, int8 per frame)
    DISTANCE      both on their feet, apart (also: one of them down, the other
                  away from him - nobody is grappling)
    CLINCH        both on their feet and tied up: hip centres within
                  `clinch_distance` (a clinch ends only beyond it plus
                  `clinch_exit`), for at least `clinch_min_s`, with a grip
                  (a wrist of one of them on the other's torso, within
                  `clinch_contact`, on at least `clinch_tied_share` of the
                  frames where that can be measured; where it cannot, bodies
                  pressed together) and both at the same depth: their
                  apparent sizes keep the ratio they have over the whole
                  video (within `clinch_size_ratio`). In 2D, fighters
                  trading in the pocket or one in front of the other look
                  just as close; on the tuning broadcast (no clinch work) the
                  distance rule alone found 18 "clinches", these two checks
                  leave the one real tie-up. A fighter bent down at the legs
                  of an opponent who stands upright (a shot, a single leg) is
                  standing grappling, so clinch.
    RED_TOP /     one or both down, next to each other, and red's (blue's)
    BLUE_TOP      torso centre is higher than the other's by
                  `ground_top_margin` torso lengths
    SCRAMBLE      one or both down next to each other without a clear top
    UNKNOWN (-1)  a fighter is not measured, or their apparent sizes are too far
                  apart for two fighters in the cage (beyond `identity_size_guard`
                  times their usual ratio: one identity is on someone else, a
                  spectator for instance): no state is guessed
"Down" is the same as everywhere in the motion stage (events.down_mask):
lying, sitting, on hands and knees, or the hips well below their standing
height. Only top and bottom are told apart on the ground; guard, half guard,
side control, mount and back are not (2D joints cannot separate them reliably).

Against flicker: a fighter's posture and the distance jump around from frame
to frame, so the raw per-frame states are smoothed. An unmeasured stretch
between two equal states takes that state (`state_fill_s`, longer on the
ground: `ground_fill_s`), and a state shorter than `state_min_s` between two
others is a flicker: it joins its neighbours, or becomes a scramble between two
ground states. Frames whose state was filled or changed keep a lower
confidence.

Transitions
    takedown          from a standing state to the ground within
                      `takedown_max_s` with the fighter who went down under the
                      other one, after close contact (clinch, or the fighters
                      within 1.2 x clinch_distance), and not right after a
                      knockdown. Landed when the attacker stays on top at least
                      `takedown_hold_s`; `brief` when the opponent got up or
                      came out on top before that.
    takedown_attempt  a level change into the opponent (shoulders below his,
                      hips down or torso leaning forward, close to him) that
                      did not bring him down. A fighter whose level change
                      ended with the opponent on top of him (a sprawl) made an
                      attempt; the opponent did not take him down.
    reversal          the fighter underneath comes out on top (both top
                      positions held `reversal_min_s`, the scramble between
                      them at most `reversal_max_s`)
    get_up            the fighter underneath stands up; also any rise from the
                      ground (events.py), then without an opponent on top
    submission_attempt  possible: a forearm held across the opponent's neck with
                      his head against the attacker's upper body, for at least
                      `sub_min_s`. Low confidence (`sub_max_confidence`): collar
                      ties and head control look alike in 2D. Triangles and
                      joint locks are not detected.
Control
    ground control    time on top (RED_TOP / BLUE_TOP)
    clinch control    low-confidence estimate in a separate field: in a clinch,
                      the fighter who drove the pair toward the opponent's back
                      (the opponent pinned, presumably against the cage, which
                      is not measured) until the other one drives back
    active control    control time during which the controlling fighter keeps
                      striking (`active_before_s` .. `active_after_s` around each
                      attempt) or holds a submission attempt. Holding a position
                      alone is not dominance (ABC 2025), so it is kept apart.
"""

from __future__ import annotations

import heapq
import math
from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np

from fight_analyzer.config import MotionSettings
from fight_analyzer.contracts import EventType, EvidenceSignal, FightPhase, GrapplingState

from .kinematics import LE, LH, LK, LA, LS, LW, RA, RE, RH, RK, RS, RW, STANDING, FighterKinematics, hip_height
from .series import close_holes, runs, value_runs, window_mask

UNKNOWN, DISTANCE, CLINCH, RED_TOP, BLUE_TOP, SCRAMBLE = -1, 0, 1, 2, 3, 4
TOP = (RED_TOP, BLUE_TOP)  # the state with fighter i on top
STANDING_STATES = frozenset({DISTANCE, CLINCH})
GROUND_STATES = frozenset({RED_TOP, BLUE_TOP, SCRAMBLE})
CONTRACT = {DISTANCE: GrapplingState.distance, CLINCH: GrapplingState.clinch, RED_TOP: GrapplingState.ground_red_top,
            BLUE_TOP: GrapplingState.ground_blue_top, SCRAMBLE: GrapplingState.scramble}
HEAD = (0, 1, 2, 3, 4)
LOW_JOINTS = (LS, RS, LH, RH, LK, RK, LA, RA)  # what lies on the mat when he is down (hands can post)
FILLED, CHANGED = 0.5, 0.5  # confidence factors of filled and relabelled frames


@dataclass
class Grappling:
    state: np.ndarray  # [F] int8
    conf: np.ndarray  # [F] float32, 0..1 (0 where unknown)
    clinch_by: np.ndarray  # [F] int8: fighter credited with clinch control, -1 nobody
    raw: np.ndarray  # [F] int8 per-frame state before smoothing (for checks)


@dataclass
class Found:
    """A grappling event before it becomes a FightEvent (events.py builds those)."""

    type: EventType
    actor: int | None
    target: int | None
    a: int
    b: int
    peak: int | None
    confidence: float
    measures: dict[str, float] = field(default_factory=dict)
    evidence: list[EvidenceSignal] = field(default_factory=list)
    note: str | None = None
    brief: bool | None = None


@dataclass
class Rise:
    """A fighter back on his feet (events._falls: a stable down stretch, then a stable standing one)."""

    fighter: int
    a: int  # last down frame
    b: int  # first standing frame
    confidence: float
    a1: int | None = None  # first down frame


@dataclass
class FallTakedown:
    """events._falls: a fall right after close contact (a takedown by the other fighter)."""

    fighter: int  # the one who went down
    b1: int  # last standing frame
    a2: int  # first down frame
    b2: int  # last down frame
    confidence: float


def _clip01(x: float) -> float:
    return min(1.0, max(0.0, x))


def _norm(v: np.ndarray) -> np.ndarray:
    return np.linalg.norm(v, axis=-1)


def _secs(frame_s: np.ndarray, a: int, b: int) -> float:
    return float(frame_s[a:b + 1].sum())


def phase(state: int) -> FightPhase | None:
    """Phase of a strike at a frame of this state (None: not measured)."""
    if state in STANDING_STATES:
        return FightPhase.distance if state == DISTANCE else FightPhase.clinch
    return FightPhase.ground if state in GROUND_STATES else None


# ---- body geometry ----------------------------------------------------------------

def torso_level(k: FighterKinematics) -> np.ndarray:
    """Image height (y, stabilized pixels) of the torso centre: between shoulder and hip centres,
    else whichever is measured."""
    sh, hip = k.mid(LS, RS), k.center
    out = (sh + hip) / 2
    out = np.where(np.isfinite(out), out, np.where(np.isfinite(sh), sh, hip))
    return out[:, 1]


def lean(k: FighterKinematics) -> np.ndarray:
    """Angle of the torso from upright, degrees (NaN when not measured)."""
    up = k.mid(LS, RS) - k.center
    with np.errstate(invalid="ignore"):
        return np.degrees(np.arctan2(np.abs(up[:, 0]), -up[:, 1]))


def on_mat(k: FighterKinematics, s: MotionSettings) -> np.ndarray:
    """Hips close above his lowest joint: sitting or lying (kneeling and hands-and-knees are not)."""
    joints = list(LOW_JOINTS)
    lowest = np.max(np.where(k.ok[:, joints], k.pos[:, joints, 1], -np.inf), axis=1)
    with np.errstate(invalid="ignore"):
        gap = (lowest - k.center[:, 1]) / k.scale
        return np.isfinite(gap) & (gap <= s.mat_hip)


def head_points(k: FighterKinematics) -> np.ndarray:
    """[F, 2] head centre: mean of the measured head points, else estimated above the shoulders."""
    ok = k.ok[:, list(HEAD)]
    pts = np.where(ok[..., None], k.pos[:, list(HEAD)], 0.0)
    count = ok.sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        head = np.where((count > 0)[:, None], pts.sum(axis=1) / np.maximum(count, 1)[:, None], np.nan)
    sh, hip = k.mid(LS, RS), k.center
    up = sh - hip
    n = _norm(up)
    with np.errstate(invalid="ignore", divide="ignore"):
        est = sh + 0.4 * k.scale[:, None] * up / n[:, None]
    return np.where(np.isfinite(head).all(axis=1)[:, None], head, est)


def _segment_gap(p: np.ndarray, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Distance of points p [F, 2] to segments a-b [F, 2] (NaN where unknown)."""
    ab = b - a
    with np.errstate(invalid="ignore", divide="ignore"):
        u = np.clip(np.sum((p - a) * ab, axis=1) / np.sum(ab * ab, axis=1), 0.0, 1.0)
    return _norm(p - (a + u[:, None] * ab))


# ---- per-frame states ---------------------------------------------------------------

def raw_states(kin: tuple[FighterKinematics, FighterKinematics], down: np.ndarray, distance: np.ndarray,
               s: MotionSettings, identity_conf: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Per-frame state and confidence before smoothing."""
    n = distance.size
    state = np.full(n, UNKNOWN, np.int8)
    conf = np.zeros(n, np.float32)
    valid = np.stack([k.valid for k in kin])
    scales = np.stack([k.scale for k in kin])
    count = np.isfinite(scales).sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        scale = np.where(count > 0, np.nansum(scales, axis=0) / np.maximum(count, 1), np.nan)
    level = np.stack([torso_level(k) for k in kin])
    mat = np.stack([on_mat(k, s) for k in kin])
    upright = np.stack([(k.posture == STANDING) for k in kin]) & ~down
    ratio, base = size_ratio(kin)
    with np.errstate(invalid="ignore", divide="ignore"):
        rel = ratio / base if np.isfinite(base) and base > 0 else np.ones(n)
        plausible = ~np.isfinite(rel) | ((rel <= s.identity_size_guard) & (rel >= 1 / s.identity_size_guard))
    both = valid.all(axis=0) & np.isfinite(distance) & np.isfinite(scale) & plausible
    up = ~down
    with np.errstate(invalid="ignore"):
        near = distance <= s.control_distance
        geo = np.full(n, 0.5)
        # both on their feet
        standing = both & up[0] & up[1]
        clinch = standing & (distance <= s.clinch_distance)
        state[standing] = DISTANCE
        state[clinch] = CLINCH
        geo[standing] = 0.6 + 0.4 * np.clip(np.abs(distance[standing] - s.clinch_distance) / 0.4, 0, 1)
        # one or both down, away from each other: nobody is grappling
        apart = both & (down[0] | down[1]) & ~near
        state[apart] = DISTANCE
        geo[apart] = 0.6
        close = both & (down[0] | down[1]) & near
        for i in (0, 1):
            j = 1 - i
            # bent at the legs of an opponent who stands upright: standing grappling
            shot = close & down[j] & up[i] & upright[i] & ~mat[j]
            state[shot] = CLINCH
            geo[shot] = 0.5
        sep = (level[1] - level[0]) / scale  # > 0: red higher on the screen
        ground = close & (state == UNKNOWN)
        red_top = ground & (sep >= s.ground_top_margin)
        blue_top = ground & (-sep >= s.ground_top_margin)
        state[ground] = SCRAMBLE
        state[red_top] = RED_TOP
        state[blue_top] = BLUE_TOP
        tops = red_top | blue_top
        geo[tops] = 0.5 + 0.5 * np.clip((np.abs(sep[tops]) - s.ground_top_margin) / 0.5, 0, 1)
    ident = np.full(n, 0.8)
    if identity_conf is not None and identity_conf.shape[0] == n:
        ident = np.clip(np.nan_to_num(identity_conf.min(axis=1), nan=0.0), 0.0, 1.0)
    known = state != UNKNOWN
    conf[known] = (ident * geo)[known]
    return state, conf


def _hysteresis(state: np.ndarray, distance: np.ndarray, s: MotionSettings) -> np.ndarray:
    """A clinch ends only once the fighters are beyond clinch_distance + clinch_exit."""
    out = state.copy()
    in_clinch = False
    for t in range(out.size):
        v = out[t]
        if v == UNKNOWN:
            continue
        if v == CLINCH:
            in_clinch = True
        elif v == DISTANCE and in_clinch and distance[t] <= s.clinch_distance + s.clinch_exit:
            out[t] = CLINCH
        else:
            in_clinch = False
    return out


def _fill(state: np.ndarray, conf: np.ndarray, ts: np.ndarray, s: MotionSettings) -> None:
    """Unmeasured stretches between two equal states take that state (in place)."""
    rl = value_runs(state)
    for k in range(1, len(rl) - 1):
        v, a, b = rl[k]
        before, after = rl[k - 1], rl[k + 1]
        if v != UNKNOWN or before[0] != after[0] or before[0] == UNKNOWN:
            continue
        limit = s.ground_fill_s if before[0] in GROUND_STATES else s.state_fill_s
        if ts[after[1]] - ts[before[2]] <= limit:
            state[a:b + 1] = before[0]
            conf[a:b + 1] = FILLED * min(float(conf[before[2]]), float(conf[after[1]]))


def _relabel(cur: int, p: int | None, q: int | None, sp: float, sq: float) -> int | None:
    """New state of a short run between p and q (None: unknown neighbour or edge); None: keep."""
    p = None if p == UNKNOWN else p
    q = None if q == UNKNOWN else q
    if p is None and q is None:
        new = UNKNOWN  # a short measured island in unmeasured time: too little to say anything
    elif p is None or q is None:
        new = q if p is None else p
    elif p == q:
        new = p
    elif cur in STANDING_STATES:
        standing = [(sp, p), (sq, q)]
        standing = [x for x in standing if x[1] in STANDING_STATES]
        new = max(standing)[1] if standing else SCRAMBLE
    elif cur in (RED_TOP, BLUE_TOP):
        new = SCRAMBLE if (p in GROUND_STATES or q in GROUND_STATES) else max((sp, p), (sq, q))[1]
    else:
        new = cur  # a scramble is a transition: it may be short
    return None if new == cur else new


def _merge_short(state: np.ndarray, frame_s: np.ndarray, min_s: float) -> np.ndarray:
    """Runs shorter than min_s are relabelled from the shortest up (`_relabel`); equal neighbours merge."""
    rl = value_runs(state)
    m = len(rl)
    if m < 2:
        return state.copy()
    val = [v for v, _, _ in rl]
    first = [a for _, a, _ in rl]
    last = [b for _, _, b in rl]
    sec = [_secs(frame_s, a, b) for _, a, b in rl]
    prev = list(range(-1, m - 1))
    nxt = list(range(1, m + 1))
    nxt[-1] = -1
    alive = [True] * m
    heap = [(sec[k], k) for k in range(m) if val[k] != UNKNOWN and sec[k] < min_s]
    heapq.heapify(heap)

    def absorb(k: int, nb: int) -> None:
        first[k], last[k] = min(first[k], first[nb]), max(last[k], last[nb])
        sec[k] += sec[nb]
        alive[nb] = False
        if nb == prev[k]:
            prev[k] = prev[nb]
            if prev[k] >= 0:
                nxt[prev[k]] = k
        else:
            nxt[k] = nxt[nb]
            if nxt[k] >= 0:
                prev[nxt[k]] = k

    while heap:
        d, k = heapq.heappop(heap)
        if not alive[k] or d != sec[k]:
            continue
        p, q = prev[k], nxt[k]
        new = _relabel(val[k], val[p] if p >= 0 else None, val[q] if q >= 0 else None,
                       sec[p] if p >= 0 else 0.0, sec[q] if q >= 0 else 0.0)
        if new is None:
            continue
        val[k] = new
        for nb in (prev[k], nxt[k]):
            if nb >= 0 and alive[nb] and val[nb] == val[k]:
                absorb(k, nb)
        if val[k] != UNKNOWN and sec[k] < min_s:
            heapq.heappush(heap, (sec[k], k))
    out = state.copy()
    for k in range(m):
        if alive[k]:
            out[first[k]:last[k] + 1] = val[k]
    return out


def tie_up(kin: tuple[FighterKinematics, FighterKinematics], s: MotionSettings) -> np.ndarray:
    """[F] 1 when a wrist of one fighter is on the other's torso (mid-shoulders to mid-hips, within
    `clinch_contact` of his torso lengths): a grip; 0 when none is; NaN when it cannot be measured.
    (Elbows, the head and the thighs were tried on the tuning broadcast: in 2D, guards and hands
    at the waist of fighters trading in the pocket come that close to the other one all the time.)"""
    n = kin[0].present.size
    known = np.zeros(n, bool)
    tied = np.zeros(n, bool)
    for i in (0, 1):
        k, o = kin[i], kin[1 - i]
        sh, hip = o.mid(LS, RS), o.center
        for j in (LW, RW):
            with np.errstate(invalid="ignore", divide="ignore"):
                gap = _segment_gap(k.pos[:, j], sh, hip) / o.scale
            ok = k.ok[:, j] & o.present & np.isfinite(gap)
            known |= ok
            with np.errstate(invalid="ignore"):
                tied |= ok & (gap <= s.clinch_contact)
    return np.where(known, tied.astype(np.float64), np.nan)


def size_ratio(kin: tuple[FighterKinematics, FighterKinematics]) -> tuple[np.ndarray, float]:
    """[F] red's apparent torso length over blue's, and its median while both are measured (the
    ratio of their real sizes, as the camera sees them at all depths)."""
    with np.errstate(invalid="ignore", divide="ignore"):
        ratio = kin[0].scale / kin[1].scale
    both = kin[0].valid & kin[1].valid & np.isfinite(ratio)
    return ratio, float(np.median(ratio[both])) if both.any() else math.nan


def _confirm_clinches(state: np.ndarray, kin: tuple[FighterKinematics, FighterKinematics], distance: np.ndarray,
                      s: MotionSettings) -> None:
    """A clinch needs both fighters at the same depth and a grip on most measurable frames (where
    grips cannot be measured on enough of them, bodies pressed together); in place."""
    tie = tie_up(kin, s)
    ratio, base = size_ratio(kin)
    for v, a, b in value_runs(state):
        if v != CLINCH:
            continue
        r = ratio[a:b + 1]
        r = r[np.isfinite(r)]
        same_depth = True
        if r.size and math.isfinite(base) and base > 0:
            rel = float(np.median(r)) / base
            same_depth = 1 / s.clinch_size_ratio <= rel <= s.clinch_size_ratio
        part = tie[a:b + 1]
        measured = np.isfinite(part)
        if measured.mean() >= 0.2:
            grip = float(part[measured].mean()) >= s.clinch_tied_share
        else:
            d = distance[a:b + 1]
            grip = bool(np.isfinite(d).any()) and float(np.nanmedian(d)) <= s.clinch_pressed
        if not (same_depth and grip):
            state[a:b + 1] = DISTANCE


def _short_clinches(state: np.ndarray, frame_s: np.ndarray, s: MotionSettings) -> None:
    """Close range for less than clinch_min_s between stretches at distance is an exchange, not a clinch."""
    rl = value_runs(state)
    for k, (v, a, b) in enumerate(rl):
        if v != CLINCH or _secs(frame_s, a, b) >= s.clinch_min_s:
            continue
        nbs = [rl[x][0] for x in (k - 1, k + 1) if 0 <= x < len(rl)]
        if all(x in (DISTANCE, UNKNOWN) for x in nbs):
            state[a:b + 1] = DISTANCE


def clinch_control(state: np.ndarray, approach: np.ndarray, ts: np.ndarray, frame_s: np.ndarray,
                   s: MotionSettings) -> np.ndarray:
    """[F] fighter credited with clinch control (-1: nobody): in each clinch, the one who last drove
    the pair toward the opponent's back, until the other drives back."""
    n = state.size
    out = np.full(n, -1, np.int8)
    with np.errstate(invalid="ignore"):
        drive = (approach[0] - approach[1]) / 2  # > 0: red moves in while blue gives way
    in_clinch = state == CLINCH
    starts = np.full(n, -1, np.int8)
    for i, sign in ((0, 1.0), (1, -1.0)):
        with np.errstate(invalid="ignore"):
            mask = in_clinch & np.isfinite(drive) & (sign * drive >= s.clinch_drive_speed)
        for a, b in runs(close_holes(mask, ts, 0.15) & in_clinch, ts, 0.3):
            if _secs(frame_s, a, b) >= s.clinch_drive_min_s:
                starts[a:b + 1] = i
    for _, a, b in [r for r in value_runs(state) if r[0] == CLINCH]:
        who = -1
        for t in range(a, b + 1):
            if starts[t] >= 0:
                who = starts[t]
            out[t] = who
    return out


def states(ts: np.ndarray, frame_s: np.ndarray, kin: tuple[FighterKinematics, FighterKinematics],
           down: np.ndarray, distance: np.ndarray, approach: np.ndarray, s: MotionSettings,
           identity_conf: np.ndarray | None = None) -> Grappling:
    raw, raw_conf = raw_states(kin, down, distance, s, identity_conf)
    state = _hysteresis(raw, distance, s)
    conf = raw_conf.copy()
    _fill(state, conf, ts, s)
    state = _merge_short(state, frame_s, s.state_min_s)
    _short_clinches(state, frame_s, s)
    state = _merge_short(state, frame_s, s.state_min_s)
    _confirm_clinches(state, kin, distance, s)
    changed = (state != raw) & (raw != UNKNOWN)
    conf[changed] *= CHANGED
    conf[state == UNKNOWN] = 0.0
    return Grappling(state=state.astype(np.int8), conf=conf.astype(np.float32),
                     clinch_by=clinch_control(state, approach, ts, frame_s, s), raw=raw)


# ---- control ------------------------------------------------------------------------

def control_masks(state: np.ndarray, clinch_by: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """[2, F] on top on the ground, [2, F] credited with clinch control."""
    top = np.stack([state == TOP[i] for i in (0, 1)])
    clinch = np.stack([(state == CLINCH) & (clinch_by == i) for i in (0, 1)])
    return top, clinch


def active_control(state: np.ndarray, clinch_by: np.ndarray, ts: np.ndarray,
                   strike_moments: Sequence[np.ndarray], holds: Sequence[Sequence[tuple[float, float]]],
                   s: MotionSettings) -> np.ndarray:
    """[2, F] control (on top or clinch control) while the controlling fighter keeps striking
    (`strike_moments[i]`, seconds) or holds a submission attempt (`holds[i]`, (start, end) seconds)."""
    top, clinch = control_masks(state, clinch_by)
    out = np.zeros((2, state.size), bool)
    for i in (0, 1):
        offense = window_mask(ts, np.asarray(strike_moments[i], np.float64), s.active_before_s, s.active_after_s)
        for a, b in holds[i]:
            offense |= (ts >= a) & (ts <= b)
        out[i] = (top[i] | clinch[i]) & offense
    return out


# ---- transitions ----------------------------------------------------------------------

@dataclass
class _Hold:
    """On the ground with one fighter on top (short scrambles of the same top included)."""

    top: int
    a: int  # first frame on top
    b: int  # last frame on top
    top_s: float  # seconds on top (scrambles inside not counted)
    conf: float


@dataclass
class _Sequence:
    """A stretch on the ground between standing states (or the edges of the measurement)."""

    a: int
    b: int
    holds: list[_Hold]
    before: tuple[int, int, int] | None  # standing run right before (state, first, last)
    after: tuple[int, int, int] | None  # standing run right after
    gap_before_s: float  # unmeasured time between the standing run before and the ground
    gap_after_s: float


def _sequences(g: Grappling, ts: np.ndarray, frame_s: np.ndarray, s: MotionSettings) -> list[_Sequence]:
    rl = value_runs(g.state)
    out: list[_Sequence] = []
    k = 0
    while k < len(rl):
        if rl[k][0] not in GROUND_STATES:
            k += 1
            continue
        j = k
        # extend over ground states and short unmeasured stretches
        while j + 1 < len(rl):
            v, a, b = rl[j + 1]
            if v in GROUND_STATES:
                j += 1
            elif v == UNKNOWN and j + 2 < len(rl) and rl[j + 2][0] in GROUND_STATES \
                    and ts[rl[j + 2][1]] - ts[rl[j][2]] <= s.takedown_max_s:
                j += 2
            else:
                break
        a, b = rl[k][1], rl[j][2]
        before = after = None
        gap_before = gap_after = math.inf
        if k >= 1 and rl[k - 1][0] in STANDING_STATES:
            before, gap_before = rl[k - 1], float(ts[a] - ts[rl[k - 1][2]])
        elif k >= 2 and rl[k - 1][0] == UNKNOWN and rl[k - 2][0] in STANDING_STATES:
            before, gap_before = rl[k - 2], float(ts[a] - ts[rl[k - 2][2]])
        if j + 1 < len(rl) and rl[j + 1][0] in STANDING_STATES:
            after, gap_after = rl[j + 1], float(ts[rl[j + 1][1]] - ts[b])
        elif j + 2 < len(rl) and rl[j + 1][0] == UNKNOWN and rl[j + 2][0] in STANDING_STATES:
            after, gap_after = rl[j + 2], float(ts[rl[j + 2][1]] - ts[b])
        holds: list[_Hold] = []
        for v, x, y in rl[k:j + 1]:
            if v not in TOP:
                continue
            top = TOP.index(v)
            secs = _secs(frame_s, x, y)
            c = float(np.mean(g.conf[x:y + 1]))
            last = holds[-1] if holds else None
            if last is not None and last.top == top and ts[x] - ts[last.b] <= s.reversal_max_s:
                w = last.top_s + secs
                last.conf = (last.conf * last.top_s + c * secs) / max(w, 1e-9)
                last.b, last.top_s = y, w
            else:
                holds.append(_Hold(top, x, y, secs, c))
        out.append(_Sequence(a, b, holds, before, after, gap_before, gap_after))
        k = j + 1
    return out


def level_changes(kin: tuple[FighterKinematics, FighterKinematics], down: np.ndarray, distance: np.ndarray,
                  state: np.ndarray, ts: np.ndarray, s: MotionSettings,
                  standing_ref: Sequence[np.ndarray]) -> list[np.ndarray]:
    """[F] bool per fighter: he drops his level into the opponent (a shot) while the opponent stands."""
    out = []
    for i in (0, 1):
        k, o = kin[i], kin[1 - i]
        with np.errstate(invalid="ignore", divide="ignore"):
            drop = (k.mid(LS, RS)[:, 1] - o.mid(LS, RS)[:, 1]) / o.scale
            share = hip_height(k) / standing_ref[i]
            bent = (np.isfinite(share) & (share <= s.shot_hip_share)) | (lean(k) >= s.shot_lean_deg)
            mask = (k.valid & o.valid & ~down[1 - i] & (drop >= s.shot_drop) & bent & ~on_mat(k, s)
                    & (distance <= s.shot_distance) & (state != UNKNOWN) & ~np.isin(state, list(GROUND_STATES)))
        out.append(mask)
    return out


def _shots(mask: np.ndarray, ts: np.ndarray, frame_s: np.ndarray, s: MotionSettings,
           own_strikes: np.ndarray, own_down: np.ndarray, distance: np.ndarray) -> list[tuple[int, int]]:
    """Level-change episodes of one fighter: long enough, starting from his feet (not from the
    ground after a knockdown), reaching the opponent (a duck at distance is no shot), not just
    bobbing while punching."""
    out = []
    for a, b in runs(close_holes(mask, ts, 0.2), ts, 0.3):
        secs = _secs(frame_s, a, b)
        if secs < s.shot_min_s or own_down[int(np.searchsorted(ts, ts[a] - 0.5)):a + 1].any():
            continue
        with np.errstate(invalid="ignore"):
            contact = frame_s[a:b + 1][distance[a:b + 1] <= s.clinch_distance].sum()
        if contact < 0.2:
            continue
        punching = ((own_strikes >= ts[a] - 0.2) & (own_strikes <= ts[b] + 0.2)).any()
        if punching and secs < 0.6:
            continue
        out.append((a, b))
    merged: list[tuple[int, int]] = []
    for a, b in out:
        if merged and ts[a] - ts[merged[-1][1]] < s.attempt_gap_s:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    return merged


def transitions(g: Grappling, ts: np.ndarray, frame_s: np.ndarray, kin: tuple[FighterKinematics, FighterKinematics],
                down: np.ndarray, distance: np.ndarray, s: MotionSettings, *,
                knockdowns: Sequence[tuple[int, int]] = (), fall_takedowns: Sequence[FallTakedown] = (),
                rises: Sequence[Rise] = (), strike_moments: Sequence[np.ndarray] = (np.zeros(0), np.zeros(0)),
                standing_ref: Sequence[np.ndarray] | None = None) -> list[Found]:
    """Takedowns (landed / brief), takedown attempts, reversals, get-ups, ground control and clinches.
    `knockdowns`: (fighter who went down, first down frame) of the knockdowns; `fall_takedowns` and
    `rises` come from events._falls."""
    found: list[Found] = []
    seqs = _sequences(g, ts, frame_s, s)
    mat = [on_mat(k, s) for k in kin]

    def on_mat_s(i: int, a: int, b: int) -> float:
        """Seconds he spent with the hips on the mat (sitting, lying) on frames a..b."""
        return float(frame_s[a:b + 1][mat[i][a:b + 1]].sum()) if b >= a else 0.0

    shots = [] if standing_ref is None else level_changes(kin, down, distance, g.state, ts, s, standing_ref)
    episodes = [_shots(shots[i], ts, frame_s, s, np.asarray(strike_moments[i]), down[i], distance) if shots else []
                for i in (0, 1)]

    def knocked(fighter: int, t0: float, t1: float) -> bool:
        return any(f == fighter and t0 - 1.0 <= ts[a2] <= t1 + 1.0 for f, a2 in knockdowns)

    def close_seconds(t0: float, t1: float) -> float:
        with np.errstate(invalid="ignore"):
            near = (ts >= t0) & (ts <= t1) & (distance <= s.clinch_distance * 1.2)
        return float(frame_s[near].sum())

    takedowns: list[Found] = []
    for q in seqs:
        if q.before is None or q.gap_before_s > s.takedown_max_s or not q.holds:
            continue
        h = q.holds[0]
        if ts[h.a] - ts[q.before[2]] > s.takedown_max_s:
            continue  # scrambled on the ground too long before anybody was on top
        x, y = h.top, 1 - h.top
        end = q.before[2]
        t_end, t_land = float(ts[end]), float(ts[q.a])
        if knocked(y, t_end, t_land):
            continue  # down from a strike: a knockdown, not a takedown
        from_clinch = q.before[0] == CLINCH
        close_s = close_seconds(t_end - s.takedown_window_s, t_land)
        if not from_clinch and close_s < 0.5:
            continue  # no contact before: he went down on his own (a slip, or he sat down)
        # his own level change ended under the opponent: a stuffed shot, not a takedown by the other one
        if any(ts[a] <= t_land and ts[b] >= t_end - 1.0 for a, b in episodes[y]) and not any(
                ts[a] <= t_land and ts[b] >= t_end - 1.0 for a, b in episodes[x]):
            continue
        landed = h.top_s >= s.takedown_hold_s
        ground_s = float(ts[q.b] - ts[q.a] + frame_s[q.b])
        # how the attacker's top position ended: the other one came out on top, or got up
        other = next((x2 for x2 in q.holds[1:] if x2.top != x), None)
        if other is not None:
            escaped_at: float | None = float(ts[other.a])
        elif q.after is not None and q.gap_after_s <= s.takedown_max_s:
            escaped_at = float(ts[q.after[1]])
        else:
            escaped_at = None  # the recording or the measurement ended first
        brief: bool | None = False
        if not landed:
            brief = None if escaped_at is None else escaped_at - t_land < s.takedown_hold_s + 1.0
        conf = 0.45 + 0.15 * from_clinch + 0.15 * landed + 0.1 * h.conf
        if brief:
            conf = min(conf, 0.45)
        elif brief is None:
            conf = min(conf, 0.55)
        evidence = [EvidenceSignal.close_contact, EvidenceSignal.hip_drop]
        if h.top_s > 0:
            evidence.append(EvidenceSignal.top_position)
        note = ("Kısa: rakip hemen kalktı ya da üste çıktı" if brief
                else "Üstte kalma süresi ölçülemeden kayıt ya da ölçüm kesildi" if brief is None else None)
        takedowns.append(Found(EventType.takedown, x, y, end, max(q.a, h.b), q.a, round(min(conf, 0.85), 3),
                               {"top_s": round(h.top_s, 2), "ground_s": round(ground_s, 2),
                                "close_s": round(close_s, 2), "from_clinch": 1.0 if from_clinch else 0.0,
                                "transition_s": round(t_land - t_end, 2)},
                               evidence, note, brief))
    # Falls after close contact that the states do not show as a takedown (the ground was not
    # measured well enough): kept as possible takedowns with low confidence.
    for fl in fall_takedowns:
        x, y = 1 - fl.fighter, fl.fighter
        t2 = ts[fl.a2]
        if any(td.target == y and abs(ts[td.peak] - t2) <= 2.0 for td in takedowns):
            continue
        after = g.state[fl.a2:int(np.searchsorted(ts, t2 + 2.0, side="right"))]
        if np.isin(after, list(TOP)).any() or knocked(y, ts[fl.b1], t2):
            continue  # a top position was measured: the states decided (above), or he was knocked down
        if any(ts[a] <= t2 and ts[b] >= ts[fl.b1] - 1.0 for a, b in episodes[y]):
            continue  # his own level change took him down: a stuffed shot
        if on_mat_s(y, fl.a2, int(np.searchsorted(ts, t2 + 2.0, side="right")) - 1) < 0.3:
            continue  # bent over (a wrestler's level change), not brought down to the mat
        up_again = (np.isin(after, list(STANDING_STATES))).any()
        takedowns.append(Found(
            EventType.takedown, x, y, fl.b1, fl.a2, fl.a2, round(min(fl.confidence, 0.45), 3),
            {"top_s": 0.0, "close_s": 0.0}, [EvidenceSignal.close_contact, EvidenceSignal.hip_drop],
            "Olası; yere iniş görüldü, üst pozisyon ölçülemedi", True if up_again else None))
    found += takedowns

    # Level changes that brought nobody down: takedown attempts.
    for i in (0, 1):
        for a, b in episodes[i]:
            if any(td.actor == i and ts[a] - 0.5 <= ts[td.peak] <= ts[b] + s.takedown_max_s for td in takedowns):
                continue  # this attempt landed
            k, o = kin[i], kin[1 - i]
            with np.errstate(invalid="ignore"):
                drop = (k.mid(LS, RS)[a:b + 1, 1] - o.mid(LS, RS)[a:b + 1, 1]) / o.scale[a:b + 1]
            p = a + int(np.nanargmax(drop)) if np.isfinite(drop).any() else a
            secs = _secs(frame_s, a, b)
            conf = 0.3 + 0.1 * min(1.0, secs / 1.0) + 0.1 * (g.state[p] == CLINCH)
            found.append(Found(EventType.takedown_attempt, i, 1 - i, a, b, p, round(min(conf, 0.5), 3),
                               {"seconds": round(secs, 2), "drop": round(float(np.nanmax(drop)), 2)
                                if np.isfinite(drop).any() else 0.0},
                               [EvidenceSignal.level_change, EvidenceSignal.close_contact],
                               "Olası; seviye değişimi ve yakın temas, rakip ayakta kaldı"))

    # Reversals and getting up from underneath.
    for q in seqs:
        for h1, h2 in zip(q.holds, q.holds[1:]):
            if h1.top == h2.top or ts[h2.a] - ts[h1.b] > s.reversal_max_s:
                continue
            if h1.top_s < s.reversal_min_s or h2.top_s < s.reversal_min_s:
                continue
            conf = 0.3 + 0.3 * min(h1.conf, h2.conf)
            found.append(Found(EventType.reversal, h2.top, h1.top, h1.b, h2.a, h2.a, round(min(conf, 0.6), 3),
                               {"before_s": round(h1.top_s, 2), "after_s": round(h2.top_s, 2)},
                               [EvidenceSignal.position_change, EvidenceSignal.top_position]))
        if q.after is None or q.gap_after_s > s.takedown_max_s:
            continue
        first_up = q.after[1]
        # on his feet for a moment: the top fighter stepping away from a fighter still down is
        # "distance" too, and that fighter has not got up yet
        stand = slice(first_up, int(np.searchsorted(ts, ts[first_up] + s.posture_stable_s, side="right")))

        def stood(i: int) -> bool:
            return bool(kin[i].present[stand].any()) and not down[i, stand].any()

        if q.holds:
            h = q.holds[-1]
            riser = 1 - h.top
            if stood(riser):
                bottom_s = sum(x.top_s for x in q.holds if x.top == h.top)
                found.append(Found(EventType.get_up, riser, h.top, q.b, first_up, first_up,
                                   round(0.35 + 0.3 * h.conf, 3),
                                   {"bottom_s": round(bottom_s, 2), "from_bottom": 1.0}, [],
                                   "Alttan ayağa kalktı"))
        else:
            t0 = float(ts[q.b]) - 0.5
            for i in (0, 1):
                if down[i, int(np.searchsorted(ts, t0)):q.b + 1].any() and stood(i):
                    found.append(Found(EventType.get_up, i, None, q.b, first_up, first_up, 0.45,
                                       {"from_bottom": 0.0}, [], "Ayağa kalktı"))
    # Rises the states did not see as leaving the ground (e.g. after a slip or a knockdown).
    for r in rises:
        if any(f.type == EventType.get_up and f.actor == r.fighter and abs(ts[f.peak] - ts[r.b]) <= 2.0
               for f in found):
            continue
        lo = int(np.searchsorted(ts, ts[r.a] - 1.5))
        if (g.state[int(np.searchsorted(ts, ts[r.a] - 1.0)):r.a + 1] == TOP[r.fighter]).any():
            continue  # standing up from the top position is no getting up
        under = (g.state[lo:r.a + 1] == TOP[1 - r.fighter]).any()
        first = r.a1 if r.a1 is not None else r.a
        if not under and on_mat_s(r.fighter, first, r.a) < 0.3:
            continue  # he was bent over or crouching (a level change in a clinch), never down on the mat
        if not under and kin[1 - r.fighter].present[first:r.a + 1].mean() < 0.5:
            # the opponent was hidden (tied up with him, one skeleton for both): what looked like the
            # hips on the mat may be the other fighter's joints, and whose position it was is unknown
            continue
        found.append(Found(EventType.get_up, r.fighter, 1 - r.fighter if under else None, r.a, r.b, r.b,
                           r.confidence, {"from_bottom": 1.0 if under else 0.0}, [],
                           "Alttan ayağa kalktı" if under else "Ayağa kalktı"))

    # Ground control (on top) and clinches.
    for v, a, b in value_runs(g.state):
        secs = _secs(frame_s, a, b)
        if v in TOP and secs >= s.control_min_s:
            i = TOP.index(v)
            found.append(Found(EventType.ground_control, i, 1 - i, a, b, None,
                               round(min(0.7, 0.3 + 0.4 * float(np.mean(g.conf[a:b + 1]))), 3),
                               {"seconds": round(secs, 2)}, [EvidenceSignal.top_position],
                               "Tahmini; durum makinesinden (yerde üstte)"))
        elif v == CLINCH and secs >= s.clinch_min_s:
            by = g.clinch_by[a:b + 1]
            fs = frame_s[a:b + 1]
            found.append(Found(EventType.clinch, None, None, a, b, None, 0.6,
                               {"seconds": round(secs, 2), "red_control_s": round(float(fs[by == 0].sum()), 2),
                                "blue_control_s": round(float(fs[by == 1].sum()), 2)}))
    return found


# ---- submissions --------------------------------------------------------------------

def neck_wraps(kin: tuple[FighterKinematics, FighterKinematics], state: np.ndarray,
               s: MotionSettings) -> tuple[list[np.ndarray], list[np.ndarray], list[np.ndarray]]:
    """Per attacker: [F] bool his forearm is across the opponent's neck with the opponent's head
    against his upper body; [F] the forearm's gap to the neck (torso lengths); [F] hands together."""
    wraps, gaps, locked = [], [], []
    for i in (0, 1):
        k, o = kin[i], kin[1 - i]
        head = head_points(o)
        neck = o.mid(LS, RS) + 0.4 * (head - o.mid(LS, RS))
        best = np.full(state.size, np.nan)
        for el, wr in ((LE, LW), (RE, RW)):
            e, w = k.pos[:, el], k.pos[:, wr]
            fore = w - e
            n = _norm(fore)
            with np.errstate(invalid="ignore", divide="ignore"):
                glove = w + s.fist_reach * k.scale[:, None] * fore / n[:, None]
                gap = _segment_gap(neck, e, glove) / o.scale
            best = np.fmin(best, gap)
        with np.errstate(invalid="ignore"):
            head_close = _norm(head - k.mid(LS, RS)) / o.scale <= s.sub_head_close
            hands = _norm(k.pos[:, LW] - k.pos[:, RW]) / k.scale <= 0.6
            context = (state != UNKNOWN) & (state != DISTANCE)
            wraps.append(k.present & o.present & context & head_close & (best <= s.sub_neck_reach))
        gaps.append(best)
        locked.append(hands)
    both = wraps[0] & wraps[1]  # each one's arm around the other's neck: cannot be told apart
    return [w & ~both for w in wraps], gaps, locked


def submissions(g: Grappling, kin: tuple[FighterKinematics, FighterKinematics], ts: np.ndarray,
                frame_s: np.ndarray, s: MotionSettings) -> list[Found]:
    """Possible submission attempts: a neck wrap held at least sub_min_s."""
    wraps, gaps, locked = neck_wraps(kin, g.state, s)
    out = []
    for i in (0, 1):
        for a, b in runs(close_holes(wraps[i], ts, s.sub_close_s), ts, s.sub_close_s):
            secs = _secs(frame_s, a, b)
            if secs < s.sub_min_s:
                continue
            seg = gaps[i][a:b + 1]
            p = a + int(np.nanargmin(seg)) if np.isfinite(seg).any() else (a + b) // 2
            lock = float(np.mean(locked[i][a:b + 1]))
            ground = float(np.mean(np.isin(g.state[a:b + 1], list(GROUND_STATES))))
            conf = 0.15 + 0.1 * min(1.0, secs / 4.0) + 0.1 * lock + 0.05 * (ground >= 0.5)
            out.append(Found(EventType.submission_attempt, i, 1 - i, a, b, p,
                             round(min(s.sub_max_confidence, conf), 3),
                             {"seconds": round(secs, 2), "hands_together": round(lock, 2),
                              "neck_gap": round(float(np.nanmin(seg)), 3) if np.isfinite(seg).any() else 0.0,
                              "on_ground": round(ground, 2)},
                             [EvidenceSignal.neck_wrap],
                             "Olası; kol rakibin boynunun çevresinde tutuldu (boğma girişimi olabilir)"))
    return out


# ---- summaries ----------------------------------------------------------------------

def phase_seconds(state: np.ndarray, frame_s: np.ndarray) -> dict[str, float]:
    """Seconds in each state (whole video)."""
    def secs(mask: np.ndarray) -> float:
        return round(float(frame_s[mask].sum()), 2)
    return {"distance_s": secs(state == DISTANCE), "clinch_s": secs(state == CLINCH),
            "ground_s": secs((state == RED_TOP) | (state == BLUE_TOP)), "scramble_s": secs(state == SCRAMBLE),
            "unknown_s": secs(state == UNKNOWN)}
