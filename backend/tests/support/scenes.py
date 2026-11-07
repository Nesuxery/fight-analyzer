"""Synthetic fight scenes with known identities, for tracking tests.

People are drawn as simple figures whose keypoints are known exactly; the
"detector output" is generated from the same geometry, so tests exercise
cut detection, appearance, OC-SORT tracklets and identity assignment end to
end without a pose model. Ground truth (which person each detection is)
lets the tests count wrong assignments and identity switches.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from fight_analyzer.pose.cache import PoseArrays

W, H, FPS = 640, 360, 30.0

# Standing pose, body-height units, origin between the feet, y up negative.
_TEMPLATE = np.array([
    [0.02, -0.93], [0.03, -0.95], [0.0, -0.95], [0.05, -0.94], [-0.03, -0.94],
    [0.11, -0.8], [-0.11, -0.8], [0.15, -0.64], [-0.15, -0.64], [0.13, -0.5], [-0.13, -0.5],
    [0.08, -0.5], [-0.08, -0.5], [0.09, -0.26], [-0.09, -0.26], [0.1, 0.0], [-0.1, 0.0],
], np.float32)

SKIN = (120, 150, 200)


@dataclass
class Actor:
    pid: str
    shorts: tuple[int, int, int]
    pattern: str = "solid"  # solid | stripes | checker
    torso: tuple[int, int, int] = SKIN
    torso_pattern: str = "solid"


@dataclass
class Placement:
    x: float
    floor: float
    height: float
    detected: bool = True


@dataclass
class Scene:
    actors: dict[str, Actor]
    frames: int
    # frame index where each shot starts -> background colour (BGR)
    shots: dict[int, tuple[int, int, int]] = field(default_factory=lambda: {0: (70, 90, 60)})
    place: dict[str, list[Placement | None]] = field(default_factory=dict)

    def path(self, pid: str, keys: list[tuple[int, float, float, float]], detected=None) -> None:
        """Linear interpolation between (frame, x, floor, height) keyframes; None outside."""
        out: list[Placement | None] = [None] * self.frames
        for (f0, x0, y0, h0), (f1, x1, y1, h1) in zip(keys, keys[1:]):
            for f in range(f0, min(f1, self.frames - 1) + 1):
                k = 0.0 if f1 == f0 else (f - f0) / (f1 - f0)
                out[f] = Placement(x0 + (x1 - x0) * k, y0 + (y1 - y0) * k, h0 + (h1 - h0) * k)
        if detected:
            for f in detected:
                if out[f] is not None:
                    out[f].detected = False
        self.place[pid] = out

    def hide_detection(self, pid: str, frames) -> None:
        for f in frames:
            p = self.place[pid][f]
            if p is not None:
                p.detected = False


def _keypoints(p: Placement, facing: float) -> np.ndarray:
    pts = _TEMPLATE.copy()
    pts[:, 0] *= facing
    out = np.zeros((17, 3), np.float32)
    out[:, 0] = p.x + pts[:, 0] * p.height
    out[:, 1] = p.floor + pts[:, 1] * p.height
    out[:, 2] = 0.9
    return out


def _fill(img, poly, color, pattern, scale):
    mask = np.zeros(img.shape[:2], np.uint8)
    cv2.fillConvexPoly(mask, np.round(poly).astype(np.int32), 1)
    layer = np.empty_like(img)
    layer[:] = color
    if pattern == "stripes":
        step = max(3, int(scale * 0.04))
        layer[::, :][(np.arange(img.shape[0]) // step % 2 == 0)] = (240, 240, 240)
    elif pattern == "checker":
        step = max(3, int(scale * 0.05))
        yy, xx = np.indices(img.shape[:2])
        layer[((yy // step + xx // step) % 2 == 0)] = (30, 30, 30)
    img[mask > 0] = layer[mask > 0]


def _draw(img: np.ndarray, actor: Actor, k: np.ndarray, h: float) -> None:
    lw = max(2, int(h * 0.06))
    for a, b in ((5, 7), (7, 9), (6, 8), (8, 10), (11, 13), (13, 15), (12, 14), (14, 16)):
        cv2.line(img, tuple(np.round(k[a, :2]).astype(int)), tuple(np.round(k[b, :2]).astype(int)), SKIN, lw)
    torso = np.array([k[5, :2], k[6, :2], k[12, :2], k[11, :2]])
    torso = torso + (torso - torso.mean(0)) * np.array([0.6, 0.05])  # wider than the joints
    _fill(img, torso, actor.torso, actor.torso_pattern, h)
    hips = np.array([k[11, :2], k[12, :2]])
    mid = hips.mean(0)
    half = 0.16 * h
    knees = (k[13, :2] + k[14, :2]) / 2
    down = (knees - mid) * 0.55
    shorts = np.array([mid + [-half, -0.02 * h], mid + [half, -0.02 * h],
                       mid + down + [half, 0], mid + down + [-half, 0]])
    _fill(img, shorts, actor.shorts, actor.pattern, h)
    cv2.circle(img, tuple(np.round(k[0, :2]).astype(int)), max(3, int(h * 0.06)), SKIN, -1)


@dataclass
class Rendered:
    frames: list[np.ndarray]
    arrays: PoseArrays
    truth: list[str]  # person id per detection


def render(scene: Scene, seed: int = 0) -> Rendered:
    rng = np.random.default_rng(seed)
    starts = sorted(scene.shots)
    frames, boxes, confs, kps, counts, truth = [], [], [], [], [], []
    for t in range(scene.frames):
        shot_start = max(s for s in starts if s <= t)
        bg = np.array(scene.shots[shot_start], np.float32)
        img = np.empty((H, W, 3), np.uint8)
        img[:] = bg
        # fixed fence texture per shot, so cuts change both colour and structure
        for x in range(shot_start % 37, W, 40):
            cv2.line(img, (x, 0), (x, H // 2), tuple(int(c * 0.7) for c in bg), 2)
        visible = [(pid, p) for pid, seq in scene.place.items() if (p := seq[t]) is not None]
        visible.sort(key=lambda item: item[1].floor)  # far first
        n = 0
        for pid, p in visible:
            facing = 1.0 if p.x < W / 2 else -1.0
            k = _keypoints(p, facing)
            _draw(img, scene.actors[pid], k, p.height)
            if not p.detected:
                continue
            jitter = rng.normal(0, 1.0, (17, 2)).astype(np.float32)
            k[:, :2] += jitter
            pad = 0.06 * p.height
            box = np.array([k[:, 0].min() - pad, k[:, 1].min() - 2 * pad,
                            k[:, 0].max() + pad, k[:, 1].max() + pad], np.float32)
            boxes.append(box)
            confs.append(0.9)
            kps.append(k)
            truth.append(pid)
            n += 1
        noise = rng.integers(-6, 7, img.shape, dtype=np.int16)
        frames.append(np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8))
        counts.append(n)
    f = scene.frames
    arrays = PoseArrays(
        frame_index=np.arange(f, dtype=np.int32),
        timestamp_ms=np.arange(f, dtype=np.float64) * 1000 / FPS,
        det_offsets=np.concatenate([[0], np.cumsum(counts)]).astype(np.int64),
        boxes=np.array(boxes, np.float32).reshape(-1, 4),
        box_conf=np.array(confs, np.float32),
        keypoints=np.array(kps, np.float32).reshape(-1, 17, 3),
    )
    return Rendered(frames=frames, arrays=arrays, truth=truth)


def det_id_of(r: Rendered, frame: int, pid: str) -> int:
    """Per-frame detection id of person `pid` on `frame`."""
    a, b = int(r.arrays.det_offsets[frame]), int(r.arrays.det_offsets[frame + 1])
    for d in range(a, b):
        if r.truth[d] == pid:
            return d - a
    raise KeyError(f"{pid} not detected on frame {frame}")


@dataclass
class Evaluation:
    wrong: list[int]  # frames where a fighter sits on someone else's detection
    switches: int
    uncertain: list[int]
    tracked: list[int]


def evaluate(r: Rendered, det: np.ndarray, state: np.ndarray, fighters=("A", "B")) -> Evaluation:
    wrong, uncertain, tracked, switches = [0, 0], [0, 0], [0, 0], 0
    for f, pid in enumerate(fighters):
        prev = None
        for t in range(det.shape[0]):
            if state[t, f] == 2:
                uncertain[f] += 1
            d = int(det[t, f])
            if d < 0:
                continue
            tracked[f] += 1
            who = r.truth[d]
            if who != pid:
                wrong[f] += 1
            if prev is not None and who != prev:
                switches += 1
            prev = who
    return Evaluation(wrong=wrong, switches=switches, uncertain=uncertain, tracked=tracked)
