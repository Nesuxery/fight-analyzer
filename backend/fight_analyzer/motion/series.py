"""Small helpers for per-frame series (used by events.py and grappling.py)."""

from __future__ import annotations

import numpy as np


def frame_seconds(ts: np.ndarray) -> np.ndarray:
    """Seconds each frame stands for (the time to the next frame; the last one gets the median)."""
    if ts.size == 0:
        return ts.copy()
    d = np.diff(ts)
    last = float(np.median(d)) if d.size else 0.0
    return np.clip(np.append(d, last), 0.0, 0.5)


def runs(mask: np.ndarray, ts: np.ndarray, max_gap_s: float) -> list[tuple[int, int]]:
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


def close_holes(mask: np.ndarray, ts: np.ndarray, gap_s: float) -> np.ndarray:
    """Short False stretches between True frames become True."""
    out = mask.copy()
    idx = np.flatnonzero(mask)
    for a, b in zip(idx[:-1], idx[1:]):
        if b > a + 1 and ts[b] - ts[a] <= gap_s:
            out[a + 1:b] = True
    return out


def value_runs(values: np.ndarray) -> list[tuple[int, int, int]]:
    """(value, first, last) of the stretches of equal values, in order."""
    n = values.size
    if n == 0:
        return []
    cuts = np.flatnonzero(values[1:] != values[:-1]) + 1
    starts = np.concatenate(([0], cuts))
    ends = np.concatenate((cuts - 1, [n - 1]))
    return [(int(values[a]), int(a), int(b)) for a, b in zip(starts, ends)]


def window_mask(ts: np.ndarray, moments: np.ndarray, before_s: float, after_s: float) -> np.ndarray:
    """Frames within [moment - before_s, moment + after_s] of any of the moments (seconds)."""
    d = np.zeros(ts.size + 1, np.int64)
    if moments.size:
        np.add.at(d, np.searchsorted(ts, moments - before_s), 1)
        np.add.at(d, np.searchsorted(ts, moments + after_s, side="right"), -1)
    return np.cumsum(d[:-1]) > 0
