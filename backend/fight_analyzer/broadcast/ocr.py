"""Single text line recognition with the pinned PP-OCRv5 model (onnxruntime, CPU).

Input: a crop holding one line of text. The model reads BGR images scaled to
48 px height with values in [-1, 1]; its output is a per-column distribution
over [blank] + dictionary + [space], decoded greedily (CTC: repeats merged,
blanks dropped). Runs fully offline; nothing is downloaded here.
"""

from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np
import yaml

from . import ocr_model

HEIGHT = 48
MAX_WIDTH = 960


class Recognizer:
    def __init__(self, model_path: Path, config_path: Path, threads: int = 2) -> None:
        import onnxruntime as ort  # imported here: only analyses that read a scorebug need it

        chars = yaml.safe_load(config_path.read_text(encoding="utf-8"))["PostProcess"]["character_dict"]
        self.labels = ["", *(str(c) for c in chars), " "]
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        options.log_severity_level = 3
        self._session = ort.InferenceSession(str(model_path), options, providers=["CPUExecutionProvider"])
        self._input = self._session.get_inputs()[0].name

    def read(self, crop: np.ndarray) -> tuple[str, float]:
        """Text and mean character confidence (0 when nothing was read)."""
        if crop.ndim == 2:
            crop = cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR)
        h, w = crop.shape[:2]
        if h < 4 or w < 4:
            return "", 0.0
        width = min(MAX_WIDTH, max(16, math.ceil(HEIGHT * w / h)))
        interp = cv2.INTER_CUBIC if h < HEIGHT else cv2.INTER_AREA
        img = cv2.resize(crop, (width, HEIGHT), interpolation=interp).astype(np.float32)
        x = np.ascontiguousarray(((img / 255.0 - 0.5) / 0.5).transpose(2, 0, 1)[None])
        probs = self._session.run(None, {self._input: x})[0][0]
        best = probs.argmax(axis=1)
        conf = probs.max(axis=1)
        text, kept, prev = [], [], -1
        for i, c in zip(best.tolist(), conf.tolist()):
            if i != prev and i != 0 and i < len(self.labels):
                text.append(self.labels[i])
                kept.append(c)
            prev = i
        return "".join(text).strip(), float(np.mean(kept)) if kept else 0.0


def load(models_dir: Path) -> Recognizer | None:
    """The recognizer, or None when the pinned model files are not installed."""
    if not ocr_model.installed(models_dir):
        return None
    folder = ocr_model.folder(models_dir)
    return Recognizer(folder / ocr_model.MODEL.name, folder / ocr_model.CONFIG.name)
