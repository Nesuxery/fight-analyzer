"""Fighter identity contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, TypeVar, cast

from pydantic import BaseModel, Field

from .common import Contract

T = TypeVar("T")


class FighterId(StrEnum):
    """Stable identity of the two fighters chosen by the user."""

    fighter_a = "fighter_a"  # red corner
    fighter_b = "fighter_b"  # blue corner


def other_fighter(fighter_id: FighterId) -> FighterId:
    """The opponent of `fighter_id`."""
    return FighterId.fighter_b if fighter_id is FighterId.fighter_a else FighterId.fighter_a


def swap_fighter_ids(value: T) -> T:
    """Copy of `value` with every FighterId replaced by the other fighter.

    For user inputs that belong to a person (finish winner, point deductions, ...):
    swapping the corners gives that person the other fighter id, so these inputs must
    follow. Walks contracts, lists, tuples and dicts; plain strings are not ids (a note
    that reads "fighter_a" stays as it is)."""
    return cast(T, _swapped(value))


def _swapped(value: Any) -> Any:
    if isinstance(value, FighterId):
        return other_fighter(value)
    if isinstance(value, BaseModel):
        return value.model_copy(update={name: _swapped(getattr(value, name)) for name in type(value).model_fields})
    if isinstance(value, list):
        return [_swapped(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_swapped(v) for v in value)
    if isinstance(value, dict):
        return {_swapped(k): _swapped(v) for k, v in value.items()}
    return value


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
