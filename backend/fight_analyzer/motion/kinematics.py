"""Per-fighter kinematics: joints in stabilized coordinates, body scale,
smoothing and velocities.

- Only frames where the fighter's identity is verified (tracked, or occluded
  with a detection) are used; a joint below `kp_min_conf` is not a
  measurement. One-frame jumps, left/right swaps of the pose model and
  impossible speeds are removed before smoothing.
- Positions are mapped through the camera transform of their frame, so a pan
  or zoom does not look like movement.
- The body scale is the fighter's torso length (mid-shoulders to mid-hips),
  estimated from all visible body segments with typical proportions and the
  largest consistent estimate (a segment can only look shorter when turned
  away from the camera, never longer). Lengths and speeds are expressed in
  these "body units", which also removes the distance to the camera.
- Smoothing is a One-Euro filter driven by real time differences: strong at
  low speed (keypoint jitter), weak at high speed (a punch keeps its peak).
- Velocities are differences of smoothed positions divided by the timestamp
  difference, so nothing depends on the frame rate.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from fight_analyzer.config import MotionSettings
from fight_analyzer.pose.cache import PoseArrays

from .camera import CameraTrack

NOSE, LS, RS, LE, RE, LW, RW, LH, RH, LK, RK, LA, RA = 0, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16
BODY_JOINTS = tuple(range(5, 17))
PAIRS = ((LS, RS), (LE, RE), (LW, RW), (LH, RH), (LK, RK), (LA, RA))
# Body segments and their typical length in torso lengths (adult proportions).
SEGMENTS = (((LS, RS), 0.80), ((LH, RH), 0.60), ((LS, LE), 0.62), ((RS, RE), 0.62), ((LE, LW), 0.52),
            ((RE, RW), 0.52), ((LH, LK), 0.83), ((RH, RK), 0.83), ((LK, LA), 0.83), ((RK, RA), 0.83))
ARM_LENGTH = 0.62 + 0.52
LEG_LENGTH = 0.83 + 0.83

STANDING, GROUNDED, TRANSITION, UNKNOWN = 0, 1, 2, -1


@dataclass
class FighterKinematics:
    present: np.ndarray  # [F] bool: identity verified with a detection
    det: np.ndarray  # [F] int64 global detection index or -1
    run: np.ndarray  # [F] int64 continuity run (same camera segment and tracker id, no long hole) or -1
    image: np.ndarray  # [F, 17, 2] raw image pixels
    conf: np.ndarray  # [F, 17] keypoint confidence
    ok: np.ndarray  # [F, 17] bool: usable measurement
    pos: np.ndarray  # [F, 17, 2] smoothed stabilized pixels (NaN when not ok)
    vel: np.ndarray  # [F, 17, 2] stabilized pixels per second (NaN when unknown)
    scale: np.ndarray  # [F] torso length in stabilized pixels (NaN when unknown)
    center: np.ndarray  # [F, 2] hip centre (stabilized), NaN when a hip is missing
    center_vel: np.ndarray  # [F, 2]
    posture: np.ndarray  # [F] int8 STANDING / GROUNDED / TRANSITION / UNKNOWN
    valid: np.ndarray  # [F] bool: enough of the body measured for signals

    def mid(self, a: int, b: int) -> np.ndarray:
        return (self.pos[:, a] + self.pos[:, b]) / 2

    def ref_vel(self) -> np.ndarray:
        """Velocity of the body reference: hip centre, else shoulder centre."""
        out = self.center_vel.copy()
        sh = (self.vel[:, LS] + self.vel[:, RS]) / 2
        miss = np.isnan(out[:, 0])
        out[miss] = sh[miss]
        return out


def hip_height(k: FighterKinematics) -> np.ndarray:
    """Height of the hip centre above the lower foot, in torso lengths (NaN when not measured).
    Image y grows downwards, so the lower foot is the larger y."""
    lower = np.fmax(k.pos[:, LA, 1], k.pos[:, RA, 1])  # NaN only when neither ankle is measured
    with np.errstate(all="ignore"):
        return (lower - k.center[:, 1]) / k.scale


def _time_window(ts: np.ndarray, idx: np.ndarray, t: int, half_s: float) -> np.ndarray:
    lo = np.searchsorted(ts[idx], ts[t] - half_s, side="left")
    hi = np.searchsorted(ts[idx], ts[t] + half_s, side="right")
    return idx[lo:hi]


def _alpha(cutoff: float, dt: float) -> float:
    tau = 1.0 / (2 * math.pi * cutoff)
    return 1.0 / (1.0 + tau / dt)


def _one_euro(ts: np.ndarray, xy: np.ndarray, ok: np.ndarray, s: MotionSettings, body_px: float,
              max_gap_s: float) -> np.ndarray:
    """One-Euro filter of a 2D track (NaN where not ok); restarts after holes."""
    out = np.full_like(xy, np.nan)
    beta = s.smooth_beta / max(body_px, 1e-6)  # per pixel/s instead of per body unit/s
    x_hat = dx_hat = None
    last_t = None
    for i in np.flatnonzero(ok):
        t = ts[i]
        if x_hat is None or t - last_t > max_gap_s or t <= last_t:
            x_hat, dx_hat = xy[i].copy(), np.zeros(2)
        else:
            dt = t - last_t
            dx = (xy[i] - x_hat) / dt
            dx_hat = dx_hat + _alpha(s.smooth_d_cutoff_hz, dt) * (dx - dx_hat)
            cutoff = s.smooth_min_cutoff_hz + beta * float(np.hypot(*dx_hat))
            x_hat = x_hat + _alpha(cutoff, dt) * (xy[i] - x_hat)
        out[i] = x_hat
        last_t = t
    return out


def _velocity(ts: np.ndarray, pos: np.ndarray, ok: np.ndarray, groups: list[np.ndarray], window_s: float,
              max_gap_s: float) -> np.ndarray:
    """Displacement over a fixed time window centred on each sample (positions
    interpolated in time), divided by that time; shortened at the ends of a
    stretch. The same motion gives the same speed at any frame rate."""
    vel = np.full_like(pos, np.nan)
    half = window_s / 2
    for rows in groups:
        idx = rows[ok[rows]]
        if idx.size < 2:
            continue
        for piece in np.split(idx, np.flatnonzero(np.diff(ts[idx]) > max_gap_s) + 1):
            if piece.size < 2:
                continue
            tv = ts[piece]
            lo = np.maximum(tv - half, tv[0])
            hi = np.minimum(tv + half, tv[-1])
            span = hi - lo
            good = span > 0
            for c in range(2):
                pv = pos[piece, c]
                vel[piece[good], c] = (np.interp(hi[good], tv, pv) - np.interp(lo[good], tv, pv)) / span[good]
    return vel


def _raw_scale(p: np.ndarray, ok: np.ndarray) -> float:
    est = []
    if ok[LS] and ok[RS] and ok[LH] and ok[RH]:
        est.append(float(np.linalg.norm((p[LS] + p[RS]) / 2 - (p[LH] + p[RH]) / 2)))
    for (a, b), ratio in SEGMENTS:
        if ok[a] and ok[b]:
            est.append(float(np.linalg.norm(p[a] - p[b])) / ratio)
    est = sorted(e for e in est if e > 0)
    if not est:
        return math.nan
    return est[-2] if len(est) >= 3 else est[-1]


def _clean(ts: np.ndarray, xy: np.ndarray, ok: np.ndarray, run: np.ndarray, scale: np.ndarray,
           s: MotionSettings) -> None:
    """Drop keypoint errors in place: left/right swaps, one-frame spikes, impossible speeds."""
    n = ts.size
    for a, b in PAIRS:
        for t in range(1, n):
            if run[t] < 0 or run[t] != run[t - 1] or not (ok[t, a] and ok[t, b] and ok[t - 1, a] and ok[t - 1, b]):
                continue
            straight = np.linalg.norm(xy[t, a] - xy[t - 1, a]) + np.linalg.norm(xy[t, b] - xy[t - 1, b])
            crossed = np.linalg.norm(xy[t, a] - xy[t - 1, b]) + np.linalg.norm(xy[t, b] - xy[t - 1, a])
            if crossed < 0.5 * straight and straight > s.spike_body * scale[t]:
                ok[t, a] = ok[t, b] = False
    for j in range(xy.shape[1]):
        for t in range(1, n - 1):
            if not (ok[t - 1, j] and ok[t, j] and ok[t + 1, j]) or not run[t - 1] == run[t] == run[t + 1]:
                continue
            k = (ts[t] - ts[t - 1]) / max(ts[t + 1] - ts[t - 1], 1e-9)
            expected = xy[t - 1, j] + (xy[t + 1, j] - xy[t - 1, j]) * k
            dev = np.linalg.norm(xy[t, j] - expected)
            if dev > s.spike_body * scale[t] and np.linalg.norm(xy[t + 1, j] - xy[t - 1, j]) < 0.5 * dev:
                ok[t, j] = False
        last = None
        for t in range(n):
            if not ok[t, j]:
                continue
            if last is not None and run[last] == run[t] and np.isfinite(scale[t]):
                dt = ts[t] - ts[last]
                if dt > 0 and np.linalg.norm(xy[t, j] - xy[last, j]) / dt > s.max_speed * scale[t]:
                    ok[t, j] = False
                    continue
            last = t


def _posture(p: np.ndarray, ok: np.ndarray, scale: float) -> int:
    if not (ok[LS] and ok[RS] and ok[LH] and ok[RH]) or not np.isfinite(scale):
        return UNKNOWN
    up = (p[LS] + p[RS]) / 2 - (p[LH] + p[RH]) / 2
    angle = math.degrees(math.atan2(abs(up[0]), -up[1]))  # 0 = upright, 90 = horizontal
    hip_y = (p[LH, 1] + p[RH, 1]) / 2
    feet = [p[j, 1] for j in (LA, RA) if ok[j]]
    knees = [p[j, 1] for j in (LK, RK) if ok[j]]
    if angle >= 60:
        # bent over at the waist on his legs (e.g. striking a downed opponent) is not down
        return TRANSITION if feet and (max(feet) - hip_y) / scale >= 1.0 else GROUNDED
    if feet:
        drop = (max(feet) - hip_y) / scale  # how far the lower foot is below the hips
        if angle <= 40 and drop >= 1.0:
            return STANDING
        if drop <= 0.5:
            return GROUNDED
        return TRANSITION
    if knees:
        drop = (max(knees) - hip_y) / scale
        if angle <= 40 and drop >= 0.5:
            return STANDING
        if drop <= 0.2:
            return GROUNDED
        return TRANSITION
    return UNKNOWN


def _mode_filter(ts: np.ndarray, values: np.ndarray, run: np.ndarray, half_s: float) -> np.ndarray:
    out = values.copy()
    known = np.flatnonzero((values != UNKNOWN) & (run >= 0))
    for r in np.unique(run[known]):
        idx = known[run[known] == r]
        for t in idx:
            counts = np.bincount(values[_time_window(ts, idx, t, half_s)], minlength=3)
            out[t] = int(np.argmax(counts))
    return out


def compute(arrays: PoseArrays, state: np.ndarray, det: np.ndarray, track_id: np.ndarray,
            camera: CameraTrack, fighter: int, s: MotionSettings) -> FighterKinematics:
    ts = arrays.timestamp_ms.astype(np.float64) / 1000.0
    n = arrays.frame_count
    present = (state[:, fighter] <= 1) & (det[:, fighter] >= 0)
    d = np.where(present, det[:, fighter], -1)
    image = np.full((n, 17, 2), np.nan)
    conf = np.zeros((n, 17))
    stab = np.full((n, 17, 2), np.nan)
    for t in np.flatnonzero(present):
        kp = arrays.keypoints[d[t]]
        image[t] = kp[:, :2]
        conf[t] = kp[:, 2]
        stab[t] = kp[:, :2] @ camera.to_ref[t][:, :2].T + camera.to_ref[t][:, 2]
    ok = present[:, None] & (conf >= s.kp_min_conf)

    # Continuity runs: same camera segment and tracker id, no hole longer than max_gap_s.
    run = np.full(n, -1, np.int64)
    current, last = -1, None
    for t in np.flatnonzero(present):
        key = (int(camera.segment[t]), int(track_id[d[t]]))
        if last is None or key != last[1] or ts[t] - ts[last[0]] > s.max_gap_s or track_id[d[t]] < 0:
            current += 1
        run[t] = current
        last = (t, key)

    present_idx = np.flatnonzero(run >= 0)
    groups = np.split(present_idx, np.flatnonzero(np.diff(run[present_idx])) + 1) if present_idx.size else []

    raw = np.array([_raw_scale(stab[t], ok[t]) if present[t] else math.nan for t in range(n)])
    scale = np.full(n, np.nan)
    for rows in groups:
        idx = rows[np.isfinite(raw[rows])]
        for t in rows:
            win = _time_window(ts, idx, t, 0.5)
            if win.size == 0:
                win = _time_window(ts, idx, t, 1.5)
            if win.size:
                scale[t] = float(np.median(raw[win]))

    _clean(ts, stab, ok, run, np.where(np.isfinite(scale), scale, np.inf), s)
    pos = np.full_like(stab, np.nan)
    for rows in groups:
        body = float(np.nanmedian(scale[rows])) if np.isfinite(scale[rows]).any() else math.nan
        if not np.isfinite(body):
            continue
        for j in range(17):
            mask = ok[rows, j]
            if mask.any():
                pos[rows, j] = _one_euro(ts[rows], stab[rows, j], mask, s, body, s.max_gap_s)
    ok &= np.isfinite(pos[..., 0]) & np.isfinite(scale)[:, None]
    pos[~ok] = np.nan
    vel = np.stack([_velocity(ts, pos[:, j], ok[:, j], groups, s.velocity_window_s, s.max_gap_s)
                    for j in range(17)], axis=1)

    hips = ok[:, LH] & ok[:, RH]
    center = np.where(hips[:, None], (pos[:, LH] + pos[:, RH]) / 2, np.nan)
    center_vel = np.where(hips[:, None], (vel[:, LH] + vel[:, RH]) / 2, np.nan)
    raw_posture = np.array([_posture(pos[t], ok[t], scale[t]) if present[t] else UNKNOWN for t in range(n)],
                           np.int8)
    posture = _mode_filter(ts, raw_posture, run, 0.15).astype(np.int8)
    valid = present & np.isfinite(scale) & (ok[:, BODY_JOINTS].sum(axis=1) >= 6)
    return FighterKinematics(present=present, det=d, run=run, image=image, conf=conf, ok=ok, pos=pos, vel=vel,
                             scale=scale, center=center, center_vel=center_vel, posture=posture, valid=valid)
