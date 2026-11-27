"""Bout format, rounds and the broadcast scorebug.

Rounds come from three sources, in this order of priority: the user (always
wins), the scorebug clock read with OCR, and round-break detection when no
clock can be read. Every automatic value carries a confidence; the fight
clock is read from a broadcast graphic, it is not official timing.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import Field, model_validator

from .common import JOB_ID_PATTERN, Contract, VersionedContract
from .judging import RoundMark
from .motion import ExcludedSegment
from .tracking import FighterNames

RoundNumber = Annotated[int, Field(ge=1, le=5)]


class Ruleset(StrEnum):
    abc_2025 = "abc_2025"  # ABC Unified Rules, 2025 judging criteria clarification


class BoutConfig(Contract):
    """Bout format confirmed by the user ("Maç ayarları")."""

    scheduled_rounds: int = Field(default=3, ge=1, le=5, description="3 for most bouts, 5 for title fights.")
    round_length_s: float = Field(default=300, gt=0, le=600)
    rest_s: float = Field(default=60, ge=0, le=600, description="Break between rounds.")
    title_fight: bool = False
    ruleset: Ruleset = Ruleset.abc_2025
    names: FighterNames | None = Field(
        default=None, description="Corner names. Always filled in Job.bout; in a request null keeps them.")


class RoundSource(StrEnum):
    ocr = "ocr"  # scorebug clock read from the broadcast
    break_ = "break"  # between detected round breaks (no readable clock)
    manual = "manual"  # entered or corrected by the user


class RoundSegment(Contract):
    index: int = Field(ge=1, le=5, description="Round number.")
    start_frame: int = Field(ge=0)
    end_frame: int = Field(ge=0, description="Last frame of the round (inclusive).")
    video_start_s: float = Field(ge=0)
    video_end_s: float = Field(ge=0, description="End of the last frame: (end_frame + 1) / fps.")
    clock_start: float | None = Field(
        default=None, ge=0, description="Fight clock (seconds left) when the round starts in the video.")
    clock_end: float | None = Field(
        default=None, ge=0, description="Seconds left at the end: 0 = ran out; more = stopped early or cut off.")
    source: RoundSource
    confidence: float = Field(ge=0, le=1)
    partial: bool = Field(description="Not the full round length in the recording (finish, or cut off).")
    start_extrapolated_s: float | None = Field(
        default=None, ge=0, description=(
            "Clock rounds: the clock was not readable at the start (covered by a graphic, or the scorebug came "
            "late), so the start was extrapolated back from the first clock read this many seconds later; the "
            "confidence is lower. None: the start was read on the clock (or entered, or found otherwise)."))

    @model_validator(mode="after")
    def _ordered(self) -> RoundSegment:
        if self.end_frame < self.start_frame:
            raise ValueError("round must not end before it starts")
        return self


class RoundNoteCode(StrEnum):
    auto_conflicts_manual = "auto_conflicts_manual"  # overlaps a manual round or is out of order with it: not used
    beyond_scheduled = "beyond_scheduled"  # detected round number above the scheduled rounds: not used
    out_of_order = "out_of_order"  # overlaps or precedes the round before it: not used


class RoundNote(Contract):
    code: RoundNoteCode
    round: int = Field(ge=1)
    other: int | None = Field(default=None, description="The other round involved, if any.")


class RoundEdits(Contract):
    """Request body of PUT /jobs/{id}/rounds. A mark replaces the automatic round of
    the same number; cleared numbers are automatic rounds the user removed."""

    rounds: list[RoundMark] = Field(default_factory=list, max_length=5)
    cleared_rounds: list[RoundNumber] = Field(default_factory=list, max_length=5)


class ScreenRect(Contract):
    """Rectangle in the analysis video as shares of its width and height (0..1)."""

    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    w: float = Field(gt=0, le=1)
    h: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def _inside(self) -> ScreenRect:
        if self.x + self.w > 1.0001 or self.y + self.h > 1.0001:
            raise ValueError("rectangle must lie inside the frame")
        return self


class RoiSource(StrEnum):
    auto = "auto"
    manual = "manual"  # drawn by the user on the selection screen


class ScorebugRoi(Contract):
    clock: ScreenRect = Field(description="Area read for the clock (and the round number next to it).")
    source: RoiSource
    confidence: float = Field(ge=0, le=1, description=(
        "Automatic: share of reads there that parsed as a clock in the frames searched; "
        "manual: share of seconds of video it read as a clock."))


class ScorebugRegion(Contract):
    """Request body of PUT /jobs/{id}/scorebug: the user's clock rectangle; null = automatic."""

    clock: ScreenRect | None = None


class NameSuggestion(Contract):
    """Names read from the scorebug. A suggestion only: never applied without the user."""

    left: str | None = Field(description="As read left of the clock, e.g. 'VOLKANOVSKI'.")
    right: str | None
    red: str | None = Field(description="Suggested red corner name (left by broadcast convention), title case.")
    blue: str | None
    confidence: float = Field(ge=0, le=1)


class BroadcastNoteCode(StrEnum):
    ocr_unavailable = "ocr_unavailable"  # model not installed: the clock is not read
    clock_not_found = "clock_not_found"  # no persistent text area reads as a fight clock
    roi_unreadable = "roi_unreadable"  # the user's rectangle does not read as a clock
    no_rounds = "no_rounds"  # clock read, but no run long enough for a round
    round_number_inferred = "round_number_inferred"  # round number unreadable: taken from the order
    rounds_from_breaks = "rounds_from_breaks"  # no clock: rounds between detected breaks


class BroadcastNote(Contract):
    code: BroadcastNoteCode
    round: int | None = None


class BroadcastSummary(Contract):
    cache_key: str
    cache_hit: bool
    version: int = Field(default=1, ge=1, description=(
        "Version of the broadcast analysis that made this (1: rounds only; 2: replays, stoppages, non-fight parts)."))
    method: str
    ocr_available: bool
    ocr_model: str | None = None
    roi: ScorebugRoi | None = None
    clock_share: float = Field(ge=0, le=1, description="Share of seconds with a usable clock read.")
    rounds: list[RoundSegment] = Field(description="Automatic rounds; Job.rounds applies the user's edits.")
    names: NameSuggestion | None = None
    notes: list[BroadcastNote] = Field(default_factory=list)
    segments: list[ExcludedSegment] = Field(default_factory=list, description=(
        "Parts found from the broadcast signals: replays, stoppages, and the stretches before the first / after "
        "the last clock round without a scorebug. Job.auto_exclusions combines them with the rounds in effect."))
    scorebug_frame: int | None = Field(
        default=None, ge=0, description="A frame that shows the scorebug (for drawing the clock rectangle).")
    processing_s: float = Field(ge=0)


class BroadcastTimeline(VersionedContract):
    """The fight clock read from the scorebug, one sample per second of video
    (null: no usable read and no safe interpolation)."""

    job_id: str = Field(pattern=JOB_ID_PATTERN)
    fps: float = Field(gt=0)
    sample_hz: float = Field(gt=0)
    t_s: list[float]
    round: list[int | None]
    remaining_s: list[float | None]
    confidence: list[float]
    roi: ScorebugRoi | None = None
    rounds: list[RoundSegment] = Field(description="Automatic rounds (before the user's edits).")
