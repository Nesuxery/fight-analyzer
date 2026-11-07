from __future__ import annotations

import pytest
from pydantic import ValidationError

from fight_analyzer.contracts import (
    COCO17_KEYPOINT_NAMES,
    SCHEMA_VERSION,
    BoundingBox,
    DataOrigin,
    EventType,
    FightEvent,
    FighterId,
    FrameRecord,
    Keypoint,
    ModelInfo,
    PersonDetection,
    PoseSequence,
    VideoInfo,
)
from fight_analyzer.contracts import export as schema_export

JOB_ID = "0" * 32
VIDEO = VideoInfo(width=1920, height=1080, fps=29.97, frame_count=300, duration_ms=10010.0)


def _person(n_keypoints: int = 17) -> dict:
    return {
        "detection_id": 0,
        "bbox": {"x1": 10, "y1": 20, "x2": 110, "y2": 320},
        "confidence": 0.9,
        "keypoints": [{"x": 50.0, "y": 60.0, "confidence": 0.8}] * n_keypoints,
    }


def test_pose_sequence_round_trip_keeps_version_and_fields():
    seq = PoseSequence(
        job_id=JOB_ID,
        data_origin=DataOrigin.measured,
        video=VIDEO,
        model=ModelInfo(name="yolo26n-pose.pt", device="cpu"),
        frames=[FrameRecord(frame_index=0, timestamp_ms=0.0,
                            detections=[PersonDetection.model_validate(_person())])],
    )
    restored = PoseSequence.model_validate_json(seq.model_dump_json())
    assert restored == seq
    assert restored.schema_version == SCHEMA_VERSION
    assert restored.keypoint_names == list(COCO17_KEYPOINT_NAMES)
    assert restored.frames[0].detections[0].fighter_id is None


@pytest.mark.parametrize("n", [16, 18])
def test_person_requires_exactly_17_keypoints(n):
    with pytest.raises(ValidationError):
        PersonDetection.model_validate(_person(n))


def test_confidence_and_geometry_are_validated():
    with pytest.raises(ValidationError):
        Keypoint(x=0, y=0, confidence=1.5)
    with pytest.raises(ValidationError):
        BoundingBox(x1=100, y1=0, x2=50, y2=10)
    with pytest.raises(ValidationError):
        VideoInfo(width=0, height=1080, fps=30, frame_count=1, duration_ms=1)


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        Keypoint.model_validate({"x": 1, "y": 2, "confidence": 0.5, "z": 3})


def test_event_must_not_end_before_start_and_carries_origin():
    with pytest.raises(ValidationError):
        FightEvent(event_id="e1", type=EventType.punch, start_frame=10, end_frame=5,
                   start_ms=333, end_ms=166, confidence=0.5, data_origin=DataOrigin.measured)
    demo = FightEvent(event_id="e2", type=EventType.kick, actor=FighterId.fighter_a,
                      start_frame=1, end_frame=2, start_ms=33, end_ms=66, confidence=0.4,
                      data_origin=DataOrigin.demo)
    assert demo.model_dump(mode="json")["data_origin"] == "demo"


def test_exported_json_schema_is_up_to_date():
    assert schema_export.SCHEMA_PATH.exists(), "run python -m fight_analyzer.contracts.export"
    assert schema_export.SCHEMA_PATH.read_text(encoding="utf-8") == schema_export.render(), (
        "shared/schemas is stale; run python -m fight_analyzer.contracts.export"
    )
