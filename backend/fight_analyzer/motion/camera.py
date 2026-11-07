"""Camera motion from the background.

For every pair of consecutive frames inside a shot, corner features outside
all person boxes and outside persistent broadcast graphics are tracked with
pyramidal Lucas-Kanade optical flow (checked forwards and backwards), and a
similarity transform (shift, zoom, small rotation) is fitted with RANSAC.
Chained from the first frame of the shot it maps every frame onto that frame
("stabilized" coordinates), so a fighter's own movement can be separated from
a pan or zoom. Where too few background points agree the chain is broken and a
new stabilization segment starts: positions before and after are never
compared ("camera motion unknown").

Broadcast graphics (score bar, channel logo) stay fixed on screen while the
camera moves and would vote for "no motion". They are found as pixels that
look the same in different shots and do not change within a shot, and are
masked out. With a single shot this is not possible; then a consensus that
is concentrated in a small area is rejected instead.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from fight_analyzer.config import MotionSettings
from fight_analyzer.pose.cache import PoseArrays

CAMERA_VERSION = 2  # 2: overlay mask from the longest shots only (bounded memory)
# Shots compared for the graphics mask: memory and the pairwise comparison stay bounded
# however many camera cuts a long broadcast has.
MAX_OVERLAY_SHOTS = 24
BOX_PAD = 0.08  # person boxes are grown by this share before masking
MIN_SPREAD = 0.08  # inliers must span at least this share of the frame area
MAX_STEP_ZOOM = 0.2  # per-frame zoom beyond +-20 % is not camera motion
MAX_STEP_ROTATION = math.radians(5)


@dataclass
class CameraTrack:
    to_ref: np.ndarray  # [F, 2, 3] float64: frame pixels -> stabilized pixels of the segment
    segment: np.ndarray  # [F] int32: positions are comparable only within one segment
    known: np.ndarray  # [F] bool: motion from the previous frame was measured (False = new segment)
    inliers: np.ndarray  # [F] int32 background points that agreed (diagnostic)

    @property
    def known_share(self) -> float:
        """Frame-to-frame motions measured, among frames that continue a shot."""
        return float(self.known.mean()) if self.known.size else 0.0


def _small_gray(frame: np.ndarray, width: int) -> tuple[np.ndarray, float]:
    h, w = frame.shape[:2]
    f = min(1.0, width / w)
    if f < 1.0:
        frame = cv2.resize(frame, (round(w * f), round(h * f)), interpolation=cv2.INTER_AREA)
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), f


def _person_mask(shape: tuple[int, int], boxes: np.ndarray, f: float, overlay: np.ndarray | None) -> np.ndarray:
    mask = np.full(shape, 255, np.uint8)
    if overlay is not None:
        mask[overlay] = 0
    h, w = shape
    for x1, y1, x2, y2 in boxes:
        px, py = (x2 - x1) * BOX_PAD + 4 / f, (y2 - y1) * BOX_PAD + 4 / f
        a = (max(0, int((x1 - px) * f)), max(0, int((y1 - py) * f)))
        b = (min(w - 1, int(math.ceil((x2 + px) * f))), min(h - 1, int(math.ceil((y2 + py) * f))))
        cv2.rectangle(mask, a, b, 0, -1)
    return mask


def overlay_mask(path: Path, shot_id: np.ndarray, fps: float, s: MotionSettings) -> np.ndarray | None:
    """Pixels (at camera_width) of graphics that persist across shots, or None.
    Uses the MAX_OVERLAY_SHOTS longest shots."""
    step = max(1, round(fps / 4))
    ids, lengths = np.unique(shot_id, return_counts=True)
    used = {int(i) for i in ids[np.argsort(-lengths, kind="stable")[:MAX_OVERLAY_SHOTS]]}
    stats: dict[int, list] = {}
    cap = cv2.VideoCapture(str(path))
    try:
        t = 0
        while t < shot_id.size:
            if t % step or int(shot_id[t]) not in used:
                if not cap.grab():
                    break
                t += 1
                continue
            ok, frame = cap.read()
            if not ok:
                break
            gray, _ = _small_gray(frame, s.camera_width)
            g = gray.astype(np.float64)
            entry = stats.setdefault(int(shot_id[t]), [np.zeros_like(g), np.zeros_like(g), 0])
            entry[0] += g
            entry[1] += g * g
            entry[2] += 1
            t += 1
    finally:
        cap.release()
    shots = {k: (v[0] / v[2], np.sqrt(np.maximum(v[1] / v[2] - (v[0] / v[2]) ** 2, 0))) for k, v in stats.items()
             if v[2] >= 3}
    if len(shots) < 2:
        return None
    keys = sorted(shots)
    static = np.zeros(shots[keys[0]][0].shape, bool)
    informative = False
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            diff = np.abs(shots[a][0] - shots[b][0])
            if float(np.median(diff)) < 15:  # the two shots look alike: says nothing about graphics
                continue
            informative = True
            # same in both shots and unchanged within each (graphics need not be in every shot)
            static |= (diff < 8) & (shots[a][1] < 8) & (shots[b][1] < 8)
    if not informative:
        return None
    mask = cv2.dilate(static.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    return mask if mask.mean() < 0.4 else None


def _pair(prev: np.ndarray, cur: np.ndarray, prev_mask: np.ndarray, cur_mask: np.ndarray,
          s: MotionSettings) -> tuple[np.ndarray | None, int]:
    """Similarity transform prev -> cur (small-image pixels) and its inlier count."""
    pts = cv2.goodFeaturesToTrack(prev, maxCorners=s.camera_features, qualityLevel=0.01, minDistance=8,
                                  mask=prev_mask)
    if pts is None or len(pts) < s.camera_min_inliers:
        return None, 0
    lk = {"winSize": (21, 21), "maxLevel": 3,
          "criteria": (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.03)}
    nxt, st, _ = cv2.calcOpticalFlowPyrLK(prev, cur, pts, None, **lk)
    back, st2, _ = cv2.calcOpticalFlowPyrLK(cur, prev, nxt, None, **lk)
    good = (st[:, 0] == 1) & (st2[:, 0] == 1) & (np.linalg.norm((pts - back)[:, 0], axis=1) < 1.0)
    h, w = cur.shape
    xi = np.clip(np.round(nxt[:, 0, 0]).astype(int), 0, w - 1)
    yi = np.clip(np.round(nxt[:, 0, 1]).astype(int), 0, h - 1)
    good &= cur_mask[yi, xi] > 0
    if int(good.sum()) < s.camera_min_inliers:
        return None, int(good.sum())
    src, dst = pts[good], nxt[good]
    m, inl = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=1.0,
                                         maxIters=500, confidence=0.99)
    if m is None or inl is None:
        return None, 0
    inl = inl[:, 0].astype(bool)
    n = int(inl.sum())
    if n < s.camera_min_inliers:
        return None, n
    p = src[inl][:, 0]
    if (np.ptp(p[:, 0]) * np.ptp(p[:, 1])) / (w * h) < MIN_SPREAD:
        return None, n  # agreement only in a small area (graphics, one object)
    zoom = math.hypot(m[0, 0], m[1, 0])
    if abs(zoom - 1) > MAX_STEP_ZOOM or abs(math.atan2(m[1, 0], m[0, 0])) > MAX_STEP_ROTATION:
        return None, n
    return m, n


def _invert(m: np.ndarray) -> np.ndarray:
    a = np.linalg.inv(m[:, :2])
    return np.hstack([a, -(a @ m[:, 2:3])])


def _compose(outer: np.ndarray, inner: np.ndarray) -> np.ndarray:
    """outer(inner(p))."""
    return np.hstack([outer[:, :2] @ inner[:, :2], outer[:, :2] @ inner[:, 2:3] + outer[:, 2:3]])


def estimate(frames: Iterable[np.ndarray], arrays: PoseArrays, shot_id: np.ndarray, s: MotionSettings,
             overlay: np.ndarray | None = None,
             on_progress: Callable[[int], None] | None = None) -> CameraTrack:
    count = arrays.frame_count
    eye = np.array([[1.0, 0, 0], [0, 1.0, 0]])
    to_ref = np.tile(eye, (count, 1, 1))
    segment = np.zeros(count, np.int32)
    known = np.zeros(count, bool)
    inliers = np.zeros(count, np.int32)
    prev = prev_mask = None
    cum = eye.copy()  # small-image pixels of the current frame -> segment reference
    seg = -1
    f = 1.0
    t = -1
    for t, frame in enumerate(frames):
        if t >= count:
            break
        gray, f = _small_gray(frame, s.camera_width)
        boxes = arrays.boxes[int(arrays.det_offsets[t]):int(arrays.det_offsets[t + 1])]
        mask = _person_mask(gray.shape, boxes, f, overlay if overlay is not None and overlay.shape == gray.shape
                            else None)
        m = None
        if prev is not None and t > 0 and shot_id[t] == shot_id[t - 1]:
            m, inliers[t] = _pair(prev, gray, prev_mask, mask, s)
        if m is None:
            seg += 1
            cum = eye.copy()
        else:
            cum = _compose(cum, _invert(m))
            known[t] = True
        full = cum.copy()
        full[:, 2] /= f  # same linear part; translation back to full-size pixels
        to_ref[t], segment[t] = full, seg
        prev, prev_mask = gray, mask
        if on_progress and t % 10 == 0:
            on_progress(t + 1)
    if t + 1 < count:  # fewer decodable frames than poses: unknown from there on
        segment[t + 1:] = np.arange(seg + 1, seg + 1 + count - t - 1)
    return CameraTrack(to_ref=to_ref, segment=segment, known=known, inliers=inliers)


def apply(m: np.ndarray, xy: np.ndarray) -> np.ndarray:
    """Map points [..., 2] with a 2x3 transform."""
    return xy @ m[:, :2].T + m[:, 2]


def zoom(m: np.ndarray) -> float:
    return math.hypot(m[0, 0], m[1, 0])
