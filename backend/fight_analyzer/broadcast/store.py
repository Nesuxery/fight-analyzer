"""Cache of the broadcast analysis: cache/broadcast/<key>/ (JSON manifest + reads.npy, no pickle).

The key covers everything the result depends on: the analysis video, the
poses and camera cuts (break detection), the settings and ruleset, the OCR
model and the user's clock rectangle.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import numpy as np

from fight_analyzer.config import BroadcastSettings, RulesetSettings
from fight_analyzer.contracts import (
    SCHEMA_VERSION,
    BroadcastNote,
    NameSuggestion,
    RoundSegment,
    ScorebugRoi,
    ScreenRect,
)
from fight_analyzer.contracts.common import utcnow
from fight_analyzer.fsutil import cache_key, staging_dir

from .analyze import BroadcastData
from .clock import Read

BROADCAST_VERSION = 1
MANIFEST = "manifest.json"
READS = "reads.npy"


def key(video_key: str, pose_key: str, prep_key: str, s: BroadcastSettings, ruleset: RulesetSettings,
        ocr_id: str | None, manual: ScreenRect | None) -> tuple[str, dict]:
    inputs = {"kind": "broadcast", "version": BROADCAST_VERSION, "video_key": video_key, "pose_key": pose_key,
              "prep_key": prep_key, "settings": asdict(s), "ruleset": asdict(ruleset), "ocr": ocr_id,
              "manual_clock": manual.model_dump(mode="json") if manual else None}
    return cache_key(inputs), inputs


def entry_dir(cache_root: Path, k: str) -> Path:
    return cache_root / "broadcast" / k


def write(cache_root: Path, k: str, inputs: dict, data: BroadcastData) -> None:
    with staging_dir(entry_dir(cache_root, k)) as stage:
        arr = np.array([[r.t, r.clock, -1 if r.round is None else r.round, r.conf] for r in data.reads],
                       np.float64).reshape(-1, 4)
        np.save(stage / READS, arr, allow_pickle=False)
        manifest = {"schema_version": SCHEMA_VERSION, "cache_key": k, "key_inputs": inputs,
                    "created_at": utcnow().isoformat(),
                    "roi": data.roi.model_dump(mode="json") if data.roi else None,
                    "names": data.names.model_dump(mode="json") if data.names else None,
                    "rounds": [r.model_dump(mode="json") for r in data.rounds],
                    "notes": [n.model_dump(mode="json") for n in data.notes],
                    "clock_share": data.clock_share, "processing_s": data.processing_s}
        (stage / MANIFEST).write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def read(cache_root: Path, k: str) -> BroadcastData | None:
    d = entry_dir(cache_root, k)
    try:
        m = json.loads((d / MANIFEST).read_text(encoding="utf-8"))
        if m.get("cache_key") != k:
            return None
        arr = np.load(d / READS, allow_pickle=False)
        if arr.ndim != 2 or arr.shape[1] != 4:
            return None
        reads = [Read(t=float(t), clock=float(c), round=None if r < 0 else int(r), conf=float(q))
                 for t, c, r, q in arr.tolist()]
        return BroadcastData(
            reads=reads, roi=ScorebugRoi.model_validate(m["roi"]) if m["roi"] else None,
            names=NameSuggestion.model_validate(m["names"]) if m["names"] else None,
            rounds=[RoundSegment.model_validate(r) for r in m["rounds"]],
            notes=[BroadcastNote.model_validate(n) for n in m["notes"]],
            clock_share=float(m["clock_share"]), processing_s=float(m["processing_s"]))
    except (OSError, ValueError, KeyError):
        return None
