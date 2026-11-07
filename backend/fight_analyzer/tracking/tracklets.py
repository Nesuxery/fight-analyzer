"""Short-term tracklets inside camera shots.

Ultralytics' OC-SORT links detections frame to frame with a Kalman motion
model and IoU (no appearance). It is reset at every camera cut: across a cut
its predictions point to where people were in the previous shot, so it would
either start new ids or, worse, bind whoever happens to stand there.

The tracker's ids are only temporary. Tracks are further split wherever the
person overlaps someone else (clinch, crossing, referee stepping in) or the
track skips frames, so every segment is either a clean stretch of one person
or an explicitly ambiguous "contact" stretch.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from fight_analyzer.config import TrackingSettings
from fight_analyzer.pose.cache import PoseArrays


class _Detections:
    """Minimal Results-like view the Ultralytics trackers accept."""

    def __init__(self, xyxy: np.ndarray, conf: np.ndarray) -> None:
        self.xyxy = xyxy.astype(np.float32)
        self.conf = conf.astype(np.float32)
        self.cls = np.zeros(len(conf), np.float32)
        wh = self.xyxy[:, 2:4] - self.xyxy[:, 0:2]
        self.xywh = np.concatenate([self.xyxy[:, 0:2] + wh / 2, wh], axis=1)

    def __len__(self) -> int:
        return len(self.conf)

    def __getitem__(self, mask) -> _Detections:
        return _Detections(self.xyxy[mask], self.conf[mask])


def tracker_name(s: TrackingSettings) -> str:
    from importlib.metadata import version

    return f"Ultralytics {s.tracker} ({version('ultralytics')})"


def _make_tracker(s: TrackingSettings, fps: float):
    import ultralytics
    from ultralytics.trackers.track import TRACKER_MAP
    from ultralytics.utils import YAML, IterableSimpleNamespace

    cfg_path = Path(ultralytics.__file__).parent / "cfg" / "trackers" / f"{s.tracker}.yaml"
    cfg = IterableSimpleNamespace(**YAML.load(cfg_path))
    cfg.track_buffer = max(1, round(fps * 0.5))  # keep lost tracks briefly; identity layer bridges longer gaps
    return TRACKER_MAP[cfg.tracker_type](args=cfg)


def run_tracker(arrays: PoseArrays, shot_id: np.ndarray, s: TrackingSettings, fps: float,
                on_frame=None) -> np.ndarray:
    """Temporary track id per detection (-1 when the tracker did not confirm it)."""
    track_id = np.full(arrays.detection_count, -1, np.int32)
    global_ids: dict[tuple[int, int], int] = {}
    tracker = None
    current_shot = -1
    for t in range(arrays.frame_count):
        if shot_id[t] != current_shot:  # new shot: forget all motion state
            current_shot = int(shot_id[t])
            tracker = _make_tracker(s, fps)
        a, b = int(arrays.det_offsets[t]), int(arrays.det_offsets[t + 1])
        out = tracker.update(_Detections(arrays.boxes[a:b], arrays.box_conf[a:b]))
        for row in np.atleast_2d(out) if len(out) else []:
            local, idx = int(row[4]), int(row[7])
            key = (current_shot, local)
            if key not in global_ids:
                global_ids[key] = len(global_ids)
            track_id[a + idx] = global_ids[key]
        if on_frame:
            on_frame(t)
    return track_id


def _iou_cover(boxes: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    x1 = np.maximum(boxes[:, None, 0], boxes[None, :, 0])
    y1 = np.maximum(boxes[:, None, 1], boxes[None, :, 1])
    x2 = np.minimum(boxes[:, None, 2], boxes[None, :, 2])
    y2 = np.minimum(boxes[:, None, 3], boxes[None, :, 3])
    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    area = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    union = area[:, None] + area[None, :] - inter
    iou = inter / np.maximum(union, 1e-6)
    cover = inter / np.maximum(np.minimum(area[:, None], area[None, :]), 1e-6)
    np.fill_diagonal(iou, 0)
    np.fill_diagonal(cover, 0)
    return iou, cover


def contact_flags(arrays: PoseArrays, s: TrackingSettings, min_height_ratio: float = 0.35) -> np.ndarray:
    """Detections overlapping another comparable-size person in the same frame.
    Small background people (crowd) overlapping a fighter do not count."""
    contact = np.zeros(arrays.detection_count, bool)
    for t in range(arrays.frame_count):
        a, b = int(arrays.det_offsets[t]), int(arrays.det_offsets[t + 1])
        if b - a < 2:
            continue
        boxes = arrays.boxes[a:b]
        iou, cover = _iou_cover(boxes)
        h = boxes[:, 3] - boxes[:, 1]
        comparable = np.minimum(h[:, None], h[None, :]) >= min_height_ratio * np.maximum(h[:, None], h[None, :])
        hit = ((iou >= s.contact_iou) | (cover >= s.contact_cover)) & comparable
        contact[a:b] = hit.any(axis=1)
    return contact


@dataclass
class Segment:
    id: int
    track: int  # temporary tracker id (-1: unconfirmed single detection)
    shot: int
    contact: bool
    dets: np.ndarray  # global detection indices, in frame order
    frames: np.ndarray

    @property
    def start(self) -> int:
        return int(self.frames[0])

    @property
    def end(self) -> int:
        return int(self.frames[-1])


def build_segments(det_frame: np.ndarray, track_id: np.ndarray, contact: np.ndarray,
                   shot_id: np.ndarray, s: TrackingSettings) -> np.ndarray:
    """Segment id per detection: tracks split at contact changes and gaps."""
    seg_id = np.full(len(det_frame), -1, np.int32)
    next_id = 0
    order = np.lexsort((det_frame, track_id))
    prev = None
    for d in order:
        tid = int(track_id[d])
        if tid < 0:
            seg_id[d] = next_id
            next_id += 1
            prev = None
            continue
        if (prev is not None and int(track_id[prev]) == tid
                and int(shot_id[det_frame[d]]) == int(shot_id[det_frame[prev]])
                and bool(contact[d]) == bool(contact[prev])
                and int(det_frame[d]) - int(det_frame[prev]) <= s.split_gap_frames):
            seg_id[d] = seg_id[prev]
        else:
            seg_id[d] = next_id
            next_id += 1
        prev = d
    return seg_id


def segments_from(seg_id: np.ndarray, det_frame: np.ndarray, track_id: np.ndarray,
                  contact: np.ndarray, shot_id: np.ndarray) -> list[Segment]:
    order = np.lexsort((det_frame, seg_id))
    bounds = np.flatnonzero(np.diff(seg_id[order])) + 1
    out: list[Segment] = []
    for group in np.split(order, bounds):
        if group.size == 0:
            continue
        sid = int(seg_id[group[0]])
        frames = det_frame[group]
        out.append(Segment(id=sid, track=int(track_id[group[0]]), shot=int(shot_id[frames[0]]),
                           contact=bool(contact[group[0]]), dets=group.astype(np.int64),
                           frames=frames.astype(np.int64)))
    out.sort(key=lambda seg: seg.id)
    return out
