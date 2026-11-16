"""Synthetic skeleton motion with known actions, for motion/event tests.

Fighters are posed in torso units (mid-shoulders to mid-hips = 1) with limb
lengths matching kinematics.SEGMENTS, in a body frame (up / forward axes) so
that standing, striking and lying down use the same geometry. Actions are
functions of time, so a scene can be sampled at any frame rate (frame-rate
independence) and with keypoint jitter. The output is what the motion stage
gets in production: PoseArrays, identity arrays (state/det), tracker ids and
a camera track.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from fight_analyzer.motion.camera import CameraTrack
from fight_analyzer.pose.cache import PoseArrays

UPPER_ARM, FOREARM, THIGH, SHIN = 0.62, 0.52, 0.83, 0.83
Action = Callable[[float, dict], None]


def ease(x: float) -> float:
    """0..1 smooth step (cosine)."""
    x = min(1.0, max(0.0, x))
    return 0.5 - 0.5 * math.cos(math.pi * x)


def _ik(base: np.ndarray, end: np.ndarray, a: float, b: float, bend: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Middle and end joint of a two-link limb reaching toward `end`, bent toward `bend`."""
    d_vec = end - base
    length = max(float(np.linalg.norm(d_vec)), 1e-9)
    u = d_vec / length
    d = min(max(length, abs(a - b) + 1e-6), a + b - 1e-6)
    cos_alpha = (a * a + d * d - b * b) / (2 * a * d)
    alpha = math.acos(max(-1.0, min(1.0, cos_alpha)))
    n = np.array([-u[1], u[0]])
    if np.dot(n, bend) < 0:
        n = -n
    return base + a * (math.cos(alpha) * u + math.sin(alpha) * n), base + u * d


@dataclass
class Fighter:
    x: float  # hip centre, torso units
    facing: float = 1.0  # +1 faces +x (screen right)
    actions: list[Action] = field(default_factory=list)
    present: Callable[[float], bool] = lambda t: True
    wrist_conf: Callable[[float], float] = lambda t: 0.9
    hands: str = "up"  # "up": guard at the chin; "low": arms hanging (nothing in front of the face)

    def pose(self, t: float) -> np.ndarray:
        """[17, 2] joints in torso units (y down). The floor is at y = 1.62 while upright."""
        st: dict = {"x": self.x, "lie": 0.0, "punch": {}, "kick": {}, "head": 0.0, "elbow": {}, "sit": 0.0,
                    "dip": 0.0, "cover": 0.0, "push": 0.0, "step": {}, "leg": {}}
        for act in self.actions:
            act(t, st)
        theta = st["lie"] * math.pi / 2  # falls backwards
        up = np.array([-self.facing * math.sin(theta), -math.cos(theta)])
        fwd = self.facing * np.array([-up[1], up[0]])
        down = -up
        x = st["x"] - self.facing * st["push"]  # pushed backwards
        lowered = st["sit"] + st["dip"]  # hips down, feet stay on the floor
        hip = np.array([x, 1.2 * st["lie"] + lowered])
        sh = hip + up
        ls, rs = sh + 0.25 * fwd, sh - 0.25 * fwd
        lh, rh = hip + 0.15 * fwd, hip - 0.15 * fwd
        # guard: hands near the chin, so a straight punch travels ~0.8 torso lengths
        if self.hands == "low":
            wrists = {"l": ls + 0.1 * fwd + 1.0 * down, "r": rs + 0.1 * fwd + 1.0 * down}
        else:
            wrists = {"l": ls + 0.30 * fwd + 0.15 * down, "r": rs + 0.42 * fwd + 0.12 * down}
        if st["cover"]:  # forearms up in front of the face
            side = np.array([up[1], -up[0]])
            face = sh + 0.35 * up
            for hand, s_ in (("l", 1), ("r", -1)):
                cover = face + 0.3 * fwd + 0.07 * s_ * side
                wrists[hand] = wrists[hand] + (cover - wrists[hand]) * st["cover"]
        for hand, (k, height, direction) in st["punch"].items():
            base = ls if hand == "l" else rs
            reach = base + 1.13 * direction * fwd + height * down
            wrists[hand] = wrists[hand] + (reach - wrists[hand]) * k
        ankles = {"l": lh + 0.25 * fwd + 1.62 * down, "r": rh - 0.25 * fwd + 1.62 * down}
        if lowered and not st["lie"]:
            for foot in ankles:
                ankles[foot][1] = 1.62
                ankles[foot] = ankles[foot] + 0.9 * st["sit"] * fwd  # sitting: legs out in front
        for foot, dx in st["step"].items():
            ankles[foot] = ankles[foot] + dx * fwd
        for foot, dx in st["leg"].items():
            ankles[foot] = ankles[foot] - dx * fwd  # the struck leg is knocked back
        for foot, (k, height) in st["kick"].items():
            base = lh if foot == "l" else rh
            target = base + 1.55 * fwd + height * up
            ankles[foot] = ankles[foot] + (target - ankles[foot]) * k
        le, lw = _ik(ls, wrists["l"], UPPER_ARM, FOREARM, down)
        re, rw = _ik(rs, wrists["r"], UPPER_ARM, FOREARM, down)
        for hand, (k, height) in st["elbow"].items():  # elbow leads forward, forearm folded back
            base = ls if hand == "l" else rs
            strike_e = base + 0.6 * fwd - 0.1 * down + height * down
            strike_w = base + 0.15 * fwd + 0.05 * down + height * down
            if hand == "l":
                le, lw = le + (strike_e - le) * k, lw + (strike_w - lw) * k
            else:
                re, rw = re + (strike_e - re) * k, rw + (strike_w - rw) * k
        lk, la = _ik(lh, ankles["l"], THIGH, SHIN, fwd)
        rk, ra = _ik(rh, ankles["r"], THIGH, SHIN, fwd)
        nose = sh + 0.35 * up + 0.1 * fwd - st["head"] * fwd  # head snapped back
        side = np.array([up[1], -up[0]])
        return np.array([nose, nose + 0.05 * up + 0.04 * side, nose + 0.05 * up - 0.04 * side,
                         nose + 0.12 * side - 0.08 * fwd, nose - 0.12 * side - 0.08 * fwd,
                         ls, rs, le, re, lw, rw, lh, rh, lk, rk, la, ra])


def punch(t0: float, hand: str = "l", out_s: float = 0.12, hold_s: float = 0.04, back_s: float = 0.16,
          height: float = 0.0, direction: float = 1.0) -> Action:
    """Straight punch from the guard to full reach (direction -1: away from the opponent)."""
    def act(t: float, st: dict) -> None:
        if t0 <= t <= t0 + out_s + hold_s + back_s:
            k = ease((t - t0) / out_s) if t < t0 + out_s + hold_s else 1 - ease((t - t0 - out_s - hold_s) / back_s)
            st["punch"][hand] = (k, height, direction)
    return act


def kick(t0: float, foot: str = "r", out_s: float = 0.2, back_s: float = 0.25, height: float = 0.6) -> Action:
    def act(t: float, st: dict) -> None:
        if t0 <= t <= t0 + out_s + back_s:
            k = ease((t - t0) / out_s) if t < t0 + out_s else 1 - ease((t - t0 - out_s) / back_s)
            st["kick"][foot] = (k, height)
    return act


def head_snap(t0: float, amount: float = 0.45, out_s: float = 0.08, back_s: float = 0.3) -> Action:
    """The head is thrown back relative to the shoulders (what a landed strike does)."""
    def act(t: float, st: dict) -> None:
        if t0 <= t <= t0 + out_s + back_s:
            k = ease((t - t0) / out_s) if t < t0 + out_s else 1 - ease((t - t0 - out_s) / back_s)
            st["head"] = amount * k
    return act


def _pulse(t: float, t0: float, out_s: float, back_s: float | None) -> float | None:
    """0..1 going out over out_s and (back_s given) back over back_s; None outside."""
    if t < t0 or (back_s is not None and t > t0 + out_s + back_s):
        return None
    if t < t0 + out_s or back_s is None:
        return ease((t - t0) / out_s)
    return 1 - ease((t - t0 - out_s) / back_s)


def elbow(t0: float, hand: str = "r", out_s: float = 0.12, back_s: float = 0.2, height: float = 0.0) -> Action:
    """The elbow swings forward at shoulder height with the forearm folded back."""
    def act(t: float, st: dict) -> None:
        k = _pulse(t, t0, out_s, back_s)
        if k is not None:
            st["elbow"][hand] = (k, height)
    return act


def sit(t0: float, duration_s: float = 0.4, depth: float = 1.0) -> Action:
    """Down to the floor sitting upright, legs out in front (as against the cage after a knockdown)."""
    def act(t: float, st: dict) -> None:
        k = _pulse(t, t0, duration_s, None)
        if k is not None:
            st["sit"] = depth * k
    return act


def dip(t0: float, amount: float = 0.35, out_s: float = 0.15, back_s: float = 0.4) -> Action:
    """The knees give way and the hips dip, then come back (feet stay on the floor)."""
    def act(t: float, st: dict) -> None:
        k = _pulse(t, t0, out_s, back_s)
        if k is not None:
            st["dip"] = amount * k
    return act


def cover(t0: float, t1: float) -> Action:
    """Both forearms up in front of the face between t0 and t1."""
    def act(t: float, st: dict) -> None:
        if t0 <= t <= t1:
            st["cover"] = min(ease((t - t0) / 0.15), ease((t1 - t) / 0.15))
    return act


def pushed(t0: float, dist: float = 0.4, out_s: float = 0.15) -> Action:
    """The whole body is pushed backwards (a hard body shot)."""
    def act(t: float, st: dict) -> None:
        k = _pulse(t, t0, out_s, None)
        if k is not None:
            st["push"] = dist * k
    return act


def step(t0: float, foot: str = "r", dx: float = 0.8, out_s: float = 0.12) -> Action:
    """One foot moves quickly along the facing direction and stays (the stance width changes)."""
    def act(t: float, st: dict) -> None:
        k = _pulse(t, t0, out_s, None)
        if k is not None:
            st["step"][foot] = dx * k
    return act


def leg_hit(t0: float, foot: str = "l", amount: float = 0.4, out_s: float = 0.08, back_s: float = 0.3) -> Action:
    """The struck leg is knocked back and returns."""
    def act(t: float, st: dict) -> None:
        k = _pulse(t, t0, out_s, back_s)
        if k is not None:
            st["leg"][foot] = amount * k
    return act


def walk(t0: float, t1: float, speed: float) -> Action:
    """Move the hips along x by `speed` torso units/s between t0 and t1."""
    def act(t: float, st: dict) -> None:
        st["x"] += speed * (min(max(t, t0), t1) - t0)
    return act


def fall(t0: float, duration_s: float = 0.4) -> Action:
    def act(t: float, st: dict) -> None:
        if t >= t0:
            st["lie"] = ease((t - t0) / duration_s)
    return act


@dataclass
class MotionScene:
    fighters: tuple[Fighter, Fighter]
    duration_s: float
    fps: float = 30.0
    torso_px: float = 100.0
    origin: tuple[float, float] = (100.0, 300.0)
    jitter_px: float = 1.0
    pan_px_per_s: float = 0.0  # the camera pans: the whole picture drifts left on screen
    uncertain: Callable[[float, int], bool] = lambda t, fighter: False
    seed: int = 0

    def render(self):
        rng = np.random.default_rng(self.seed)
        n = int(round(self.duration_s * self.fps))
        ts = np.arange(n) / self.fps
        boxes, kps, counts, track = [], [], [], []
        state = np.full((n, 2), 2, np.int8)
        det = np.full((n, 2), -1, np.int64)
        to_ref = np.tile(np.array([[1.0, 0, 0], [0, 1.0, 0]]), (n, 1, 1))
        idx = 0
        for i, t in enumerate(ts):
            shift = -self.pan_px_per_s * t
            to_ref[i, 0, 2] = -shift  # screen pixels -> reference pixels
            count = 0
            for fi, f in enumerate(self.fighters):
                if not f.present(t):
                    continue
                joints = f.pose(t) * self.torso_px + np.array(self.origin)
                joints[:, 0] += shift
                joints += rng.normal(0, self.jitter_px, joints.shape)
                conf = np.full(17, 0.9)
                conf[[9, 10]] = f.wrist_conf(t)
                kps.append(np.concatenate([joints, conf[:, None]], axis=1))
                pad = 0.15 * self.torso_px
                boxes.append([joints[:, 0].min() - pad, joints[:, 1].min() - pad,
                              joints[:, 0].max() + pad, joints[:, 1].max() + pad])
                track.append(fi + 1)
                if not self.uncertain(t, fi):
                    state[i, fi], det[i, fi] = 0, idx
                idx += 1
                count += 1
            counts.append(count)
        arrays = PoseArrays(
            frame_index=np.arange(n, dtype=np.int32), timestamp_ms=ts * 1000.0,
            det_offsets=np.concatenate([[0], np.cumsum(counts)]).astype(np.int64),
            boxes=np.array(boxes, np.float32).reshape(-1, 4), box_conf=np.full(len(boxes), 0.9, np.float32),
            keypoints=np.array(kps, np.float32).reshape(-1, 17, 3))
        camera = CameraTrack(to_ref=to_ref, segment=np.zeros(n, np.int32), known=np.ones(n, bool),
                             inliers=np.full(n, 100, np.int32))
        return arrays, state, det, np.array(track, np.int32), camera
