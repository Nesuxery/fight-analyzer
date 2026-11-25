"""What the result screen shows at every frame, computed the way the browser does.

This mirrors frontend/src/model/measured.ts and frontend/src/player/effects.ts:
the same inputs (the API contracts: events, motion samples, momentum ledger),
the same order of floating-point operations and JavaScript rounding
(Math.round = half up). The MP4 and the CSV therefore show the percentages and
counters the browser shows on the same frame. Both test suites check the
golden file shared/fixtures/frame-metrics.json.

Statistics refer to the presented frame: t(frame) = frame * 1000 / fps ms, and
an event counts from its peak frame (start frame when it has no peak) on.
Excluded parts (motion/exclusions.py, taken from the momentum timeline so they
are the ones the ledger used) are not fight time: their events are not counted,
their samples are not measurements and the momentum decays on fight time.
"""

from __future__ import annotations

import math
from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from fight_analyzer.contracts import (
    EventType,
    EvidenceSignal,
    ExcludedSegment,
    FightEvent,
    FighterId,
    MomentumContribution,
    MomentumTimeline,
    MotionTimeline,
)
from fight_analyzer.motion import exclusions as excl

from .style import OverlayStyle

LN2 = math.log(2)
MIN_SHARE_SAMPLES_S = 3  # shares from fewer measured seconds are noise -> empty
SIDES = ("red", "blue")
FIGHTER = {"red": FighterId.fighter_a, "blue": FighterId.fighter_b}
STRIKES = {EventType.punch, EventType.kick, EventType.knee, EventType.elbow, EventType.ground_strike}
HAND_STRIKES = {EventType.punch, EventType.knee, EventType.elbow, EventType.ground_strike}  # "Vuruş denemeleri"
MAJOR = {EventType.knockdown, EventType.takedown}


def js_round(x):
    """Math.round of JavaScript (ties toward +infinity), scalar or array."""
    r = np.floor(x)
    out = r + ((x - r) >= 0.5)
    return int(out) if np.ndim(out) == 0 else out


def frame_ms(frame, fps: float):
    return frame * 1000 / fps


def sample_at(sample_ms: Sequence[float], t_ms: float) -> int:
    """Index of the sample covering t (last sample at or before t; 0 before the first)."""
    if len(sample_ms) == 0:
        return -1
    return max(0, bisect_right(sample_ms, t_ms) - 1)


def event_frame(e: FightEvent) -> int:
    return e.peak_frame if e.peak_frame is not None else e.start_frame


# ---- momentum ----------------------------------------------------------------

def momentum_totals(contribs: Sequence[MomentumContribution], t_ms: np.ndarray, half_life_s: float,
                    iv: excl.Intervals = ()) -> np.ndarray:
    """[2, n] decayed points of red and blue at each time (on fight time). Each element
    accumulates the ledger in its order, exactly like `totals()` of measured.ts."""
    iv = list(iv)
    t = excl.fight_ms_array(np.asarray(t_ms, dtype=np.float64), iv) / 1000
    lam = LN2 / half_life_s
    m = np.zeros((2, t.size))
    for c in contribs:
        start = excl.fight_ms(c.start_ms, iv) / 1000
        end = excl.fight_ms(c.end_ms, iv) / 1000
        with np.errstate(over="ignore"):
            if end <= start:
                v = c.points * np.exp(-lam * (t - start))
            else:
                rate = c.points / (end - start)
                upto = np.minimum(np.maximum(t, start), end)
                v = (rate / lam) * (np.exp(-lam * (t - upto)) - np.exp(-lam * (t - start)))
        v = np.where(t < start, 0.0, v)
        m[0 if c.fighter_id == FighterId.fighter_a else 1] += v
    return m


def red_share(m_red, m_blue, prior: float):
    return (100 * (m_red + prior)) / (m_red + m_blue + 2 * prior)


# ---- statistics --------------------------------------------------------------

@dataclass
class MotionSums:
    """Prefix sums over the motion samples (motionSums of measured.ts)."""

    hz: float
    count: int
    act: dict[str, np.ndarray]
    act_n: dict[str, np.ndarray]
    adv: dict[str, np.ndarray]
    ret: dict[str, np.ndarray]
    move_n: dict[str, np.ndarray]
    valid: dict[str, np.ndarray]


def motion_sums(motion: MotionTimeline, iv: excl.Intervals = ()) -> MotionSums:
    """Samples inside excluded parts count as not measured."""
    n = len(motion.sample_ms)
    skip = [excl.in_intervals(t, list(iv)) for t in motion.sample_ms]
    sums = MotionSums(hz=motion.sample_hz, count=n, act={}, act_n={}, adv={}, ret={}, move_n={}, valid={})
    for f in motion.fighters:
        side = "red" if f.fighter_id == FighterId.fighter_a else "blue"
        act = [0.0] * (n + 1)
        act_n, adv, ret, move_n, valid = ([0] * (n + 1) for _ in range(5))
        for i in range(n):
            a, mv, ok = (None, None, False) if skip[i] else (f.activity[i], f.movement[i], f.valid[i])
            act[i + 1] = act[i] + (a if a is not None else 0)  # sequential, as in JS
            act_n[i + 1] = act_n[i] + (0 if a is None else 1)
            adv[i + 1] = adv[i] + (1 if mv == "advancing" else 0)
            ret[i + 1] = ret[i] + (1 if mv == "retreating" else 0)
            move_n[i + 1] = move_n[i] + (1 if mv else 0)
            valid[i + 1] = valid[i] + (1 if ok else 0)
        sums.act[side] = np.array(act)
        for name, values in (("act_n", act_n), ("adv", adv), ("ret", ret), ("move_n", move_n), ("valid", valid)):
            getattr(sums, name)[side] = np.array(values, dtype=np.int64)
    for side in SIDES:  # a fighter missing from the timeline was never measured
        if side not in sums.act:
            sums.act[side] = np.zeros(n + 1)
            for name in ("act_n", "adv", "ret", "move_n", "valid"):
                getattr(sums, name)[side] = np.zeros(n + 1, dtype=np.int64)
    return sums


STAT_COLUMNS = ("strike_attempts", "kick_attempts", "possible_contacts", "knockdowns", "takedowns", "significant",
                "activity", "pressure", "advance", "retreat", "control_s", "measured_s")


def side_stats(side: str, frames: np.ndarray, t_ms: np.ndarray, events: Sequence[FightEvent],
               sums: MotionSums, segments: Sequence[ExcludedSegment] = (),
               iv: excl.Intervals = ()) -> dict[str, np.ndarray]:
    """measuredStats/measuredSeconds of measured.ts for every frame; NaN = not enough data ("—")."""
    fighter = FIGHTER[side]
    # events seen only by inferring the opponent's identity are listed, not counted (as in measured.ts)
    mine = [e for e in events if e.actor == fighter and not excl.frame_excluded(event_frame(e), segments)
            and not (e.attribution_uncertain and EvidenceSignal.identity_inferred in e.evidence)]

    def count(pred) -> np.ndarray:
        at = np.sort(np.array([event_frame(e) for e in mine if pred(e)], dtype=np.int64))
        return np.searchsorted(at, frames, side="right").astype(np.int64)

    upto = np.minimum(sums.count, np.maximum(0, np.floor(t_ms / 1000 * sums.hz).astype(np.int64) + 1))
    act_n = sums.act_n[side][upto]
    move_n = sums.move_n[side][upto]
    adv = sums.adv[side][upto]
    ret = sums.ret[side][upto]
    moving = adv + ret

    def enough(samples: np.ndarray) -> np.ndarray:
        return samples / sums.hz >= MIN_SHARE_SAMPLES_S

    with np.errstate(divide="ignore", invalid="ignore"):
        activity = np.where(enough(act_n), js_round((sums.act[side][upto] / act_n) * 100), np.nan)
        pressure = np.where(enough(move_n), js_round((adv / move_n) * 100), np.nan)
        advance = np.where(enough(move_n), np.where(moving > 0, js_round((adv / moving) * 100), 0), np.nan)
        retreat = np.where(enough(move_n), np.where(moving > 0, js_round((ret / moving) * 100), 0), np.nan)
    control = np.zeros(frames.size)
    for e in mine:  # list order, as the browser sums them
        if e.type != EventType.ground_control:
            continue
        part = _outside_ms(e.start_ms, np.minimum(e.end_ms, t_ms), list(iv)) / 1000
        control = control + np.where(event_frame(e) <= frames, part, 0.0)
    return {
        "strike_attempts": count(lambda e: e.type in HAND_STRIKES),
        "kick_attempts": count(lambda e: e.type == EventType.kick),
        "possible_contacts": count(lambda e: e.possible_contact),
        "knockdowns": count(lambda e: e.type == EventType.knockdown),
        "takedowns": count(lambda e: e.type == EventType.takedown),
        "significant": count(lambda e: e.type in MAJOR),
        "activity": activity, "pressure": pressure, "advance": advance, "retreat": retreat,
        "control_s": js_round(control).astype(np.int64),
        "measured_s": sums.valid[side][upto] / sums.hz,
    }


def _outside_ms(a: float, b: np.ndarray, iv: excl.Intervals) -> np.ndarray:
    """excl.outside_ms for many end times, with the same operations per element."""
    length = np.where(b > a, b - a, 0.0)
    for x, y in iv:
        lo = max(a, x)
        hi = np.minimum(b, y)
        length = np.where((b > a) & (hi > lo), length - (hi - lo), length)
    return length


@dataclass
class FrameMetrics:
    frames: np.ndarray  # [F] frame index
    t_ms: np.ndarray  # [F]
    m: np.ndarray  # [2, F] decayed momentum points (red, blue)
    red_share: np.ndarray  # [F] exact red share, %
    red_shown: np.ndarray  # [F] displayed red share (integer %); blue = 100 - red
    insufficient: np.ndarray  # [F] a fighter could not be measured
    motion_sample: np.ndarray  # [F] index into the motion samples (-1 = none)
    excluded: np.ndarray  # [F] frame lies in an excluded part
    stats: dict[str, dict[str, np.ndarray]]  # side -> STAT_COLUMNS


def compute(frame_count: int, fps: float, events: Sequence[FightEvent], motion: MotionTimeline,
            momentum: MomentumTimeline) -> FrameMetrics:
    frames = np.arange(frame_count, dtype=np.int64)
    t_ms = frame_ms(frames, fps)
    p = momentum.parameters
    segments = momentum.exclusions
    iv = excl.intervals(segments, fps)
    m = momentum_totals(momentum.contributions, t_ms, p.half_life_s, iv)
    share = red_share(m[0], m[1], p.prior)
    insufficient = np.array([momentum.insufficient[i] if (i := sample_at(momentum.sample_ms, t)) >= 0 else False
                             for t in t_ms.tolist()], dtype=bool)
    motion_sample = np.array([sample_at(motion.sample_ms, t) for t in t_ms.tolist()], dtype=np.int64)
    sums = motion_sums(motion, iv)
    excluded = np.zeros(frame_count, dtype=bool)
    for x in segments:
        excluded[x.start_frame:x.end_frame + 1] = True
    return FrameMetrics(frames=frames, t_ms=t_ms, m=m, red_share=share, red_shown=js_round(share).astype(np.int64),
                        insufficient=insufficient, motion_sample=motion_sample, excluded=excluded,
                        stats={side: side_stats(side, frames, t_ms, events, sums, segments, iv) for side in SIDES})


# ---- effects -----------------------------------------------------------------

@dataclass
class StrikeFlash:
    event: FightEvent
    strength: float  # 1 at the peak, fading to 0 after it


@dataclass
class ContactRing:
    event: FightEvent
    strength: float
    labelled: bool  # only the most recent one carries the "olası temas" text


@dataclass
class MajorWarning:
    event: FightEvent
    strength: float


@dataclass
class Effects:
    flashes: list[StrikeFlash]
    rings: list[ContactRing]
    warnings: list[MajorWarning]


def event_peak_s(e: FightEvent) -> float:
    return (e.peak_ms if e.peak_ms is not None else e.start_ms) / 1000


def effects_at(events: Sequence[FightEvent], t_s: float, style: OverlayStyle,
               excluded_ids: frozenset[str] | set[str] = frozenset()) -> Effects:
    """Effects visible at video time t_s (effectsAt of effects.ts). Durations are video
    time, so pausing freezes an effect and seeking back shows it again. Events in
    excluded parts get no effect."""
    flashes, rings, warnings = [], [], []
    for e in events:
        if e.event_id in excluded_ids:
            continue
        age = t_s - event_peak_s(e)
        if e.type in STRIKES:
            if -style.strike_before_s <= age <= style.strike_after_s:
                flashes.append(StrikeFlash(e, 1.0 if age <= 0 else 1 - age / style.strike_after_s))
            if e.possible_contact and e.location is not None and 0 <= age <= style.contact_after_s:
                rings.append(ContactRing(e, 1 - age / style.contact_after_s, False))
        elif e.type in MAJOR and 0 <= age <= style.major_after_s:
            hold = style.major_after_s - style.major_fade_s
            warnings.append(MajorWarning(e, 1.0 if age <= hold else (style.major_after_s - age) / style.major_fade_s))
    if rings:
        max(rings, key=lambda r: event_peak_s(r.event)).labelled = True
    return Effects(flashes, rings, warnings)
