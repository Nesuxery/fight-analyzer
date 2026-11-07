"""Camera cut (shot boundary) detection from frame colour histograms.

A cut is a large jump between consecutive frames, either absolutely or
relative to the recent level of change (fast camera pans change a lot too).
A single-frame flash (the frame after it looks like the frame before it) is
not a cut, and shots shorter than `min_shot_frames` are merged.
"""

from __future__ import annotations

import cv2
import numpy as np

from fight_analyzer.config import TrackingSettings

SIG_DIM = 8 * 4 * 4


def signature(frame_bgr: np.ndarray) -> np.ndarray:
    small = cv2.resize(frame_bgr, (64, 36), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1, 2], None, [8, 4, 4], [0, 180, 0, 256, 0, 256]).ravel()
    return (hist / max(1.0, float(hist.sum()))).astype(np.float32)


def distance(a: np.ndarray, b: np.ndarray) -> float:
    """1 - Bhattacharyya coefficient (0 = identical histograms)."""
    return float(max(0.0, 1.0 - np.sqrt(a * b).sum()))


class CutScorer:
    """Streams frame signatures; keeps only what is needed for the decision."""

    def __init__(self) -> None:
        self.step: list[float] = []  # d(t-1, t)
        self.skip: list[float] = []  # d(t-1, t+1), filled one frame late
        self._prev2: np.ndarray | None = None
        self._prev: np.ndarray | None = None

    def add(self, sig: np.ndarray) -> None:
        if self._prev is None:
            self.step.append(0.0)
        else:
            self.step.append(distance(self._prev, sig))
        if self._prev2 is not None:
            self.skip.append(distance(self._prev2, sig))  # for frame t-1
        elif self._prev is not None:
            self.skip.append(0.0)
        self._prev2, self._prev = self._prev, sig

    def finish(self) -> tuple[np.ndarray, np.ndarray]:
        step = np.asarray(self.step, np.float32)
        skip = np.asarray(self.skip + [1.0] * (len(self.step) - len(self.skip)), np.float32)
        return step, skip


def detect_cuts(step: np.ndarray, skip: np.ndarray, s: TrackingSettings, window: int = 15) -> list[int]:
    """Frames where a new shot starts (never frame 0)."""
    cuts: list[int] = []
    for t in range(1, len(step)):
        d = float(step[t])
        recent = step[max(1, t - window):t]
        level = float(np.median(recent)) if recent.size else 0.0
        if not (d >= s.cut_threshold or (d >= s.cut_floor and d >= s.cut_relative * (level + 0.01))):
            continue
        # skip[t] = d(t-1, t+1): the frame after looks like the one before -> flash, not a cut
        if t + 1 < len(step) and float(skip[t]) < 0.5 * d:
            continue
        # ... and the frame right after such a flash returns to the old shot
        if t >= 2 and float(skip[t - 1]) < 0.5 * d:
            continue
        if cuts and t - cuts[-1] < s.min_shot_frames:
            if d > float(step[cuts[-1]]):
                cuts[-1] = t
            continue
        cuts.append(t)
    return cuts


def shot_ids(frame_count: int, cuts: list[int]) -> np.ndarray:
    ids = np.zeros(frame_count, np.int32)
    for c in cuts:
        ids[c:] += 1
    return ids
