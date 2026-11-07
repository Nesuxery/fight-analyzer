from __future__ import annotations

import numpy as np
import pytest

from fight_analyzer.contracts import ModelInfo, PoseAnalysisSettings, VideoInfo
from fight_analyzer.pose.cache import (
    CacheCorrupt,
    PoseArrays,
    entry_dir,
    load_arrays,
    pose_cache_key,
    read_manifest,
    write_entry,
)

VIDEO = VideoInfo(width=640, height=360, fps=30, fps_num=30, fps_den=1, frame_count=3,
                  duration_ms=100)
MODEL = ModelInfo(name="yolo26n-pose.pt", framework_version="ultralytics 0", weights_sha256="a" * 64)
SETTINGS = PoseAnalysisSettings(imgsz=640, conf=0.25, iou=0.7, max_det=20)


def _arrays() -> PoseArrays:
    counts = [2, 0, 1]
    n = sum(counts)
    rng = np.random.default_rng(0)
    return PoseArrays(
        frame_index=np.arange(3, dtype=np.int32),
        timestamp_ms=np.arange(3, dtype=np.float64) * 1000 / 30,
        det_offsets=np.array([0, 2, 2, 3], dtype=np.int64),
        boxes=np.tile(np.array([[10, 20, 110, 220]], np.float32), (n, 1)),
        box_conf=np.full(n, 0.9, np.float32),
        keypoints=rng.random((n, 17, 3)).astype(np.float32),
    )


def _write(tmp_path, arrays=None):
    key, inputs = pose_cache_key("b" * 64, MODEL, SETTINGS)
    manifest = write_entry(tmp_path, key, inputs, video=VIDEO, video_sha256="b" * 64, model=MODEL,
                           settings=SETTINGS, arrays=arrays or _arrays(), processing_s=1.0)
    return key, manifest


def test_round_trip_and_frame_records(tmp_path):
    key, manifest = _write(tmp_path)
    assert read_manifest(tmp_path, key) == manifest
    assert manifest.max_persons == 2 and manifest.detection_count == 3
    loaded = load_arrays(tmp_path, manifest)
    np.testing.assert_array_equal(loaded.keypoints, _arrays().keypoints)
    assert [len(loaded.frame(i).detections) for i in range(3)] == [2, 0, 1]
    record = loaded.frame(0)
    assert record.detections[1].detection_id == 1 and len(record.detections[0].keypoints) == 17
    assert not list(tmp_path.glob("pose/.*"))  # staging dir cleaned up


def test_key_covers_video_model_settings_and_format(tmp_path, monkeypatch):
    base, _ = pose_cache_key("b" * 64, MODEL, SETTINGS)
    assert pose_cache_key("c" * 64, MODEL, SETTINGS)[0] != base
    assert pose_cache_key("b" * 64, MODEL.model_copy(update={"weights_sha256": "d" * 64}),
                          SETTINGS)[0] != base
    assert pose_cache_key("b" * 64, MODEL, SETTINGS.model_copy(update={"imgsz": 960}))[0] != base
    # The device is not part of the key: CPU and GPU runs share entries.
    assert pose_cache_key("b" * 64, MODEL.model_copy(update={"device": "cuda:0"}), SETTINGS)[0] == base
    # The stored format decides, not the contract schema: a new optional field elsewhere
    # must not throw away hours of pose extraction.
    monkeypatch.setattr("fight_analyzer.pose.cache.SCHEMA_VERSION", "9.9.9")
    assert pose_cache_key("b" * 64, MODEL, SETTINGS)[0] == base
    monkeypatch.setattr("fight_analyzer.pose.cache.CACHE_FORMAT", 999)
    assert pose_cache_key("b" * 64, MODEL, SETTINGS)[0] != base


def test_tampered_or_pickled_arrays_are_rejected(tmp_path):
    key, manifest = _write(tmp_path)
    d = entry_dir(tmp_path, key)
    kp = d / "keypoints.npy"
    data = bytearray(kp.read_bytes())
    data[-1] ^= 0xFF
    kp.write_bytes(bytes(data))
    with pytest.raises(CacheCorrupt):
        load_arrays(tmp_path, manifest)

    key2, manifest2 = _write(tmp_path / "other")
    boxes = entry_dir(tmp_path / "other", key2) / "boxes.npy"
    np.save(boxes, np.array([{"evil": 1}], dtype=object), allow_pickle=True)
    with pytest.raises(CacheCorrupt):
        load_arrays(tmp_path / "other", manifest2, check_hashes=False)


def test_inconsistent_arrays_are_not_written(tmp_path):
    bad = _arrays()
    bad.det_offsets = np.array([0, 1, 1, 9], dtype=np.int64)
    with pytest.raises(CacheCorrupt):
        _write(tmp_path, bad)
