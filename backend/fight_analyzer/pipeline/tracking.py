"""Identity tracking (after the user's selection).

Input: tracking preparation + the user's anchors (red/blue on one or more
frames). Output: per-frame identity state of both fighters (tracked /
occluded / uncertain), uncertain stretches, review points and counters such
as identity switches and uncertain time, cached by selection.
"""

from __future__ import annotations

from fight_analyzer.contracts import (
    AppearanceSummary,
    FighterSelection,
    PipelineStage,
    ProgressUnit,
    TrackingSummary,
)
from fight_analyzer.jobs.worker import JobContext, JobFailed
from fight_analyzer.pose.cache import CacheCorrupt, load_arrays, read_manifest
from fight_analyzer.tracking import prep as prep_mod
from fight_analyzer.tracking import quality, results
from fight_analyzer.tracking.identity import IDENTITY_VERSION, AppearanceModel, assign, build_context

from .base import RateMeter, overall

STAGE = PipelineStage.tracking


def method_description(tracker: str) -> str:
    return (f"{tracker}: çekim içi geçici iz parçaları (her kamera kesiminde sıfırlanır) + kalıcı kimlik "
            f"katmanı v{IDENTITY_VERSION}: şort/gövde görünümü (renk ve doku), konum, hız ve boyut; "
            f"kesimden sonra yalnızca görünüm. Görünüm modeli videonun farklı yerlerinden örneklerle iki "
            f"geçişte kurulur; hazırlığın kaçırdığı kamera kesimleri ayrıca bulunur; örtüşmede her kare "
            f"kendi görünümüyle doğrulanır.")


def appearance_summary(model: AppearanceModel | None) -> AppearanceSummary | None:
    if model is None:
        return None
    return AppearanceSummary(red_samples=len(model.refs[0]), blue_samples=len(model.refs[1]),
                             red_shots=len({shot for shot, _ in model.refs[0]}),
                             blue_shots=len({shot for shot, _ in model.refs[1]}),
                             third_samples=len(model.third), height_ratio=model.height_ratio)


def run(ctx: JobContext, selection: FighterSelection) -> None:
    job = ctx.store.get_job(ctx.job.job_id)
    av, pose = job.outputs.analysis_video, job.outputs.pose
    cache_root = ctx.settings.cache_dir
    s, ident = ctx.settings.tracking, ctx.settings.identity
    prep_key, data = ctx.state.get("tracking_prep") or (None, None)
    if data is None:
        prep_key, _ = prep_mod.prep_key(pose.cache_key, s)
        data = prep_mod.read(cache_root, prep_key)
    if data is None or av is None or pose is None:
        raise JobFailed("missing_tracking_prep", "Tracking preparation is missing.", STAGE)

    manifest = read_manifest(cache_root, pose.cache_key)
    try:
        arrays = load_arrays(cache_root, manifest, check_hashes=False) if manifest else None
    except CacheCorrupt as exc:
        raise JobFailed("missing_poses", f"Pose cache unreadable: {exc}", STAGE) from exc
    if arrays is None:
        raise JobFailed("missing_poses", "Pose cache not found.", STAGE)
    for a in selection.anchors:
        if a.frame_index >= arrays.frame_count:
            raise JobFailed("invalid_selection", f"Frame {a.frame_index} does not exist.", STAGE)
        count = int(arrays.det_offsets[a.frame_index + 1] - arrays.det_offsets[a.frame_index])
        if any(d is not None and d >= count for d in a.detection_ids()):
            raise JobFailed("invalid_selection", f"Selected person not found on frame {a.frame_index}.", STAGE)

    meter = RateMeter(STAGE, ProgressUnit.frames, arrays.frame_count, min_units=1)
    ctx.report(overall(STAGE, 0), "Kimlikler eşleniyor", stage=STAGE, detail=meter.detail(0))
    key, _ = results.identity_key(prep_key, selection.anchors, s, ident)
    summary = results.read_summary(cache_root, key)
    if summary is not None and results.read_arrays(cache_root, key) is not None:
        summary = summary.model_copy(update={"cache_hit": True})
    else:
        context = build_context(arrays, data, s, av.video.fps, ident)
        result = assign(context, selection.anchors)
        summary = TrackingSummary(
            cache_key=key, cache_hit=False, method=method_description(data.tracker), version=IDENTITY_VERSION,
            appearance=appearance_summary(result.model), extra_cuts=result.extra_cuts,
            anchors=selection.anchors, shots=results.shots_from(result.shot_id), fighters=result.fighters,
            identity_switches=result.identity_switches, swap_corrections=result.swap_corrections,
            anchor_conflicts=result.anchor_conflicts, uncertain_segments=result.uncertain_segments,
            review_points=result.review_points)
        mask = quality.frame_quality(arrays, data, result.state, result.det, result.reason, av.video.height, ident)
        results.write(cache_root, key, result, summary, mask)
    ctx.store.merge_outputs(ctx.job.job_id, ctx.worker_id, tracking=summary)
    ctx.report(overall(STAGE, 1), "Kimlik takibi tamamlandı",
               detail=meter.detail(arrays.frame_count, note="Önbellekten alındı" if summary.cache_hit else None))
