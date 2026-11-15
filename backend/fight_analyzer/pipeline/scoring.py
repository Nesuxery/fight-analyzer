"""Experimental momentum (after event detection).

Input: events and movement runs, and the excluded parts in effect (the
user's and the automatic ones not turned off, see nonfight.py). Output: the
momentum ledger (every point with its source) and red/blue shares on the
signal time grid, cached per parameter set and list of excluded parts. The
parameters are starting design values, not validated weights; the result is
not a win probability.

`summarize` is the whole computation from cached events (well under a second),
so the API runs it too when an edit changes the excluded parts.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from fight_analyzer import nonfight
from fight_analyzer.config import MomentumSettings
from fight_analyzer.contracts import ExcludedSegment, Job, PipelineStage, ProgressUnit, ScoringSummary
from fight_analyzer.jobs.worker import JobContext, JobFailed
from fight_analyzer.motion import momentum
from fight_analyzer.motion import store as motion_store

from .base import RateMeter, overall

STAGE = PipelineStage.scoring


def excluded_parts(job: Job) -> list[ExcludedSegment]:
    """The excluded parts in effect for a job (empty until its video is known)."""
    video = job.outputs.analysis_video.video if job.outputs.analysis_video else None
    return nonfight.effective(job.exclusions, job.auto_exclusions, video.frame_count) if video else []


def summarize(cache_root: Path, events_key: str, data: motion_store.EventsData, s: MomentumSettings,
              segments: Sequence[ExcludedSegment], fps: float) -> ScoringSummary:
    """Momentum for these events and excluded parts, from the cache or computed and cached."""
    segments = list(segments)
    key, inputs = motion_store.momentum_key(events_key, s, segments, fps)
    result = motion_store.read_momentum(cache_root, key)
    hit = result is not None
    if result is None:
        result = motion_store.compute_momentum(data, s, segments, fps)
        motion_store.write_momentum(cache_root, key, inputs, result)
    final = float(result.red_share[-1]) if result.red_share.size else 50.0
    return ScoringSummary(cache_key=key, cache_hit=hit, parameters=momentum.parameters(s), exclusions=segments,
                          unattributed_events=len(result.unattributed),
                          contributions=len(result.contributions), final_red_share=round(final, 2))


def run(ctx: JobContext) -> None:
    job = ctx.store.get_job(ctx.job.job_id)
    cache_root = ctx.settings.cache_dir
    ekey, data = ctx.state.get("events") or (None, None)
    if data is None and job.outputs.events is not None:
        ekey = job.outputs.events.cache_key
        data = motion_store.read_events(cache_root, ekey)
    if data is None:
        raise JobFailed("missing_events", "Events are not available for scoring.", STAGE)
    video = job.outputs.analysis_video.video
    meter = RateMeter(STAGE, ProgressUnit.frames, None, min_units=1)
    ctx.report(overall(STAGE, 0), "Deneysel momentum", stage=STAGE, detail=meter.detail(0))
    summary = summarize(cache_root, ekey, data, ctx.settings.momentum, excluded_parts(job), video.fps)
    ctx.store.merge_outputs(ctx.job.job_id, ctx.worker_id, scoring=summary)
    ctx.report(overall(STAGE, 1), "Momentum hazır",
               detail=meter.detail(summary.contributions, note="Önbellekten alındı" if summary.cache_hit else None))
