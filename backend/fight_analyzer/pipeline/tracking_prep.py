"""Tracking preparation (before the user's selection).

Input: analysis video + pose cache. Output: camera cuts, appearance
descriptors, OC-SORT tracklets and candidate frames for the selection screen
(cached, independent of which fighters get selected).
"""

from __future__ import annotations

from fight_analyzer.contracts import PipelineStage, ProgressUnit, TrackingPrepSummary
from fight_analyzer.jobs.worker import JobContext, JobFailed
from fight_analyzer.media.analysis_video import video_path
from fight_analyzer.pose.cache import CacheCorrupt, load_arrays, read_manifest
from fight_analyzer.tracking import prep as prep_mod

from .base import RateMeter, overall

STAGE = PipelineStage.tracking_prep


def run(ctx: JobContext) -> None:
    job = ctx.store.get_job(ctx.job.job_id)
    av = job.outputs.analysis_video if job else None
    pose = job.outputs.pose if job else None
    if av is None or pose is None:
        raise JobFailed("missing_poses", "Poses are not available for tracking.", STAGE)
    cache_root = ctx.settings.cache_dir
    s = ctx.settings.tracking
    key, inputs = prep_mod.prep_key(pose.cache_key, s)
    total = av.video.frame_count
    meter = RateMeter(STAGE, ProgressUnit.frames, total, min_units=30)
    ctx.report(overall(STAGE, 0), "Takip hazırlığı", stage=STAGE, detail=meter.detail(0))

    data = prep_mod.read(cache_root, key)
    hit = data is not None
    if data is None:
        manifest = read_manifest(cache_root, pose.cache_key)
        try:
            arrays = load_arrays(cache_root, manifest, check_hashes=True) if manifest else None
        except CacheCorrupt as exc:
            raise JobFailed("missing_poses", f"Pose cache unreadable: {exc}", STAGE) from exc
        if arrays is None:
            raise JobFailed("missing_poses", "Pose cache not found.", STAGE)

        def on_progress(done: int) -> None:
            ctx.report(overall(STAGE, done / total if total else 0),
                       "Kesimler, görünüm ve iz parçaları", detail=meter.detail(done))

        data = prep_mod.compute(prep_mod.iter_frames(video_path(cache_root, av.cache_key)), arrays,
                                av.video.fps, av.video.height, s, on_progress)
        prep_mod.write(cache_root, key, inputs, data)
    summary = TrackingPrepSummary(
        cache_key=key, cache_hit=hit, shots=len(data.cuts) + 1, cuts=data.cuts,
        tracklets=int(len(set(data.track_id.tolist()) - {-1})), candidates=len(data.candidates),
        tracker=data.tracker)
    ctx.store.merge_outputs(ctx.job.job_id, ctx.worker_id, tracking_prep=summary)
    ctx.state["tracking_prep"] = (key, data)
    ctx.report(overall(STAGE, 1), "Aday kareler hazır",
               detail=meter.detail(total, note="Önbellekten alındı" if hit else None))
