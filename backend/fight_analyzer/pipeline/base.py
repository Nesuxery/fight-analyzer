"""Shared helpers for pipeline stages."""

from __future__ import annotations

import time

from fight_analyzer.contracts import PipelineStage, ProgressUnit, StageProgress
from fight_analyzer.jobs.worker import JobFailed

# Share of the overall progress bar per stage (sums to 1). Fighter selection
# happens between pose and tracking and takes no machine time.
STAGE_WEIGHTS: dict[PipelineStage, float] = {
    PipelineStage.video_prep: 0.10,
    PipelineStage.pose: 0.50,
    PipelineStage.tracking_prep: 0.10,
    PipelineStage.broadcast: 0.04,
    PipelineStage.tracking: 0.04,
    PipelineStage.events: 0.09,
    PipelineStage.scoring: 0.08,
    PipelineStage.export: 0.05,
}


def overall(stage: PipelineStage, fraction: float) -> float:
    """Overall job progress when `stage` is `fraction` done."""
    before = 0.0
    for s, w in STAGE_WEIGHTS.items():
        if s == stage:
            return before + w * min(max(fraction, 0.0), 1.0)
        before += w
    return before


def not_implemented(stage: PipelineStage) -> JobFailed:
    return JobFailed("stage_not_implemented",
                     f"The '{stage.value}' stage is not implemented yet.", stage)


class RateMeter:
    """Measured throughput and ETA. The ETA stays null until at least
    `min_units` units and `min_seconds` seconds have been measured."""

    def __init__(self, stage: PipelineStage, unit: ProgressUnit, total: float | None,
                 min_units: float, min_seconds: float = 3.0) -> None:
        self.stage = stage
        self.unit = unit
        self.total = total
        self.min_units = min_units
        self.min_seconds = min_seconds
        self.started = time.monotonic()

    def elapsed(self) -> float:
        return time.monotonic() - self.started

    def detail(self, done: float, *, preview_seq: int | None = None,
               note: str | None = None) -> StageProgress:
        elapsed = self.elapsed()
        rate = done / elapsed if elapsed > 0 and done > 0 else None
        eta = None
        if (rate and self.total is not None and done >= self.min_units
                and elapsed >= self.min_seconds):
            eta = max(0.0, (self.total - done) / rate)
        return StageProgress(stage=self.stage, unit=self.unit, done=done, total=self.total,
                             rate_per_s=rate, eta_s=eta, preview_seq=preview_seq, note=note)
