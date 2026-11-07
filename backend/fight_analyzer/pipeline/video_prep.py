"""Video preparation.

Input: the uploaded source file. Output: a cached constant-frame-rate H.264
analysis copy (AnalysisVideo, also stored on the job as VideoInfo). The pose
engine and the browser both use this copy.
"""

from __future__ import annotations

from fight_analyzer.contracts import PipelineStage, ProgressUnit, SourceVideo
from fight_analyzer.fsutil import inside
from fight_analyzer.jobs.worker import JobContext, JobFailed
from fight_analyzer.media.analysis_video import prepare
from fight_analyzer.media.probe import ProbeError

from .base import RateMeter, overall

STAGE = PipelineStage.video_prep


def run(ctx: JobContext) -> None:
    params = ctx.params
    try:
        source = SourceVideo.model_validate(params["source"])
        # a stored path can never point outside the uploads folder
        source_path = inside(ctx.settings.data_dir, params["source_path"])
        if ctx.settings.uploads_dir.resolve() not in source_path.parents:
            raise ValueError("source path outside the uploads folder")
    except (KeyError, ValueError) as exc:
        raise JobFailed("invalid_job", f"Job has no usable source video ({exc}).", STAGE) from exc
    if not source_path.is_file():
        raise JobFailed("source_missing", "The uploaded source file no longer exists.", STAGE)

    duration_s = source.duration_ms / 1000 or None
    meter = RateMeter(STAGE, ProgressUnit.seconds, duration_s, min_units=1.0, min_seconds=2.0)
    ctx.report(overall(STAGE, 0), "Video hazırlanıyor", stage=STAGE, detail=meter.detail(0))

    def on_progress(out_time_s: float, _frames: int) -> None:
        done = min(out_time_s, duration_s) if duration_s else out_time_s
        frac = done / duration_s if duration_s else 0.0
        ctx.report(overall(STAGE, frac), "Video dönüştürülüyor", detail=meter.detail(done))

    try:
        analysis = prepare(ctx.settings.cache_dir, source_path, source, ctx.settings.transcode,
                           on_progress)
    except ProbeError as exc:
        raise JobFailed(exc.code, exc.message, STAGE) from exc

    ctx.state["analysis_video"] = analysis
    ctx.store.set_video(ctx.job.job_id, ctx.worker_id, analysis.video.model_dump_json())
    ctx.store.merge_outputs(ctx.job.job_id, ctx.worker_id, analysis_video=analysis)
    note = "Önbellekten alındı" if analysis.cache_hit else None
    ctx.report(overall(STAGE, 1), "Video hazır", detail=meter.detail(duration_s or 0, note=note))
