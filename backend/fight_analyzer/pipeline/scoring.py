"""Experimental momentum (after event detection).

Input: events and movement runs. Output: the momentum ledger (every point
with its source) and red/blue shares on the signal time grid, cached per
parameter set. The parameters are starting design values, not validated
weights; the result is not a win probability.
"""

from __future__ import annotations

from fight_analyzer.contracts import ExcludedSegment, PipelineStage, ProgressUnit, ScoringSummary
from fight_analyzer.jobs.worker import JobContext, JobFailed
from fight_analyzer.motion import exclusions as excl
from fight_analyzer.motion import momentum
from fight_analyzer.motion import store as motion_store

from .base import RateMeter, overall

STAGE = PipelineStage.scoring


def run(ctx: JobContext) -> None:
    job = ctx.store.get_job(ctx.job.job_id)
    cache_root = ctx.settings.cache_dir
    ekey, data = ctx.state.get("events") or (None, None)
    if data is None and job.outputs.events is not None:
        ekey = job.outputs.events.cache_key
        data = motion_store.read_events(cache_root, ekey)
    if data is None:
        raise JobFailed("missing_events", "Events are not available for scoring.", STAGE)
    s = ctx.settings.momentum
    video = job.outputs.analysis_video.video
    segments = excl.normalize((ExcludedSegment.model_validate(x) for x in ctx.params.get("exclusions") or []),
                              video.frame_count)
    meter = RateMeter(STAGE, ProgressUnit.frames, None, min_units=1)
    ctx.report(overall(STAGE, 0), "Deneysel momentum", stage=STAGE, detail=meter.detail(0))
    key, inputs = motion_store.momentum_key(ekey, s, segments, video.fps)
    result = motion_store.read_momentum(cache_root, key)
    hit = result is not None
    if result is None:
        result = motion_store.compute_momentum(data, s, segments, video.fps)
        motion_store.write_momentum(cache_root, key, inputs, result)
    final = float(result.red_share[-1]) if result.red_share.size else 50.0
    summary = ScoringSummary(cache_key=key, cache_hit=hit, parameters=momentum.parameters(s), exclusions=segments,
                             contributions=len(result.contributions), final_red_share=round(final, 2))
    ctx.store.merge_outputs(ctx.job.job_id, ctx.worker_id, scoring=summary)
    ctx.report(overall(STAGE, 1), "Momentum hazır",
               detail=meter.detail(len(result.contributions), note="Önbellekten alındı" if hit else None))
