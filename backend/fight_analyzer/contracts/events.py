"""Fight event timeline contract.

Events are detections from 2D poses, not ground truth: a strike is an
*attempt* (it is not known whether it landed), a 2D overlap of the striking
limb with the opponent is only a *possible* contact, and knockdowns and
takedowns are *possible* events supported by the evidence listed in
`measures`.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from .common import JOB_ID_PATTERN, Contract, DataOrigin, VersionedContract
from .fighters import Fighter, FighterId
from .video import VideoInfo


class EventType(StrEnum):
    """Event categories. Adding a member is a minor schema version bump."""

    punch = "punch"
    kick = "kick"
    knee = "knee"
    clinch = "clinch"
    takedown = "takedown"
    ground_control = "ground_control"
    knockdown = "knockdown"
    stance_change = "stance_change"
    other = "other"


class Limb(StrEnum):
    left_hand = "left_hand"
    right_hand = "right_hand"
    left_foot = "left_foot"
    right_foot = "right_foot"
    left_knee = "left_knee"
    right_knee = "right_knee"


class ImagePoint(Contract):
    """A point in analysis-video pixels."""

    x: float
    y: float


class FightEvent(Contract):
    event_id: str = Field(min_length=1)
    type: EventType
    actor: FighterId | None = Field(default=None, description="Fighter performing the action.")
    target: FighterId | None = Field(default=None, description="Fighter receiving the action.")
    start_frame: int = Field(ge=0)
    end_frame: int = Field(ge=0)
    start_ms: float = Field(ge=0)
    end_ms: float = Field(ge=0)
    peak_frame: int | None = Field(default=None, ge=0, description="Fastest moment of a strike / the fall.")
    peak_ms: float | None = Field(default=None, ge=0)
    limb: Limb | None = None
    possible_contact: bool = Field(
        default=False, description="The striking limb overlapped the opponent in 2D; contact is not certain.")
    location: ImagePoint | None = Field(default=None, description="Striking joint at the peak.")
    measures: dict[str, float] = Field(
        default_factory=dict, description="Measured values behind the detection (body units, seconds, cosines).")
    confidence: float = Field(ge=0, le=1, description="Detector confidence, not ground truth.")
    attribution_confidence: float | None = Field(
        default=None, ge=0, le=1, description=(
            "How sure the identity of the fighter(s) is over the event's frames (the actor; both for an event "
            "without one). None: analysed before identities carried it."))
    attribution_uncertain: bool = Field(
        default=False, description="Below the attribution threshold: 'Kime ait belirsiz'. Not part of the momentum.")
    data_origin: DataOrigin
    note: str | None = None

    @model_validator(mode="after")
    def _ordered(self) -> FightEvent:
        if self.end_frame < self.start_frame or self.end_ms < self.start_ms:
            raise ValueError("event must not end before it starts")
        if self.peak_frame is not None and not self.start_frame <= self.peak_frame <= self.end_frame:
            raise ValueError("peak must lie inside the event")
        return self


class EventTimeline(VersionedContract):
    job_id: str = Field(pattern=JOB_ID_PATTERN)
    data_origin: DataOrigin
    video: VideoInfo
    fighters: list[Fighter] = Field(max_length=2)
    events: list[FightEvent] = Field(default_factory=list)
