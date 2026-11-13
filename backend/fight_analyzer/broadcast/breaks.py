"""Round breaks without a readable clock (low confidence, from poses only).

Between rounds the fighters sit on stools in their corners with their teams
around them, and nobody fights. Per second of video:
- fighting: two people of fighter size standing within striking distance;
- break-like: someone of fighter size sitting (hips about level with the
  knees) or at least four people of fighter size in view.
A stretch of at least `break_min_s` without fighting seconds, mostly
break-like, is a break; rounds are what lies between breaks. With no break
found nothing is claimed (the whole video is not called "round 1").
"""

from __future__ import annotations

import math

import numpy as np

from fight_analyzer.config import BroadcastSettings, RulesetSettings
from fight_analyzer.contracts import RoundSegment, RoundSource
from fight_analyzer.pose.cache import PoseArrays

LS, RS, LH, RH, LK, RK = 5, 6, 11, 12, 13, 14
MIN_KP = 0.3
MAIN_SHARE = 0.6  # of the tallest person in the frame
MIN_MAIN_HEIGHT = 0.22  # of the frame height (close or medium shot)


def _frame_flags(arrays: PoseArrays, frame_height: int) -> tuple[np.ndarray, np.ndarray]:
    """Per frame: (fighting, break-like)."""
    f_count = arrays.frame_count
    fighting = np.zeros(f_count, bool)
    breaky = np.zeros(f_count, bool)
    for f in range(f_count):
        a, b = int(arrays.det_offsets[f]), int(arrays.det_offsets[f + 1])
        if b - a == 0:
            continue
        boxes, kps = arrays.boxes[a:b], arrays.keypoints[a:b]
        heights = boxes[:, 3] - boxes[:, 1]
        widths = np.maximum(1.0, boxes[:, 2] - boxes[:, 0])
        top = float(heights.max())
        if top < MIN_MAIN_HEIGHT * frame_height:
            continue
        main = np.flatnonzero(heights >= MAIN_SHARE * top)
        seated = np.zeros(b - a, bool)
        for d in main:
            k = kps[d]
            if (k[[LS, RS, LH, RH, LK, RK], 2] >= MIN_KP).all():
                shoulder_y, hip_y, knee_y = k[[LS, RS], 1].mean(), k[[LH, RH], 1].mean(), k[[LK, RK], 1].mean()
                torso = hip_y - shoulder_y
                seated[d] = torso > 0 and (knee_y - hip_y) < 0.35 * torso and heights[d] / widths[d] < 2.0
        standing = [d for d in main if not seated[d] and heights[d] / widths[d] >= 1.6]
        for i, d in enumerate(standing):
            for e in standing[i + 1:]:
                cx_d, cx_e = (boxes[d, 0] + boxes[d, 2]) / 2, (boxes[e, 0] + boxes[e, 2]) / 2
                if abs(cx_d - cx_e) < 1.0 * (heights[d] + heights[e]) / 2:
                    fighting[f] = True
        breaky[f] = bool(seated[main].any()) or len(main) >= 4
    return fighting, breaky


def break_spans(arrays: PoseArrays, fps: float, frame_height: int, s: BroadcastSettings) -> list[tuple[float, float]]:
    fighting, breaky = _frame_flags(arrays, frame_height)
    per = max(1, round(fps))
    seconds = math.ceil(len(fighting) / per)
    fight_s = np.array([fighting[i * per:(i + 1) * per].mean() >= 0.3 for i in range(seconds)])
    break_s = np.array([breaky[i * per:(i + 1) * per].mean() >= 0.5 for i in range(seconds)])
    spans: list[tuple[float, float]] = []
    i = 0
    while i < seconds:
        if fight_s[i]:
            i += 1
            continue
        j = i
        while j < seconds and not fight_s[j]:
            j += 1
        if j - i >= s.break_min_s and break_s[i:j].mean() >= s.break_quiet_share:
            spans.append((float(i), float(min(j, len(fighting) / fps))))
        i = j
    return spans


def rounds_between(breaks: list[tuple[float, float]], duration_s: float, fps: float, frame_count: int,
                   s: BroadcastSettings, ruleset: RulesetSettings) -> list[RoundSegment]:
    if not breaks:
        return []
    edges = [0.0, *[x for span in breaks for x in span], duration_s]
    out: list[RoundSegment] = []
    for a, b in zip(edges[0::2], edges[1::2]):
        if b - a < s.min_round_s or len(out) == 5:
            continue
        start = min(frame_count - 1, round(a * fps))
        end = min(frame_count - 1, max(start, math.ceil(b * fps) - 1))
        out.append(RoundSegment(index=len(out) + 1, start_frame=start, end_frame=end,
                                video_start_s=round(start / fps, 3), video_end_s=round((end + 1) / fps, 3),
                                source=RoundSource.break_, confidence=s.break_max_confidence,
                                partial=(b - a) < ruleset.round_length_s - 10))
    return out
