"""Fighter identity contracts."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from .common import Contract


class FighterId(StrEnum):
    """Stable identity of the two fighters chosen by the user."""

    fighter_a = "fighter_a"  # red corner
    fighter_b = "fighter_b"  # blue corner


class Fighter(Contract):
    fighter_id: FighterId
    display_name: str = Field(min_length=1, max_length=80)
    color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$", description="Skeleton/overlay colour.")


class TrackState(StrEnum):
    tracked = "tracked"  # identity verified on this detection
    occluded = "occluded"  # short overlap/occlusion: identity kept, detection may be missing
    uncertain = "uncertain"  # identity could not be verified ("Takip belirsiz")


class FighterFrameState(Contract):
    """Identity state of one fighter in one frame."""

    fighter_id: FighterId
    state: TrackState
    detection_id: int | None = Field(default=None, description="Detection in this frame, if any.")
    confidence: float = Field(ge=0, le=1)
