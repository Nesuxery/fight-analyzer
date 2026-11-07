"""Parts of the video the user excluded (broadcast replays, slow motion, breaks).

Replays cannot be told apart from live action reliably (same fighters, same
cage), so the user marks them. An excluded part is not fight time:

* an event whose moment (peak frame, else start frame) is in it is listed but
  neither counted nor scored;
* time-based points (advancing, control), control time and measured time do
  not accrue in it;
* the momentum holds its value through it: decay runs on fight time, which
  stops while an excluded part plays.

The same rules are implemented in frontend/src/model/measured.ts and used by
the export (export/frames.py); the shared golden file checks both.
Frame f covers [f, f + 1) / fps, so a part [start_frame, end_frame] covers
[start_frame, end_frame + 1) * 1000 / fps ms.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import numpy as np

from fight_analyzer.contracts import ExcludedSegment, FightEvent

Intervals = list[tuple[float, float]]


def normalize(segments: Iterable[ExcludedSegment], frame_count: int) -> list[ExcludedSegment]:
    """Clip to the video, sort, and merge overlapping or touching parts (the first one's reason wins)."""
    out: list[ExcludedSegment] = []
    for s in sorted(segments, key=lambda s: (s.start_frame, s.end_frame)):
        if s.start_frame >= frame_count:
            continue
        s = s.model_copy(update={"end_frame": min(s.end_frame, frame_count - 1)})
        if out and s.start_frame <= out[-1].end_frame + 1:
            out[-1] = out[-1].model_copy(update={"end_frame": max(out[-1].end_frame, s.end_frame)})
        else:
            out.append(s)
    return out


def intervals(segments: Sequence[ExcludedSegment], fps: float) -> Intervals:
    """[start_ms, end_ms) of normalized parts."""
    return [(s.start_frame * 1000 / fps, (s.end_frame + 1) * 1000 / fps) for s in segments]


def frame_excluded(frame: int, segments: Sequence[ExcludedSegment]) -> bool:
    return any(s.start_frame <= frame <= s.end_frame for s in segments)


def event_frame(e: FightEvent) -> int:
    return e.peak_frame if e.peak_frame is not None else e.start_frame


def excluded_event_ids(events: Iterable[FightEvent], segments: Sequence[ExcludedSegment]) -> set[str]:
    return {e.event_id for e in events if frame_excluded(event_frame(e), segments)}


def fight_ms(t_ms: float, iv: Intervals) -> float:
    """Video time -> fight time (excluded time before t removed)."""
    total = 0.0
    for a, b in iv:
        if t_ms <= a:
            break
        total += min(t_ms, b) - a
    return t_ms - total


def fight_ms_array(t_ms: np.ndarray, iv: Intervals) -> np.ndarray:
    """fight_ms for many times, with the same floating-point operations per element."""
    t = np.asarray(t_ms, dtype=np.float64)
    total = np.zeros(t.shape)
    for a, b in iv:
        total = total + np.where(t > a, np.minimum(t, b) - a, 0.0)
    return t - total


def outside_ms(a: float, b: float, iv: Intervals) -> float:
    """Length of [a, b] outside the excluded parts (0 when b <= a)."""
    if b <= a:
        return 0.0
    length = b - a
    for x, y in iv:
        lo, hi = max(a, x), min(b, y)
        if hi > lo:
            length -= hi - lo
    return length


def outside_parts(a: float, b: float, iv: Intervals) -> Intervals:
    """[a, b] split into the stretches outside the excluded parts."""
    parts: Intervals = []
    cur = a
    for x, y in iv:
        if y <= cur or x >= b:
            continue
        if x > cur:
            parts.append((cur, x))
        cur = max(cur, y)
        if cur >= b:
            break
    if cur < b:
        parts.append((cur, b))
    return parts


def in_intervals(t_ms: float, iv: Intervals) -> bool:
    return any(a <= t_ms < b for a, b in iv)
