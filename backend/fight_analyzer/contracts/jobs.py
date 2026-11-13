"""Analysis job contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from .broadcast import BoutConfig, BroadcastSummary, RoundNote, RoundSegment
from .common import JOB_ID_PATTERN, Contract, VersionedContract
from .fighters import Fighter
from .judging import MatchSetup
from .motion import EventsSummary, ExcludedSegment, ScoringSummary
from .sharing import ExportSummary
from .pose import PoseSummary
from .tracking import FighterSelection, TrackingPrepSummary, TrackingSummary
from .video import AnalysisVideo, SourceVideo, VideoInfo


class JobType(StrEnum):
    analysis = "analysis"
    export = "export"  # MP4/CSV/JSON of a finished analysis


class JobStatus(StrEnum):
    queued = "queued"
    running = "running"
    awaiting_selection = "awaiting_selection"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


TERMINAL_STATUSES = frozenset({JobStatus.completed, JobStatus.failed, JobStatus.cancelled})


class PipelineStage(StrEnum):
    """Analysis stages in execution order."""

    video_prep = "video_prep"
    pose = "pose"
    tracking_prep = "tracking_prep"  # cuts, tracklets, appearance, selection candidates
    broadcast = "broadcast"  # scorebug clock (OCR), rounds, round breaks
    tracking = "tracking"  # identity assignment after the user's selection
    events = "events"
    scoring = "scoring"
    export = "export"


class OutdatedReason(StrEnum):
    broadcast_missing = "broadcast_missing"  # analysed before rounds were read from the scorebug


class JobError(Contract):
    code: str = Field(description="Machine-readable error code, e.g. 'stage_not_implemented'.")
    message: str
    stage: PipelineStage | None = None


class ProgressUnit(StrEnum):
    frames = "frames"
    seconds = "seconds"
    bytes = "bytes"


class StageProgress(Contract):
    """Measured progress of the current stage."""

    stage: PipelineStage
    unit: ProgressUnit
    done: float = Field(ge=0, description="Units processed so far (e.g. frames).")
    total: float | None = Field(default=None, ge=0)
    rate_per_s: float | None = Field(default=None, ge=0, description="Measured units per second.")
    eta_s: float | None = Field(
        default=None, ge=0, description="Estimated seconds left; null until enough measurements."
    )
    preview_seq: int | None = Field(default=None, ge=0, description="Latest preview number.")
    note: str | None = None


class JobOutputs(Contract):
    analysis_video: AnalysisVideo | None = None
    pose: PoseSummary | None = None
    tracking_prep: TrackingPrepSummary | None = None
    broadcast: BroadcastSummary | None = None
    tracking: TrackingSummary | None = None
    events: EventsSummary | None = None
    scoring: ScoringSummary | None = None
    export: ExportSummary | None = None


class Job(VersionedContract):
    job_id: str = Field(pattern=JOB_ID_PATTERN)
    job_type: JobType
    status: JobStatus
    stage: PipelineStage | None = Field(default=None, description="Stage currently/last running.")
    progress: float = Field(ge=0, le=1, description="Overall progress, 0..1.")
    progress_detail: StageProgress | None = None
    message: str | None = None
    source: SourceVideo | None = None
    video: VideoInfo | None = Field(default=None, description="Analysis video properties.")
    fighters: list[Fighter] = Field(default_factory=list, description="Names and colours, red first.")
    selection: FighterSelection | None = None
    exclusions: list[ExcludedSegment] = Field(
        default_factory=list, description="Parts excluded from the analysis by the user (e.g. replays).")
    match: MatchSetup | None = Field(default=None, description="Rounds, ending and deductions entered by the user.")
    bout: BoutConfig = Field(default_factory=BoutConfig, description="Bout format and names (defaults until set).")
    rounds: list[RoundSegment] = Field(
        default_factory=list, description="Effective rounds: the user's marks over the automatic ones.")
    round_notes: list[RoundNote] = Field(default_factory=list, description="Automatic rounds left out, and why.")
    outdated: list[OutdatedReason] = Field(
        default_factory=list, description="Parts made by an older version of the analysis ('yeniden işle').")
    outputs: JobOutputs = Field(default_factory=JobOutputs)
    error: JobError | None = None
    attempts: int = Field(ge=0, description="How many times a worker started this job.")
    cancel_requested: bool = False
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class JobList(VersionedContract):
    jobs: list[Job]
    total: int = Field(ge=0, description="Number of jobs in the store (may exceed len(jobs)).")
