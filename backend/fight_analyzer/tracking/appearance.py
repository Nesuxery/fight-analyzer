"""Appearance descriptor of one person detection.

Two body regions are located from the keypoints: the shorts (hips towards
knees) and the torso (shoulders to hips, shrunk to avoid arms). For each
region the descriptor holds
- a colour histogram (hue x saturation for coloured pixels, 4 brightness
  bins for grey/black/white pixels), and
- a colour-independent texture part: gradient-orientation histogram and the
  mean gradient energy (patterns, stripes, logos, tattoos).
So two fighters wearing the same colour can still differ by texture, and
lighting changes that shift colours do not decide alone.
"""

from __future__ import annotations

import cv2
import numpy as np

H_BINS, S_BINS, ACHRO_BINS, ORI_BINS = 18, 3, 4, 8
COLOR_DIM = H_BINS * S_BINS + ACHRO_BINS  # 58
# Layout: [shorts colour | torso colour | shorts orientation | torso orientation | shorts energy | torso energy]
SLICES = {
    "shorts_color": slice(0, COLOR_DIM),
    "torso_color": slice(COLOR_DIM, 2 * COLOR_DIM),
    "shorts_ori": slice(2 * COLOR_DIM, 2 * COLOR_DIM + ORI_BINS),
    "torso_ori": slice(2 * COLOR_DIM + ORI_BINS, 2 * COLOR_DIM + 2 * ORI_BINS),
    "shorts_energy": slice(2 * COLOR_DIM + 2 * ORI_BINS, 2 * COLOR_DIM + 2 * ORI_BINS + 1),
    "torso_energy": slice(2 * COLOR_DIM + 2 * ORI_BINS + 1, 2 * COLOR_DIM + 2 * ORI_BINS + 2),
}
DIM = 2 * COLOR_DIM + 2 * ORI_BINS + 2
WEIGHTS = {"shorts_color": 0.40, "torso_color": 0.20, "shorts_ori": 0.12, "torso_ori": 0.10,
           "shorts_energy": 0.10, "torso_energy": 0.08}

LS, RS, LH, RH, LK, RK = 5, 6, 11, 12, 13, 14
MIN_KP_CONF = 0.3
MIN_PIXELS = 40


def _shrink(poly: np.ndarray, factor: float) -> np.ndarray:
    c = poly.mean(axis=0)
    return c + (poly - c) * factor


def regions(kps: np.ndarray, box: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """Shorts and torso polygons in frame coordinates and a keypoint quality 0..1."""
    x1, y1, x2, y2 = box
    w, h = max(1.0, x2 - x1), max(1.0, y2 - y1)
    ok = kps[:, 2] >= MIN_KP_CONF
    if ok[[LS, RS, LH, RH]].all():
        shoulders, hips = kps[[LS, RS], :2], kps[[LH, RH], :2]
        torso_h = max(8.0, float(np.linalg.norm(hips.mean(0) - shoulders.mean(0))))
        torso = _shrink(np.array([shoulders[0], shoulders[1], hips[1], hips[0]]), 0.75)
        hip_mid = hips.mean(0)
        half = max(float(np.abs(hips[0, 0] - hips[1, 0])) * 0.65, 0.18 * w, 0.22 * torso_h)
        if ok[[LK, RK]].all():
            down = (kps[[LK, RK], :2].mean(0) - hip_mid) * 0.45
        else:
            down = np.array([0.0, 0.3 * torso_h])
        top = hip_mid - down * 0.15
        shorts = np.array([top + [-half, 0], top + [half, 0], top + down + [half, 0], top + down + [-half, 0]])
        quality = float(kps[[LS, RS, LH, RH], 2].mean())
    else:  # fall back to fixed fractions of the box
        torso = np.array([[x1 + 0.3 * w, y1 + 0.22 * h], [x1 + 0.7 * w, y1 + 0.22 * h],
                          [x1 + 0.7 * w, y1 + 0.48 * h], [x1 + 0.3 * w, y1 + 0.48 * h]])
        shorts = np.array([[x1 + 0.28 * w, y1 + 0.5 * h], [x1 + 0.72 * w, y1 + 0.5 * h],
                           [x1 + 0.72 * w, y1 + 0.66 * h], [x1 + 0.28 * w, y1 + 0.66 * h]])
        quality = 0.25
    return shorts.astype(np.float32), torso.astype(np.float32), quality


def _region_features(hsv: np.ndarray, gray_mag: np.ndarray, gray_ori: np.ndarray,
                     mask: np.ndarray) -> tuple[np.ndarray, np.ndarray, float, int]:
    sel = mask > 0
    n = int(sel.sum())
    color = np.zeros(COLOR_DIM, np.float32)
    ori = np.zeros(ORI_BINS, np.float32)
    if n < MIN_PIXELS:
        return color, ori, 0.0, n
    h, s, v = hsv[..., 0][sel], hsv[..., 1][sel], hsv[..., 2][sel]
    chroma = (s >= 50) & (v >= 40)
    hb = np.minimum((h[chroma].astype(np.int32) * H_BINS) // 180, H_BINS - 1)
    sb = np.minimum(((s[chroma].astype(np.int32) - 50) * S_BINS) // 206, S_BINS - 1)
    np.add.at(color, hb * S_BINS + sb, 1)
    vb = np.minimum(v[~chroma].astype(np.int32) * ACHRO_BINS // 256, ACHRO_BINS - 1)
    np.add.at(color, H_BINS * S_BINS + vb, 1)
    color /= max(1.0, float(color.sum()))
    mag, angle = gray_mag[sel], gray_ori[sel]
    ob = np.minimum((angle * ORI_BINS / np.pi).astype(np.int32), ORI_BINS - 1)
    np.add.at(ori, ob, mag)
    total = float(ori.sum())
    if total > 0:
        ori /= total
    else:
        ori[:] = 1.0 / ORI_BINS
    energy = float(min(1.0, mag.mean() / 64.0))
    return color, ori, energy, n


def describe(frame_bgr: np.ndarray, kps: np.ndarray, box: np.ndarray) -> tuple[np.ndarray, float]:
    """Descriptor (float32[DIM]) and its quality 0..1 for one detection."""
    shorts, torso, kp_quality = regions(kps, box)
    pts = np.concatenate([shorts, torso])
    fh, fw = frame_bgr.shape[:2]
    x0, y0 = np.floor(pts.min(0)).astype(int)
    x1, y1 = np.ceil(pts.max(0)).astype(int)
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(fw, x1 + 1), min(fh, y1 + 1)
    vec = np.zeros(DIM, np.float32)
    if x1 - x0 < 4 or y1 - y0 < 4:
        return vec, 0.0
    crop = frame_bgr[y0:y1, x0:x1]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.sqrt(gx * gx + gy * gy)
    ori = np.mod(np.arctan2(gy, gx), np.pi)
    sizes = []
    for name, poly in (("shorts", shorts), ("torso", torso)):
        mask = np.zeros(crop.shape[:2], np.uint8)
        cv2.fillConvexPoly(mask, np.round(poly - [x0, y0]).astype(np.int32), 1)
        color, orient, energy, n = _region_features(hsv, mag, ori, mask)
        vec[SLICES[f"{name}_color"]] = color
        vec[SLICES[f"{name}_ori"]] = orient
        vec[SLICES[f"{name}_energy"]] = energy
        sizes.append(n)
    if min(sizes) < MIN_PIXELS:
        return vec, 0.0
    size_quality = min(1.0, min(sizes) / 400.0)
    return vec, float(kp_quality * (0.5 + 0.5 * size_quality))


def similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Weighted similarity 0..1 between descriptor sets a[n,D] and b[m,D] -> [n,m]."""
    a = np.atleast_2d(a).astype(np.float32)
    b = np.atleast_2d(b).astype(np.float32)
    out = np.zeros((a.shape[0], b.shape[0]), np.float32)
    for name, weight in WEIGHTS.items():
        sl = SLICES[name]
        if name.endswith("energy"):
            ea, eb = a[:, sl], b[:, sl].T
            out += weight * (1.0 - np.abs(ea - eb) / (ea + eb + 1e-3))
        else:  # Bhattacharyya coefficient of two distributions
            out += weight * (np.sqrt(np.maximum(a[:, sl], 0)) @ np.sqrt(np.maximum(b[:, sl], 0)).T)
    return np.clip(out, 0.0, 1.0)


def mean_descriptor(vectors: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """Quality-weighted average of descriptors (stays a set of distributions)."""
    w = np.asarray(weights, np.float32)
    if vectors.shape[0] == 0 or float(w.sum()) <= 0:
        return np.zeros(DIM, np.float32)
    return (vectors * w[:, None]).sum(0) / float(w.sum())
