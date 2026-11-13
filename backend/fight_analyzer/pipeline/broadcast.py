"""Broadcast analysis (before the user's selection, so the selection screen can
show the rounds found and the names read).

Input: analysis video, poses and camera cuts, the user's clock rectangle (if
any). Output: scorebug clock area, fight clock reads, automatic rounds (from
the clock, or from round breaks without one) and name suggestions, cached.
OCR runs offline with the pinned model; without it the clock is not read.
"""

from __future__ import annotations

from fight_analyzer.broadcast import analyze, ocr, ocr_model
from fight_analyzer.broadcast import store as bstore
from fight_analyzer.contracts import BroadcastSummary, PipelineStage, ProgressUnit, ScreenRect
from fight_analyzer.jobs.worker import JobContext, JobFailed
from fight_analyzer.media.analysis_video import video_path
from fight_analyzer.pose.cache import CacheCorrupt, PoseArrays, load_arrays, read_manifest
from fight_analyzer.tracking import prep as prep_mod

from .base import RateMeter, overall

STAGE = PipelineStage.broadcast
METHOD = ("Scorebug: ekranda sabit duran metin kutuları arasından m:ss okunan ve videoyla geri sayan alan "
          "(PaddleOCR PP-OCRv5, yerel); raunt sınırları saatin sıfırlanmasından ve durmasından. Saat yoksa "
          "pozlardan raunt arası tespiti (düşük güven).")


def run(ctx: JobContext) -> None:
    job = ctx.store.get_job(ctx.job.job_id)
    av, pose = (job.outputs.analysis_video, job.outputs.pose) if job else (None, None)
    if av is None or pose is None:
        raise JobFailed("missing_poses", "Poses are not available for the broadcast analysis.", STAGE)
    cache_root = ctx.settings.cache_dir
    prep_key, _ = ctx.state.get("tracking_prep") or prep_mod.prep_key(pose.cache_key, ctx.settings.tracking)
    raw_roi = ctx.params.get("scorebug_roi")
    manual = ScreenRect.model_validate(raw_roi) if raw_roi else None
    installed = ocr_model.installed(ctx.settings.models_dir)
    key, inputs = bstore.key(av.cache_key, pose.cache_key, prep_key, ctx.settings.broadcast, ctx.settings.ruleset,
                             ocr_model.model_id() if installed else None, manual)
    total = av.video.frame_count
    meter = RateMeter(STAGE, ProgressUnit.frames, total, min_units=300)
    ctx.report(overall(STAGE, 0), "Scorebug ve raunt saati", stage=STAGE, detail=meter.detail(0))

    data = bstore.read(cache_root, key)
    hit = data is not None
    if data is None:
        def load_poses() -> PoseArrays:
            manifest = read_manifest(cache_root, pose.cache_key)
            try:
                arrays = load_arrays(cache_root, manifest, check_hashes=False) if manifest else None
            except CacheCorrupt as exc:
                raise JobFailed("missing_poses", f"Pose cache unreadable: {exc}", STAGE) from exc
            if arrays is None:
                raise JobFailed("missing_poses", "Pose cache not found.", STAGE)
            return arrays

        def on_progress(done: int) -> None:
            ctx.report(overall(STAGE, done / total if total else 0), "Scorebug saati okunuyor",
                       detail=meter.detail(done))

        recognizer = ocr.load(ctx.settings.models_dir) if installed else None
        data = analyze.analyze(video_path(cache_root, av.cache_key), av.video, load_poses,
                               recognizer.read if recognizer else None, ctx.settings.broadcast,
                               ctx.settings.ruleset, manual, on_progress)
        bstore.write(cache_root, key, inputs, data)
    summary = BroadcastSummary(
        cache_key=key, cache_hit=hit, method=METHOD, ocr_available=installed,
        ocr_model=ocr_model.model_id() if installed else None, roi=data.roi, clock_share=data.clock_share,
        rounds=data.rounds, names=data.names, notes=data.notes, processing_s=data.processing_s)
    ctx.store.merge_outputs(ctx.job.job_id, ctx.worker_id, broadcast=summary)
    ctx.report(overall(STAGE, 1), "Raunt bilgisi hazır",
               detail=meter.detail(total, note="Önbellekten alındı" if hit else None))
