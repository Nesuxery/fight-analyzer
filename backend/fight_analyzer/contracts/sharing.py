"""Shareable output of an analysis: MP4 with the overlay burned in, per-frame
metrics as CSV and events + settings as JSON.

An export is its own job (job_type "export") so the analysis stays usable while
it renders. It reads exactly the cached analysis data the browser shows (the
cache keys are copied into the export when it is requested).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from .common import JOB_ID_PATTERN, Contract, DataOrigin, VersionedContract
from .events import DamageSignal, FightEvent
from .fighters import Fighter
from .judging import Scorecards
from .motion import ExcludedSegment, FighterEventCounts, MomentumContribution, MomentumParameters
from .tracking import FighterSelection
from .video import VideoInfo


class ExportOptions(Contract):
    """What is drawn on the exported video (CSV and JSON always contain everything)."""

    skeleton: bool = True
    effects: bool = Field(default=True, description="Strike flashes, possible-contact rings, major-event warnings.")
    momentum: bool = Field(default=True, description="Momentum bar with names and shares at the top.")
    counters: bool = Field(default=True, description="Attempt counters under the names.")
    distance: bool = False
    others: bool = Field(default=False, description="Other people (referee, spectators) in grey.")


class ExportRequest(Contract):
    options: ExportOptions = Field(default_factory=ExportOptions)


class ExportFileKind(StrEnum):
    video = "video"  # MP4 with overlay (audio kept when present)
    metrics = "metrics"  # CSV, one row per frame
    bundle = "bundle"  # JSON: events, momentum ledger, settings


class ExportFile(Contract):
    kind: ExportFileKind
    name: str
    bytes: int = Field(ge=0)
    content_type: str


class SourceKeys(Contract):
    """Cache entries the export was made from (the same ones the browser reads)."""

    pose: str
    tracking: str
    events: str
    scoring: str


class ExportSummary(Contract):
    source_job_id: str = Field(pattern=JOB_ID_PATTERN)
    options: ExportOptions
    source_keys: SourceKeys
    frames: int = Field(ge=0)
    has_audio: bool
    events: int = Field(ge=0)
    final_red_share: float = Field(ge=0, le=100, description="Displayed share on the last frame.")
    files: list[ExportFile]


class AnalysisExport(VersionedContract):
    """The JSON file of an export."""

    job_id: str = Field(pattern=JOB_ID_PATTERN, description="The analysis this was exported from.")
    exported_at: datetime
    data_origin: DataOrigin
    video: VideoInfo
    fighters: list[Fighter]
    selection: FighterSelection | None
    source_keys: SourceKeys
    settings: dict[str, Any] = Field(description="Pose, tracking, motion and momentum settings used.")
    events: list[FightEvent]
    damage: list[DamageSignal] = Field(default_factory=list, description="Damage signals (estimates), as on screen.")
    momentum_parameters: MomentumParameters
    momentum_contributions: list[MomentumContribution]
    counts: list[FighterEventCounts] = Field(description="Whole video, before exclusions.")
    exclusions: list[ExcludedSegment] = Field(default_factory=list)
    excluded_event_ids: list[str] = Field(default_factory=list, description="Listed but not counted or scored.")
    csv_columns: dict[str, str] = Field(description="Meaning of each column of the CSV file.")
    scorecards: Scorecards | None = Field(default=None, description="AI round scoring (estimate, not official).")
