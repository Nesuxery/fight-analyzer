"""Replays and stoppages from broadcast signals (rules over four signals, no model).

A replay shows the same fighters in the same cage, so it cannot be told from
live action by looking at one frame. What changes is the broadcast around it.
Four signals, sampled `sample_hz` times per second of video:

1. scorebug: the scorebug is not on screen (the strip around the clock does
   not look like it usually does), or a replay label ("REPLAY", "TEKRAR",
   "SLOW MO"...) is read on screen;
2. clock: the fight clock is known to stand still: a frozen display, reads
   before and after a gap that lost the gap's time, or the time between two
   consecutive rounds;
3. wipe: a logo transition at the start or end: many frames in a row that
   change a lot, or a very short shot (from the cut detection's frame changes);
4. slow motion: limb speeds of the people in view well below the live median
   (supporting only: a calm stretch of a fight is slow too).

Rules:
- Candidates are the stretches without a scorebug or with a replay label,
  and the stretches between two wipes (broadcasts without a scorebug).
- Time in which the fight clock is known to run is live: it is cut out of
  every candidate, whatever the other signals say.
- A candidate with at least two of the four signals is a replay. Its
  confidence grows with the number of signals; the signals are stored.
- The clock standing still for `stall_min_s` or more inside a round, outside a
  replay, is a stoppage.
- Before the first and after the last clock round: a stretch that is
  (almost) entirely without scorebug or running clock is an intro, and a
  break (the last round ran out) or post-fight part (it stopped early).
An unknown signal is never evidence: without a scorebug template "missing" is
false, and where no clock was read it is neither running nor standing still.

Everything here is a broadcast heuristic, tuned on one sample broadcast and
synthetic material; the user can turn each part off with one click.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np

from fight_analyzer.config import BroadcastSettings
from fight_analyzer.contracts import ExcludedSegment, ExclusionReason, ExclusionSignal
from fight_analyzer.nonfight import auto_segment
from fight_analyzer.pose.cache import PoseArrays

from .clock import ClockRound, Read

RUNNING, STOPPED, UNKNOWN = 1, 0, -1
LIMBS = (9, 10, 15, 16)  # wrists and ankles (COCO-17)
LS, RS, LH, RH = 5, 6, 11, 12
KP_MIN = 0.5
MAIN_SHARE = 0.6  # of the tallest person in the frame
SPEED_BASE_S = 0.1  # limb speed = displacement over this much time
Span = tuple[float, float]  # seconds


@dataclass
class Signals:
    t: np.ndarray  # [S] sample times, seconds
    bug: np.ndarray  # [S] scorebug template match (NaN: no template)
    label: np.ndarray  # [S] bool, replay label read (held until the next read)
    clock: np.ndarray  # [S] int8 RUNNING / STOPPED / UNKNOWN
    activity: np.ndarray  # [S] limb speed of the main people, torso lengths/s (NaN: not measured)
    wipes: list[Span] = field(default_factory=list)


# ---- signal 1b: replay label ----------------------------------------------------------------

_TR = str.maketrans("İıĞğŞşÇçÖöÜü", "IIGGSSCCOOUU")


def normalize_label(text: str) -> str:
    """Upper case without diacritics or punctuation ('Ağır-Çekim' -> 'AGIR CEKIM')."""
    plain = unicodedata.normalize("NFKD", text.translate(_TR))
    plain = "".join(ch for ch in plain if not unicodedata.combining(ch)).upper()
    return re.sub(r"[^A-Z0-9]+", " ", plain).strip()


def has_replay_label(text: str, words: Sequence[str]) -> bool:
    norm = f" {normalize_label(text)} "
    return any(f" {w} " in norm for w in words)


# ---- signal 2: fight clock ------------------------------------------------------------------

def stalls(reads: Sequence[Read], s: BroadcastSettings) -> list[Span]:
    """Stretches of one clock run in which the clock stood still: between consecutive reads
    it lost (almost) all of the video time, for `stall_min_s` or more in total. One repeated
    second (sampling jitter of a running clock) is not a stall."""
    out: list[Span] = []
    i, n = 0, len(reads)
    while i < n - 1:
        j = i
        while j < n - 1:
            dt = reads[j + 1].t - reads[j].t
            lost = dt - (reads[j].clock - reads[j + 1].clock)
            if dt <= 0 or lost < s.stall_share * dt:
                break
            j += 1
        if j > i:
            a, b = reads[i], reads[j]
            if (b.t + b.clock) - (a.t + a.clock) >= s.stall_min_s:
                out.append((a.t, b.t))
            i = j
        else:
            i += 1
    return out


def clock_states(t: np.ndarray, rounds: Sequence[ClockRound], s: BroadcastSettings) -> np.ndarray:
    """Per sample: the fight clock runs, stands still, or is not known."""
    state = np.full(t.shape, UNKNOWN, np.int8)
    ordered = sorted(rounds, key=lambda r: r.start_t)
    for r in ordered:
        state[(t >= r.start_t) & (t < r.end_t)] = RUNNING
        if r.reads:  # the display frozen before the bell / after the end
            state[(t >= r.reads[0].t) & (t < r.start_t)] = STOPPED
            state[(t >= r.end_t) & (t <= r.reads[-1].t)] = STOPPED
        for a, b in stalls(r.reads, s):
            state[(t >= max(a, r.start_t)) & (t < min(b, r.end_t))] = STOPPED
    for a, b in zip(ordered, ordered[1:]):
        if b.index == a.index + 1:  # with a round missing in between nothing is known about the gap
            state[(t >= a.end_t) & (t < b.start_t)] = STOPPED
    return state


# ---- signal 3: logo transition --------------------------------------------------------------

def wipe_events(cut_step: np.ndarray, cuts: Sequence[int], fps: float, s: BroadcastSettings) -> list[tuple[int, int]]:
    """Frame ranges of logo transitions: frames that change a lot packed into a short
    window (a hard cut is one such frame, camera motion none), or two cuts closer than
    `wipe_max_shot_s` (the graphic between them)."""
    events: list[tuple[int, int]] = []
    high = np.asarray(cut_step) >= s.wipe_step
    if high.any():
        window = max(2, round(s.wipe_window_s * fps))
        need = max(2, round(s.wipe_min_s * fps))
        dense = np.convolve(high.astype(np.int32), np.ones(window, np.int32), "same") >= need
        frames = np.flatnonzero(high & dense)
        if frames.size:
            start = prev = int(frames[0])
            for f in frames[1:].tolist():
                if f - prev > window:
                    events.append((start, prev))
                    start = f
                prev = f
            events.append((start, prev))
    limit = s.wipe_max_shot_s * fps
    events += [(int(a), int(b)) for a, b in zip(cuts, cuts[1:]) if b - a < limit]
    merged: list[tuple[int, int]] = []
    for a, b in sorted(events):
        if merged and a <= merged[-1][1] + 0.5 * fps:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return merged


# ---- signal 4: slow motion ------------------------------------------------------------------

def activity(arrays: PoseArrays, track_id: np.ndarray, fps: float, hz: float, count: int) -> np.ndarray:
    """Limb speed per sample: wrists and ankles relative to the hips, in torso lengths
    per second, of the same temporary track over `SPEED_BASE_S` (several frames, so a
    slow motion made by repeating frames is slow here too); per frame the fastest of
    the main people, per sample the upper quartile over its frames. NaN where it could
    not be measured. No identities are needed (this runs before the selection)."""
    f_count = arrays.frame_count
    out = np.full(count, np.nan, np.float32)
    if f_count == 0 or arrays.detection_count == 0:
        return out
    kp = np.asarray(arrays.keypoints)
    conf = kp[:, :, 2]
    hip = (kp[:, LH, :2] + kp[:, RH, :2]) / 2
    torso = np.linalg.norm((kp[:, LS, :2] + kp[:, RS, :2]) / 2 - hip, axis=1)
    core = (conf[:, [LS, RS, LH, RH]] >= KP_MIN).all(axis=1) & (torso > 4)
    rel = (kp[:, LIMBS, :2] - hip[:, None, :]) / np.maximum(torso, 1e-6)[:, None, None]
    usable = (conf[:, LIMBS] >= KP_MIN) & core[:, None]
    height = arrays.boxes[:, 3] - arrays.boxes[:, 1]
    offsets = arrays.det_offsets
    speed = np.full(f_count, np.nan, np.float32)
    base = max(1, round(SPEED_BASE_S * fps))
    recent: dict[int, list[tuple[int, int]]] = {}  # track id -> its last (frame, detection) entries
    for f in range(f_count):
        a, b = int(offsets[f]), int(offsets[f + 1])
        if a == b:
            continue
        top = float(height[a:b].max())
        best = math.nan
        for d in range(a, b):
            k = int(track_id[d])
            if k < 0:
                continue
            past = recent.setdefault(k, [])
            before = next((entry for entry in past if f - entry[0] <= base + 1), None)  # the oldest in reach
            past.append((f, d))
            if len(past) > base + 2:
                past.pop(0)
            if before is None or height[d] < MAIN_SHARE * top:
                continue
            both = usable[d] & usable[before[1]]
            if both.any():
                v = float(np.linalg.norm(rel[d][both] - rel[before[1]][both], axis=1).max()) * fps / (f - before[0])
                best = v if math.isnan(best) else max(best, v)
        speed[f] = best
    for i in range(count):
        part = speed[round(i * fps / hz):round((i + 1) * fps / hz)]
        ok = part[np.isfinite(part)]
        if ok.size >= max(2, part.size // 3):
            out[i] = float(np.percentile(ok, 75))
    return out


# ---- parts ----------------------------------------------------------------------------------

def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """Runs of True as (first, last) sample indexes."""
    idx = np.flatnonzero(mask)
    if idx.size == 0:
        return []
    breaks = np.flatnonzero(np.diff(idx) > 1)
    starts = np.concatenate(([idx[0]], idx[breaks + 1]))
    ends = np.concatenate((idx[breaks], [idx[-1]]))
    return [(int(a), int(b)) for a, b in zip(starts, ends)]


def _close(mask: np.ndarray, gap: int) -> np.ndarray:
    """Holes of at most `gap` samples between True samples filled."""
    out = mask.copy()
    runs = _runs(mask)
    for (_, b), (a, _) in zip(runs, runs[1:]):
        if a - b - 1 <= gap:
            out[b:a] = True
    return out


def _minus(span: Span, taken: Sequence[Span]) -> list[Span]:
    parts = [span]
    for a, b in taken:
        parts = [p for x, y in parts for p in ((x, min(y, a)), (max(x, b), y)) if p[1] > p[0]]
    return parts


@dataclass
class _Replay:
    start: float
    end: float
    signals: list[ExclusionSignal]
    confidence: float


ORDER = list(ExclusionSignal)


def detect(sig: Signals, rounds: Sequence[ClockRound], fps: float, frame_count: int,
           s: BroadcastSettings) -> list[ExcludedSegment]:
    """Replays, stoppages and the non-fight stretches before the first / after the last
    clock round, as automatic excluded parts (see the module text for the rules)."""
    n = int(sig.t.size)
    if n == 0 or frame_count == 0:
        return []
    hz = s.sample_hz
    dt = 1.0 / hz
    duration = frame_count / fps
    gap = round(s.close_gap_s * hz)
    missing = _close(np.isfinite(sig.bug) & (sig.bug < s.bug_present), gap)
    label = sig.label.astype(bool)
    running, stopped = sig.clock == RUNNING, sig.clock == STOPPED
    measured = np.isfinite(sig.activity)
    live = sig.activity[measured & running]
    if live.size < 20 * hz:  # no clock to say what is live: the whole video is the reference
        live = sig.activity[measured]
    live_ref = float(np.median(live)) if live.size else 0.0
    per_read = max(1, round(hz / s.ocr_hz))

    def near(t: float) -> list[Span]:
        return [w for w in sig.wipes if w[0] - s.wipe_near_s <= t <= w[1] + s.wipe_near_s]

    candidates = _runs(missing | _close(label, gap))
    for (_, a), (b, _) in zip(sig.wipes, sig.wipes[1:]):
        if s.replay_min_s <= b - a <= s.replay_max_s:
            i0, i1 = math.ceil(a * hz - 1e-6), math.floor(b * hz + 1e-6) - 1
            if 0 <= i0 <= i1 < n:
                candidates.append((i0, i1))

    replays: list[_Replay] = []
    for i0, i1 in candidates:
        for r0, r1 in _runs(~running[i0:i1 + 1]):
            j0, j1 = i0 + r0, i0 + r1
            if (j1 - j0 + 1) * dt < s.replay_min_s:
                continue
            part = slice(j0, j1 + 1)
            t0, t1 = float(sig.t[j0]), float(sig.t[j1]) + dt
            found: set[ExclusionSignal] = set()
            if missing[part].mean() >= s.signal_share:
                found.add(ExclusionSignal.scorebug_missing)
            if int(label[part].sum()) >= s.label_min_reads * per_read:
                found.add(ExclusionSignal.replay_label)
            if stopped[part].mean() >= s.signal_share:
                found.add(ExclusionSignal.clock_stopped)
            at_start, at_end = near(t0), near(t1)
            if at_start or at_end:
                found.add(ExclusionSignal.wipe)
            act = sig.activity[part]
            ok = np.isfinite(act)
            if live_ref > 0 and ok.sum() >= s.slow_min_s * hz and float(np.median(act[ok])) <= s.slow_ratio * live_ref:
                found.add(ExclusionSignal.slow_motion)
            groups = (int(bool(found & {ExclusionSignal.scorebug_missing, ExclusionSignal.replay_label}))
                      + sum(x in found for x in (ExclusionSignal.clock_stopped, ExclusionSignal.wipe,
                                                 ExclusionSignal.slow_motion)))
            if groups < 2:
                continue
            # The transitions are not fight footage either: include them, but never time the clock runs.
            lo, hi = j0, j1
            while lo > 0 and not running[lo - 1]:
                lo -= 1
            while hi < n - 1 and not running[hi + 1]:
                hi += 1
            start = max(min([t0, *(w[0] for w in at_start)]), float(sig.t[lo]))
            end = min(max([t1, *(w[1] for w in at_end)]), float(sig.t[hi]) + dt, duration)
            confidence = s.replay_confidence[min(groups, len(s.replay_confidence) + 1) - 2]
            if ExclusionSignal.replay_label in found:
                confidence += s.label_bonus
            replays.append(_Replay(start, end, [x for x in ORDER if x in found], confidence))
    replays.sort(key=lambda r: r.start)
    merged: list[_Replay] = []
    for r in replays:
        if merged and r.start <= merged[-1].end + dt:
            m = merged[-1]
            both = set(m.signals) | set(r.signals)
            merged[-1] = _Replay(m.start, max(m.end, r.end), [x for x in ORDER if x in both],
                                 max(m.confidence, r.confidence))
        else:
            merged.append(r)

    ordered = sorted(rounds, key=lambda r: r.start_t)
    edges: list[tuple[Span, ExclusionReason, list[ExclusionSignal], float]] = []
    if ordered:
        first, last = ordered[0], ordered[-1]
        ends = ExclusionReason.break_ if last.clock_end <= 0 else ExclusionReason.post_fight
        for mask, span, reason in ((sig.t < first.start_t, (0.0, first.start_t), ExclusionReason.intro),
                                   (sig.t >= last.end_t, (last.end_t, duration), ends)):
            if mask.sum() * dt < s.min_segment_s:
                continue
            share = float((missing | stopped)[mask].mean())
            if share >= s.edge_share:
                signals = [x for x, m in ((ExclusionSignal.scorebug_missing, missing),
                                          (ExclusionSignal.clock_stopped, stopped)) if m[mask].mean() >= 0.5]
                edges.append((span, reason, signals, s.edge_confidence * share))

    out: list[ExcludedSegment] = []

    def add(span: Span, reason: ExclusionReason, signals: list[ExclusionSignal], confidence: float) -> None:
        if span[1] - span[0] < s.min_segment_s:
            return
        start = min(frame_count - 1, max(0, round(span[0] * fps)))
        end = min(frame_count - 1, max(start, round(span[1] * fps) - 1))
        out.append(auto_segment(start, end, reason, signals, confidence))

    edge_spans = [e[0] for e in edges]
    for span, reason, signals, confidence in edges:
        add(span, reason, signals, confidence)
    replay_spans: list[Span] = []
    for r in merged:  # inside an intro / post-fight part a replay adds nothing
        for piece in _minus((r.start, r.end), edge_spans):
            replay_spans.append(piece)
            add(piece, ExclusionReason.replay, r.signals, r.confidence)
    in_round = np.zeros(n, bool)
    for r in ordered:
        in_round |= (sig.t >= r.start_t) & (sig.t < r.end_t)
    for j0, j1 in _runs(stopped & in_round):
        span = (float(sig.t[j0]), float(sig.t[j1]) + dt)
        if span[1] - span[0] < s.stall_min_s - 1e-6:
            continue
        for piece in _minus(span, replay_spans + edge_spans):
            # what a replay leaves over must be a stoppage of its own: where exactly the clock
            # stopped between two reads is not known, so a sliver next to a replay is not one
            if piece[1] - piece[0] >= s.stall_min_s - 1e-6:
                add(piece, ExclusionReason.stoppage, [ExclusionSignal.clock_stopped], s.stoppage_confidence)
    return sorted(out, key=lambda x: (x.start_frame, x.end_frame))
