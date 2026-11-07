"""Candidate frames for fighter selection.

Good frames show two large, confidently detected people that do not overlap,
away from camera cuts. One frame per stretch of the video is offered, so the
user can pick a moment where both fighters are clearly visible. If the video
has few such frames, the best remaining ones (e.g. overlapping) are added
with a lower score so there is always something to choose from.
"""

from __future__ import annotations

import numpy as np

from fight_analyzer.pose.cache import PoseArrays

OVERLAP_PENALTY = 0.5
NEAR_CUT_PENALTY = 0.5


def frame_scores(arrays: PoseArrays, contact: np.ndarray, shot_id: np.ndarray, cuts: list[int],
                 frame_height: int) -> np.ndarray:
    scores = np.zeros(arrays.frame_count, np.float32)
    near_cut = np.zeros(arrays.frame_count, bool)
    for c in cuts:
        near_cut[max(0, c - 3):c + 5] = True
    for t in range(arrays.frame_count):
        a, b = int(arrays.det_offsets[t]), int(arrays.det_offsets[t + 1])
        if b - a < 2:
            continue
        boxes = arrays.boxes[a:b]
        heights = boxes[:, 3] - boxes[:, 1]
        top = np.argsort(-heights)[:2] + a
        h = (arrays.boxes[top, 3] - arrays.boxes[top, 1]) / max(1, frame_height)
        kp = float(arrays.keypoints[top, :, 2].mean())
        size = float(min(1.0, h.min() / 0.4))
        score = 0.45 * kp + 0.3 * size + 0.25 * float(arrays.box_conf[top].mean())
        if contact[top].any():
            score *= OVERLAP_PENALTY
        if near_cut[t]:
            score *= NEAR_CUT_PENALTY
        scores[t] = score
    return scores


def pick(scores: np.ndarray, count: int, min_score: float = 0.45, min_spacing: int = 30) -> list[int]:
    """Best clear frame in each of `count` stretches, topped up with the best
    remaining frames (spaced apart) when there are too few clear ones."""
    frames: list[int] = []
    edges = np.linspace(0, len(scores), count + 1).astype(int)
    for lo, hi in zip(edges[:-1], edges[1:]):
        if hi <= lo:
            continue
        best = int(lo) + int(np.argmax(scores[lo:hi]))
        if scores[best] >= min_score:
            frames.append(best)
    wanted = max(3, count // 2)
    for t in np.argsort(-scores):
        if len(frames) >= wanted or scores[t] <= 0:
            break
        if all(abs(int(t) - f) >= min_spacing for f in frames):
            frames.append(int(t))
    return sorted(frames)
