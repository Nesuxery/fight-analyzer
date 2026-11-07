"""Pose extraction.

Input: the analysis copy from video_prep. Output: per-frame person boxes and
COCO-17 keypoints with confidences for everybody in frame (nobody is
labelled as a fighter yet), stored in the reusable pose cache.
"""

from __future__ import annotations

import logging
import shutil
import time

import cv2
import numpy as np

from fight_analyzer.contracts import (
    KEYPOINT_COUNT,
    AnalysisVideo,
    ModelInfo,
    PipelineStage,
    PoseAnalysisSettings,
    PoseSummary,
    ProgressUnit,
)
from fight_analyzer.jobs.worker import JobContext, JobFailed
from fight_analyzer.media.analysis_video import video_path
from fight_analyzer.pose import models
from fight_analyzer.pose.cache import (
    CacheCorrupt,
    PoseArrays,
    entry_dir,
    frame_record,
    load_arrays,
    pose_cache_key,
    read_manifest,
    write_entry,
)
from fight_analyzer.pose.preview import write_preview

from .base import RateMeter, overall

STAGE = PipelineStage.pose
log = logging.getLogger("fight_analyzer.pose")


def analysis_settings(ctx: JobContext) -> PoseAnalysisSettings:
    p = ctx.settings.pose
    return PoseAnalysisSettings(imgsz=p.imgsz, conf=p.conf, iou=p.iou, max_det=p.max_det,
                                frame_step=1)


def _analysis_video(ctx: JobContext) -> AnalysisVideo:
    av = ctx.state.get("analysis_video")
    if av is None:
        job = ctx.store.get_job(ctx.job.job_id)
        av = job.outputs.analysis_video if job else None
    if av is None:
        raise JobFailed("missing_video", "Analysis video is not prepared.", STAGE)
    return av


def _weights(ctx: JobContext) -> tuple[models.PoseWeights, object]:
    name = ctx.settings.pose_model
    try:
        weights = models.weights_for(name)
    except models.ModelError as exc:
        raise JobFailed("model_unavailable", str(exc), STAGE) from exc
    # No download during an analysis (no hidden network use): setup / the models command
    # fetches the pinned file once; here it is only verified against its SHA-256.
    path = ctx.settings.models_dir / name
    if not models.verify(path, weights):
        raise JobFailed("model_missing",
                        f"Poz modeli {name} bulunamadı ya da bozuk. İndirmek için setup.cmd çalıştırın veya "
                        f"backend klasöründe: python -m fight_analyzer.pose.models {name}", STAGE)
    return weights, path


def run(ctx: JobContext) -> None:
    av = _analysis_video(ctx)
    video = av.video
    ctx.report(overall(STAGE, 0), "Poz modeli hazırlanıyor", stage=STAGE)
    weights, weights_path = _weights(ctx)

    from fight_analyzer.pose.engine import framework_version, get_engine

    model = ModelInfo(name=weights.name, framework_version=framework_version(),
                      device=ctx.device, weights_sha256=weights.sha256, source_url=weights.url)
    settings = analysis_settings(ctx)
    key, key_inputs = pose_cache_key(av.sha256, model, settings)
    cache_root = ctx.settings.cache_dir

    if manifest := read_manifest(cache_root, key):
        try:
            load_arrays(cache_root, manifest, check_hashes=True)
        except CacheCorrupt as exc:
            log.warning("discarding corrupt pose cache %s: %s", key, exc)
            shutil.rmtree(entry_dir(cache_root, key), ignore_errors=True)
        else:
            summary = PoseSummary(cache_key=key, cache_hit=True, frame_count=manifest.frame_count,
                                  detection_count=manifest.detection_count,
                                  max_persons=manifest.max_persons, model=manifest.model,
                                  settings=manifest.settings, processing_s=manifest.processing_s)
            ctx.store.merge_outputs(ctx.job.job_id, ctx.worker_id, pose=summary)
            meter = RateMeter(STAGE, ProgressUnit.frames, manifest.frame_count, min_units=1)
            ctx.report(overall(STAGE, 1), "Pozlar önbellekten alındı",
                       detail=meter.detail(manifest.frame_count, note="Önbellekten alındı"))
            return

    try:
        engine = get_engine(weights_path, ctx.device, settings)  # type: ignore[arg-type]
    except Exception as exc:
        raise JobFailed("model_unavailable", f"Pose model failed to load: {exc}", STAGE) from exc

    cap = cv2.VideoCapture(str(video_path(cache_root, av.cache_key)))
    if not cap.isOpened():
        raise JobFailed("decode_failed", "Analysis video could not be opened.", STAGE)
    total = video.frame_count
    batch_size = max(1, ctx.settings.pose.batch)
    meter = RateMeter(STAGE, ProgressUnit.frames, total, min_units=max(10, 2 * batch_size))
    boxes, confs, kpts, counts = [], [], [], []
    done = 0
    seq = 0
    last_preview = -1e9
    ctx.report(overall(STAGE, 0), "Poz tespiti başladı", detail=meter.detail(0))
    try:
        while True:
            frames = []
            while len(frames) < batch_size:
                ok, frame = cap.read()
                if not ok:
                    break
                frames.append(frame)
            if not frames:
                break
            try:
                results = engine.infer(frames)
            except Exception as exc:
                raise JobFailed("pose_failed", f"Pose inference failed: {exc}", STAGE) from exc
            for r in results:
                boxes.append(r.boxes)
                confs.append(r.conf)
                kpts.append(r.keypoints)
                counts.append(len(r.conf))
            done += len(frames)
            now = time.monotonic()
            if now - last_preview >= ctx.settings.pose.preview_interval_s:
                last_preview = now
                seq += 1
                last = results[-1]
                index = done - 1
                record = frame_record(index, index * 1000.0 / video.fps, last.boxes, last.conf,
                                      last.keypoints)
                write_preview(ctx.settings.jobs_dir / ctx.job.job_id, ctx.job.job_id, seq,
                              frames[-1], record, video)
            ctx.report(overall(STAGE, done / total if total else 0),
                       f"Poz tespiti: {done}/{total} kare",
                       detail=meter.detail(done, preview_seq=seq or None))
    finally:
        cap.release()
    if done == 0:
        raise JobFailed("decode_failed", "No frames could be decoded from the analysis video.",
                        STAGE)
    if done != total:
        log.warning("decoded %d frames, container reported %d", done, total)
        video = video.model_copy(update={"frame_count": done,
                                         "duration_ms": done * 1000.0 / video.fps})

    frame_index = np.arange(done, dtype=np.int32)
    num, den = video.fps_num or video.fps, video.fps_den or 1
    arrays = PoseArrays(
        frame_index=frame_index,
        timestamp_ms=frame_index.astype(np.float64) * 1000.0 * den / num,
        det_offsets=np.concatenate([[0], np.cumsum(counts)]).astype(np.int64),
        boxes=np.concatenate(boxes).astype(np.float32) if boxes else np.zeros((0, 4), np.float32),
        box_conf=np.concatenate(confs).astype(np.float32) if confs else np.zeros((0,), np.float32),
        keypoints=(np.concatenate(kpts).astype(np.float32) if kpts
                   else np.zeros((0, KEYPOINT_COUNT, 3), np.float32)),
    )
    elapsed = meter.elapsed()
    manifest = write_entry(cache_root, key, key_inputs, video=video, video_sha256=av.sha256,
                           model=model, settings=settings, arrays=arrays, processing_s=elapsed)
    summary = PoseSummary(cache_key=key, cache_hit=False, frame_count=manifest.frame_count,
                          detection_count=manifest.detection_count,
                          max_persons=manifest.max_persons, model=model, settings=settings,
                          processing_s=round(elapsed, 2))
    ctx.store.merge_outputs(ctx.job.job_id, ctx.worker_id, pose=summary)
    ctx.report(overall(STAGE, 1), "Poz tespiti tamamlandı",
               detail=meter.detail(done, preview_seq=seq or None))
