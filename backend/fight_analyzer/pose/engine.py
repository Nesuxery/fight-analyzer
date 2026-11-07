"""Ultralytics YOLO pose inference on decoded frames.

Every detected person is kept; nobody is labelled as a fighter here.
Imports ultralytics/torch lazily, so only the worker pays for them.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path

import numpy as np

from fight_analyzer.contracts import KEYPOINT_COUNT, PoseAnalysisSettings

from .models import ModelError


@dataclass
class FramePoses:
    boxes: np.ndarray  # (n, 4) float32 x1, y1, x2, y2
    conf: np.ndarray  # (n,) float32
    keypoints: np.ndarray  # (n, 17, 3) float32 x, y, confidence


def framework_version() -> str:
    return f"ultralytics {version('ultralytics')}"


class PoseEngine:
    def __init__(self, weights: Path, device: str, settings: PoseAnalysisSettings) -> None:
        from ultralytics import YOLO
        from ultralytics.utils import SETTINGS

        # Offline mode (YOLO_OFFLINE) already stops telemetry; also switch it and the
        # training integrations off in the (data-dir local) settings file.
        off = {k: False for k in ("sync", "clearml", "comet", "dvc", "mlflow", "raytune", "wandb")}
        if any(SETTINGS.get(k) for k in off):
            SETTINGS.update(off)

        self.device = device
        self.settings = settings
        self.model = YOLO(str(weights), task="pose")
        if self.model.task != "pose":
            raise ModelError(f"{weights.name} is not a pose model (task={self.model.task})")
        kpt_shape = list(getattr(self.model.model, "kpt_shape", None) or [])
        if kpt_shape != [KEYPOINT_COUNT, 3]:
            raise ModelError(f"{weights.name}: expected 17x3 COCO keypoints, got {kpt_shape}")

    def infer(self, frames: list[np.ndarray]) -> list[FramePoses]:
        """Run the model on BGR frames (as decoded by OpenCV)."""
        s = self.settings
        results = self.model.predict(frames, imgsz=s.imgsz, conf=s.conf, iou=s.iou,
                                     max_det=s.max_det, device=self.device, verbose=False)
        out: list[FramePoses] = []
        for r in results:
            if r.boxes is None or len(r.boxes) == 0 or r.keypoints is None:
                out.append(FramePoses(np.zeros((0, 4), np.float32), np.zeros((0,), np.float32),
                                      np.zeros((0, KEYPOINT_COUNT, 3), np.float32)))
                continue
            kps = r.keypoints.data.cpu().numpy().astype(np.float32)
            if kps.shape[-1] == 2:  # model without per-joint confidence
                kps = np.concatenate([kps, np.ones(kps.shape[:-1] + (1,), np.float32)], axis=-1)
            out.append(FramePoses(
                boxes=r.boxes.xyxy.cpu().numpy().astype(np.float32),
                conf=r.boxes.conf.cpu().numpy().astype(np.float32),
                keypoints=kps,
            ))
        return out


_ENGINES: dict[tuple[str, str, str], PoseEngine] = {}


def get_engine(weights: Path, device: str, settings: PoseAnalysisSettings) -> PoseEngine:
    """Reuse a loaded model across jobs in the same worker process."""
    key = (str(weights), device, settings.model_dump_json())
    if key not in _ENGINES:
        _ENGINES.clear()
        _ENGINES[key] = PoseEngine(weights, device, settings)
    return _ENGINES[key]
