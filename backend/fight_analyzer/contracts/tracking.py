"""Fighter selection and identity tracking contracts.

Two kinds of ids are kept apart on purpose:
- track_id: short-lived tracker id (OC-SORT) inside one camera shot; it may
  change after occlusions and always changes at a camera cut.
- fighter_id: the persistent identity the user selected (fighter_a = red
  corner, fighter_b = blue corner). Frames where it cannot be verified are
  marked `uncertain`; no identity is guessed for them.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from .common import JOB_ID_PATTERN, Contract, VersionedContract
from .fighters import FighterId, TrackState
from .pose import PersonDetection
from .video import VideoInfo


class UncertainReason(StrEnum):
    camera_cut = "camera_cut"  # new shot, appearance not convincing yet
    overlap = "overlap"  # long overlap/clinch or ambiguous crossing
    lost = "lost"  # not detected / out of frame for too long
    ambiguous = "ambiguous"  # candidates look too similar to decide
    anchor_conflict = "anchor_conflict"  # two selections disagree here


class FighterAnchor(Contract):
    """A user selection: on `frame_index`, detection ids (as in that frame's
    FrameRecord) of the red and blue corner fighters. `None` means the user
    marked that fighter as not in the picture on this frame (close-ups)."""

    frame_index: int = Field(ge=0)
    red_detection_id: int | None = Field(default=None, ge=0)
    blue_detection_id: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _distinct(self) -> FighterAnchor:
        if self.red_detection_id is None and self.blue_detection_id is None:
            raise ValueError("select at least one fighter on the frame")
        if self.red_detection_id == self.blue_detection_id:
            raise ValueError("the same person cannot be both fighters")
        return self

    def detection_ids(self) -> tuple[int | None, int | None]:
        return self.red_detection_id, self.blue_detection_id


class FighterSelection(Contract):
    anchors: list[FighterAnchor] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def _unique_frames(self) -> FighterSelection:
        frames = [a.frame_index for a in self.anchors]
        if len(set(frames)) != len(frames):
            raise ValueError("only one selection per frame")
        if all(a.red_detection_id is None for a in self.anchors):
            raise ValueError("the red corner fighter must be selected on at least one frame")
        if all(a.blue_detection_id is None for a in self.anchors):
            raise ValueError("the blue corner fighter must be selected on at least one frame")
        return self


class FighterNames(Contract):
    red: str = Field(min_length=1, max_length=40)
    blue: str = Field(min_length=1, max_length=40)


class SelectionCandidate(Contract):
    frame_index: int = Field(ge=0)
    timestamp_ms: float = Field(ge=0)
    shot_index: int = Field(ge=0)
    score: float = Field(ge=0, le=1, description="How well both fighters are visible and separated.")
    detections: list[PersonDetection]


class SelectionCandidates(VersionedContract):
    job_id: str = Field(pattern=JOB_ID_PATTERN)
    video: VideoInfo
    frames: list[SelectionCandidate]


class ShotInfo(Contract):
    index: int = Field(ge=0)
    start_frame: int = Field(ge=0)
    end_frame: int = Field(ge=0)


class UncertainSegment(Contract):
    fighter_id: FighterId
    start_frame: int = Field(ge=0)
    end_frame: int = Field(ge=0)
    reason: UncertainReason


class ReviewPoint(Contract):
    """Moment worth checking by eye (identity re-found with a small margin,
    a tracker swap that was overridden, ...)."""

    frame_index: int = Field(ge=0)
    fighter_id: FighterId
    kind: str = Field(description="reacquired_low_margin | swap_corrected | after_cut")
    margin: float | None = None


class FighterTrackStats(Contract):
    fighter_id: FighterId
    tracked_frames: int = Field(ge=0)
    occluded_frames: int = Field(ge=0)
    uncertain_frames: int = Field(ge=0)
    uncertain_ms: float = Field(ge=0)
    longest_uncertain_ms: float = Field(ge=0)
    reacquisitions: int = Field(ge=0, description="Identity re-found after loss or a camera cut.")
    track_changes: int = Field(ge=0, description="Times the temporary tracker id under this fighter changed.")
    mean_confidence: float = Field(ge=0, le=1)


class TrackingPrepSummary(Contract):
    """Selection-independent preparation (cuts, tracklets, appearance)."""

    cache_key: str
    cache_hit: bool
    shots: int = Field(ge=0)
    cuts: list[int] = Field(description="Frames where a new camera shot starts.")
    tracklets: int = Field(ge=0)
    candidates: int = Field(ge=0)
    tracker: str = Field(description="Short-term tracker used inside shots.")


class TrackingSummary(Contract):
    cache_key: str
    cache_hit: bool
    method: str
    anchors: list[FighterAnchor]
    shots: list[ShotInfo]
    fighters: list[FighterTrackStats]
    identity_switches: int = Field(
        ge=0, description="Times a fighter's identity moved directly onto a track another person held.")
    swap_corrections: int = Field(
        ge=0, description="Tracker continuations rejected because appearance pointed to someone else.")
    anchor_conflicts: int = Field(ge=0)
    uncertain_segments: list[UncertainSegment]
    review_points: list[ReviewPoint]


class TrackStateRun(Contract):
    start_frame: int = Field(ge=0)
    end_frame: int = Field(ge=0)
    state: TrackState


class FighterTimeline(Contract):
    fighter_id: FighterId
    runs: list[TrackStateRun]


class TrackingTimeline(VersionedContract):
    """Run-length encoded identity states for the whole video (for the UI timeline)."""

    job_id: str = Field(pattern=JOB_ID_PATTERN)
    frame_count: int = Field(ge=0)
    fps: float = Field(gt=0)
    cuts: list[int]
    fighters: list[FighterTimeline]
