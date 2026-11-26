"""Motion signals and event detection (after identity tracking).

Input: analysis video, poses, tracking preparation and the identity result.
Output: camera motion (cached per video), per-fighter signals sampled on a
time grid, events (strike attempts, possible contact, clinch, ground
control, stance changes, possible knockdowns/takedowns) and movement runs,
cached per identity result. Detections are experimental, not ground truth.
"""

from __future__ import annotations

from fight_analyzer.contracts import EventsSummary, FighterEventCounts, PhaseTimes, PipelineStage, ProgressUnit
from fight_analyzer.jobs.worker import JobContext, JobFailed
from fight_analyzer.media.analysis_video import video_path
from fight_analyzer.motion import camera, kinematics
from fight_analyzer.motion import events as events_mod
from fight_analyzer.motion import store as motion_store
from fight_analyzer.pose.cache import CacheCorrupt, load_arrays, read_manifest
from fight_analyzer.tracking import prep as prep_mod
from fight_analyzer.tracking import results

from .base import RateMeter, overall

STAGE = PipelineStage.events
METHOD = ("Kamera hareketi arka plandan (optik akış + RANSAC); eklemler gövde boyuna göre ölçekli, "
          "One-Euro ile yumuşatılmış, hızlar zaman farkından; vuruş denemesi = tek hız tepesi + uzanma + "
          "rakibe yönelim; hedef bölge ve sonuç (isabet/blok/ıska/belirsiz) 2B temas ve rakibin hemen sonraki "
          "tepkisinden tahmin edilir; hasar sinyalleri (knockdown, ağır kafa vuruşu, sarsılma, zorunlu geri "
          "çekilme, submission tehlikesi) tahmindir. Kare bazlı grappling durumu (mesafe, klinç, yerde üstte "
          "kırmızı/mavi, karmaşa) duruş, yakınlık ve gövde yüksekliğinden; takedown, deneme, ters çevirme, "
          "kalkma ve olası submission girişimi bu durumların geçişlerinden tahmin edilir. Her olay kimlik "
          "güveninden bir sahiplik güveni taşır.")


def run(ctx: JobContext) -> None:
    job = ctx.store.get_job(ctx.job.job_id)
    av, pose, tracking = job.outputs.analysis_video, job.outputs.pose, job.outputs.tracking
    if av is None or pose is None or tracking is None:
        raise JobFailed("missing_tracking", "Identity tracking is not available.", STAGE)
    cache_root = ctx.settings.cache_dir
    ms = ctx.settings.motion
    prep_key, prep = ctx.state.get("tracking_prep") or (None, None)
    if prep is None:
        prep_key, _ = prep_mod.prep_key(pose.cache_key, ctx.settings.tracking)
        prep = prep_mod.read(cache_root, prep_key)
    ident = results.read_arrays(cache_root, tracking.cache_key)
    if prep is None or ident is None:
        raise JobFailed("missing_tracking", "Tracking results are not in the cache.", STAGE)

    total = av.video.frame_count
    meter = RateMeter(STAGE, ProgressUnit.frames, total, min_units=30)
    ctx.report(overall(STAGE, 0), "Hareket ve olay analizi", stage=STAGE, detail=meter.detail(0))
    ckey, cinputs = motion_store.camera_key(av.cache_key, prep_key, ms)
    ekey, einputs = motion_store.events_key(tracking.cache_key, ckey, ms)
    data = motion_store.read_events(cache_root, ekey)
    hit = data is not None
    if data is None:
        manifest = read_manifest(cache_root, pose.cache_key)
        try:
            arrays = load_arrays(cache_root, manifest, check_hashes=False) if manifest else None
        except CacheCorrupt as exc:
            raise JobFailed("missing_poses", f"Pose cache unreadable: {exc}", STAGE) from exc
        if arrays is None:
            raise JobFailed("missing_poses", "Pose cache not found.", STAGE)
        track = motion_store.read_camera(cache_root, ckey)
        if track is None:
            path = video_path(cache_root, av.cache_key)
            overlay = camera.overlay_mask(path, prep.shot_id, av.video.fps, ms)

            def on_progress(done: int) -> None:
                ctx.report(overall(STAGE, 0.8 * done / total if total else 0), "Kamera hareketi",
                           detail=meter.detail(done))

            track = camera.estimate(prep_mod.iter_frames(path), arrays, prep.shot_id, ms, overlay, on_progress)
            motion_store.write_camera(cache_root, ckey, cinputs, track)
        ctx.report(overall(STAGE, 0.85), "Eklem hızları ve olaylar", detail=meter.detail(total))
        kin = tuple(kinematics.compute(arrays, ident["state"], ident["det"], prep.track_id, track, f, ms)
                    for f in (0, 1))
        # falls of a fighter whose identity is not verified around them (see events.infer_presence)
        inferred = events_mod.inferred_kinematics(arrays, ident["state"], ident["det"], ident["conf"], prep.track_id,
                                                  track, kin, ms)
        analysis = events_mod.analyze(arrays, track, kin, ms, ident["conf"], inferred=inferred)
        data = motion_store.events_data(analysis, arrays.timestamp_ms, track, ms)
        motion_store.write_events(cache_root, ekey, einputs, data)
    summary = EventsSummary(
        cache_key=ekey, cache_hit=hit, version=motion_store.EVENTS_VERSION, method=METHOD, events=len(data.events),
        damage_signals=len(data.damage), camera_known_share=min(1.0, max(0.0, data.camera_known_share)),
        phases=PhaseTimes(**data.phases) if data.phases else None,
        fighters=[FighterEventCounts(fighter_id=fid, **stats)
                  for fid, stats in zip(events_mod.FIGHTERS, data.stats)])
    ctx.store.merge_outputs(ctx.job.job_id, ctx.worker_id, events=summary)
    ctx.state["events"] = (ekey, data)
    ctx.report(overall(STAGE, 1), "Olaylar hazır",
               detail=meter.detail(total, note="Önbellekten alındı" if hit else None))
