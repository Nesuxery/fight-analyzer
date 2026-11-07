"""Camera motion from the background: known pans/zooms, fixed broadcast graphics,
moving people, and frames where nothing can be measured."""

from __future__ import annotations

import cv2
import numpy as np

from fight_analyzer.config import MotionSettings
from fight_analyzer.motion import camera
from fight_analyzer.pose.cache import PoseArrays

S = MotionSettings()
W, H = 960, 540


def texture(seed: int, w: int = 1800, h: int = 900) -> np.ndarray:
    rng = np.random.default_rng(seed)
    img = cv2.GaussianBlur(rng.integers(0, 255, (h, w, 3), dtype=np.uint8), (0, 0), 2)
    for _ in range(400):  # strong corners, like cage mesh, logos and spectators
        x, y = int(rng.integers(0, w - 40)), int(rng.integers(0, h - 40))
        cv2.rectangle(img, (x, y), (x + int(rng.integers(8, 40)), y + int(rng.integers(8, 40))),
                      tuple(int(c) for c in rng.integers(0, 255, 3)), -1)
    return img


def graphics(frame: np.ndarray) -> None:
    """A score bar fixed on screen."""
    cv2.rectangle(frame, (200, 470), (760, 520), (20, 20, 20), -1)
    for x in range(220, 740, 26):
        cv2.putText(frame, "8", (x, 508), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)


def person(frame: np.ndarray, t: int) -> list[float]:
    """Someone moving on his own (must not count as camera motion); returns his box."""
    x = 300 + 12 * t
    cv2.rectangle(frame, (x, 150), (x + 120, 420), (40, 60, 200), -1)
    for k in range(6):
        cv2.circle(frame, (x + 20 + 15 * k, 200 + 30 * k), 6, (250, 250, 250), -1)
    return [x, 150, x + 120, 420]


def arrays_for(boxes: list[list[list[float]]]) -> PoseArrays:
    n = len(boxes)
    counts = [len(b) for b in boxes]
    flat = [box for frame in boxes for box in frame]
    return PoseArrays(frame_index=np.arange(n, dtype=np.int32), timestamp_ms=np.arange(n) * 1000 / 30,
                      det_offsets=np.concatenate([[0], np.cumsum(counts)]).astype(np.int64),
                      boxes=np.array(flat, np.float32).reshape(-1, 4), box_conf=np.ones(len(flat), np.float32),
                      keypoints=np.zeros((len(flat), 17, 3), np.float32))


def test_pan_is_measured_from_the_background_not_graphics_or_people():
    tex = texture(1)
    frames, boxes = [], []
    for t in range(40):
        f = tex[100:100 + H, 50 + 3 * t:50 + 3 * t + W].copy()  # camera pans right 3 px/frame
        boxes.append([person(f, t)])
        graphics(f)
        frames.append(f)
    track = camera.estimate(frames, arrays_for(boxes), np.zeros(40, np.int32), S)
    assert track.known[1:].all() and (track.segment == 0).all()
    shift = track.to_ref[:, 0, 2]  # screen x -> first-frame x = screen + 3t
    assert np.abs(shift - 3 * np.arange(40)).max() < 1.0
    assert np.abs(track.to_ref[:, :, :2] - np.eye(2)).max() < 0.01


def test_zoom_is_measured():
    tex = texture(2)
    frames = []
    for t in range(30):
        z = 1 + 0.004 * t
        m = cv2.getRotationMatrix2D((900, 450), 0, z)
        f = cv2.warpAffine(tex, m, (tex.shape[1], tex.shape[0]))[450 - H // 2:450 + H // 2, 900 - W // 2:900 + W // 2]
        frames.append(f.copy())
    track = camera.estimate(frames, arrays_for([[] for _ in range(30)]), np.zeros(30, np.int32), S)
    zoom_to_ref = np.array([camera.zoom(m) for m in track.to_ref])
    assert np.abs(zoom_to_ref - 1 / (1 + 0.004 * np.arange(30))).max() < 0.005


def test_unmeasurable_frames_start_a_new_segment_and_cuts_reset():
    tex = texture(3)
    frames = [tex[:H, 3 * t:3 * t + W].copy() for t in range(10)]
    frames[5] = np.full_like(frames[5], 128)  # nothing to track (e.g. a flash or a blank frame)
    shot = np.array([0] * 8 + [1] * 2, np.int32)
    track = camera.estimate(frames, arrays_for([[] for _ in range(10)]), shot, S)
    assert not track.known[5] and not track.known[6] and not track.known[8]  # blank frame, after it, cut
    assert len(set(track.segment.tolist())) == 4
    assert np.allclose(track.to_ref[8], [[1, 0, 0], [0, 1, 0]])  # each segment starts at its own frame


def test_graphics_found_as_static_across_shots(tmp_path):
    path = tmp_path / "two_shots.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 30, (W, H))
    shots = []
    for shot, seed in enumerate((4, 5)):
        tex = texture(seed)
        if shot:  # another camera angle: a different, brighter part of the arena
            tex = cv2.add(tex, np.full_like(tex, 70))
        for t in range(30):
            f = tex[:H, 2 * t:2 * t + W].copy()
            graphics(f)
            writer.write(f)
            shots.append(shot)
    writer.release()
    mask = camera.overlay_mask(path, np.array(shots, np.int32), 30.0, S)
    assert mask is not None
    f = S.camera_width / W
    bar = mask[int(475 * f):int(515 * f), int(230 * f):int(730 * f)]
    assert bar.mean() > 0.8  # the score bar
    assert mask.mean() < 0.15  # and not the scene


def test_graphics_mask_reads_only_the_longest_shots(tmp_path, monkeypatch):
    """Long broadcasts have hundreds of cuts: memory and work stay bounded."""
    path = tmp_path / "cuts.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 30, (W, H))
    tex = texture(7)
    for t in range(60):
        writer.write(tex[:H, t:t + W].copy())
    writer.release()
    shots = np.array([0] * 30 + list(range(1, 31)), np.int32)  # one long shot, then 30 one-frame shots
    read = []
    real = camera._small_gray
    monkeypatch.setattr(camera, "_small_gray", lambda frame, width: read.append(1) or real(frame, width))
    monkeypatch.setattr(camera, "MAX_OVERLAY_SHOTS", 2)
    camera.overlay_mask(path, shots, 30.0, S)
    assert len(read) == 4  # samples every 8th frame of shot 0 only (frames 0, 8, 16, 24)
