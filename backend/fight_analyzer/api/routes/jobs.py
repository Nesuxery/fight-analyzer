from __future__ import annotations

from functools import lru_cache
from pathlib import Path as FsPath
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request
from fastapi.responses import FileResponse

from fight_analyzer.contracts import (
    TERMINAL_STATUSES,
    AutoExclusionEdits,
    BoutConfig,
    BroadcastTimeline,
    DataOrigin,
    EventTimeline,
    ExclusionSource,
    ExportFileKind,
    ExportRequest,
    FighterNames,
    FighterSelection,
    Job,
    JobList,
    JobStatus,
    JobType,
    MatchSetup,
    MomentumTimeline,
    MotionTimeline,
    PoseChunk,
    PosePreview,
    QualityScope,
    RoundEdits,
    Scorecards,
    ScorebugRegion,
    SegmentExclusions,
    SelectionCandidate,
    SelectionCandidates,
    TrackingTimeline,
    TrackQualityReport,
)
from fight_analyzer.contracts.common import JOB_ID_PATTERN
from fight_analyzer.media.analysis_video import video_path
from fight_analyzer.media.thumbnail import ensure_thumbnail, thumbnail_frame
from fight_analyzer import judging, nonfight
from fight_analyzer import rounds as rounds_mod
from fight_analyzer.broadcast import clock as clock_mod
from fight_analyzer.broadcast import store as broadcast_store
from fight_analyzer.motion import exclusions as excl
from fight_analyzer.motion import store as motion_store
from fight_analyzer.pipeline import export as export_job
from fight_analyzer.pipeline import scoring as scoring_stage
from fight_analyzer.pose.cache import CacheCorrupt, PoseArrays, load_arrays, read_manifest
from fight_analyzer.pose.preview import image_name, read_preview
from fight_analyzer.tracking import prep as prep_mod
from fight_analyzer.tracking import quality as quality_mod
from fight_analyzer.tracking import results as identity_results

from ..deps import SettingsDep, StoreDep
from ..errors import ApiProblem
from ..uploads import receive_upload

router = APIRouter(prefix="/jobs", tags=["jobs"])

JobId = Annotated[str, Path(pattern=JOB_ID_PATTERN)]
MAX_CHUNK = 600


def _job(store, job_id: str, job_type: JobType | None = JobType.analysis) -> Job:
    """The job, which must be of `job_type` (None = any type)."""
    job = store.get_job(job_id)
    if job is None or (job_type is not None and job.job_type != job_type):
        raise ApiProblem(404, "job_not_found", "Analiz bulunamadı." if job_type == JobType.analysis
                         else "Dışa aktarma bulunamadı.")
    return job


@router.get("", response_model=JobList)
def list_jobs(store: StoreDep,
              limit: Annotated[int, Query(ge=1, le=500)] = 100) -> JobList:
    """Analyses, newest first (exports are listed per analysis, see /{job_id}/exports)."""
    total = sum(store.count_by_status(JobType.analysis).values())
    return JobList(jobs=store.list_jobs(limit, JobType.analysis), total=total)


@router.post("", response_model=Job, status_code=201)
async def upload_video(request: Request, store: StoreDep, settings: SettingsDep,
                       filename: Annotated[str, Query(min_length=1, max_length=255)]) -> Job:
    """Upload a video as the raw request body (Content-Type
    application/octet-stream) and queue its analysis."""
    counts = store.count_by_status(JobType.analysis)
    active = sum(counts.get(s, 0) for s in ("queued", "running", "awaiting_selection"))
    if active >= settings.max_active_jobs:
        raise ApiProblem(429, "too_many_jobs",
                         f"Aynı anda en fazla {settings.max_active_jobs} bekleyen ya da çalışan analiz olabilir. "
                         "Önce bazılarını tamamlayın veya iptal edin.")
    source, stored = await receive_upload(request, filename, settings)
    return store.create_job(params={"source": source.model_dump(mode="json"),
                                    "source_path": stored.as_posix()})


@router.get("/{job_id}", response_model=Job)
def get_job(store: StoreDep, job_id: JobId) -> Job:
    """An analysis or an export job."""
    return _job(store, job_id, None)


@router.post("/{job_id}/cancel", response_model=Job)
def cancel_job(store: StoreDep, job_id: JobId) -> Job:
    job = _job(store, job_id, None)
    if job.status in TERMINAL_STATUSES:
        raise ApiProblem(409, "job_finished", "Bu analiz zaten sona ermiş.")
    return store.request_cancel(job_id)  # type: ignore[return-value]


@router.get("/{job_id}/video", response_class=FileResponse)
def analysis_video(store: StoreDep, settings: SettingsDep, job_id: JobId) -> FileResponse:
    """The analysis copy (supports HTTP Range for seeking)."""
    job = _job(store, job_id)
    av = job.outputs.analysis_video
    if av is None:
        raise ApiProblem(409, "video_not_ready", "Analiz videosu henüz hazır değil.")
    path = video_path(settings.cache_dir, av.cache_key)
    if not path.is_file():
        raise ApiProblem(410, "video_missing", "Analiz videosu önbellekte bulunamadı.")
    return FileResponse(path, media_type="video/mp4")


@router.get("/{job_id}/thumbnail.jpg", response_class=FileResponse)
def job_thumbnail(store: StoreDep, settings: SettingsDep, job_id: JobId) -> FileResponse:
    """Small preview frame of the analysis copy for the history list."""
    job = _job(store, job_id)
    av = job.outputs.analysis_video
    video = video_path(settings.cache_dir, av.cache_key) if av else None
    if av is None or video is None or not video.is_file():
        raise ApiProblem(404, "thumbnail_unavailable", "Bu analiz için önizleme görüntüsü yok.")
    anchors = job.selection.anchors if job.selection else []
    frame = thumbnail_frame(av.video.frame_count, anchors[0].frame_index if anchors else None)
    path = ensure_thumbnail(settings.jobs_dir / job_id, video, av.cache_key, frame)
    if path is None:
        raise ApiProblem(404, "thumbnail_unavailable", "Önizleme karesi okunamadı.")
    # revalidated each time: a new selection changes the frame
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "no-cache"})


@router.get("/{job_id}/preview", response_model=PosePreview)
def pose_preview(store: StoreDep, settings: SettingsDep, job_id: JobId) -> PosePreview:
    _job(store, job_id)
    preview = read_preview(settings.jobs_dir / job_id)
    if preview is None:
        raise ApiProblem(404, "preview_not_ready", "Önizleme henüz yok.")
    return preview


@router.get("/{job_id}/preview.jpg", response_class=FileResponse)
def pose_preview_image(store: StoreDep, settings: SettingsDep, job_id: JobId,
                       seq: Annotated[int, Query(ge=1)]) -> FileResponse:
    _job(store, job_id)
    path = settings.jobs_dir / job_id / image_name(seq)
    if not path.is_file():
        raise ApiProblem(404, "preview_not_ready", "Önizleme görüntüsü yok.")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@lru_cache(maxsize=4)
def _arrays(cache_root: FsPath, key: str) -> PoseArrays:
    manifest = read_manifest(cache_root, key)
    if manifest is None:
        raise CacheCorrupt("manifest missing")
    # Hashes were verified when the worker wrote/reused the entry.
    return load_arrays(cache_root, manifest, check_hashes=False, mmap=True)


@router.get("/{job_id}/poses", response_model=PoseChunk)
def pose_chunk(store: StoreDep, settings: SettingsDep, job_id: JobId,
               start: Annotated[int, Query(ge=0)] = 0,
               count: Annotated[int, Query(ge=1, le=MAX_CHUNK)] = 150) -> PoseChunk:
    """Detections and keypoints of every person for frames [start, start+count)."""
    job = _job(store, job_id)
    pose, av = job.outputs.pose, job.outputs.analysis_video
    if pose is None or av is None or job.status in (JobStatus.queued, JobStatus.running):
        raise ApiProblem(409, "poses_not_ready", "Poz verisi henüz hazır değil.")
    try:
        arrays = _arrays(settings.cache_dir, pose.cache_key)
    except CacheCorrupt as exc:
        raise ApiProblem(410, "poses_missing", f"Poz önbelleği okunamadı: {exc}") from exc
    end = min(arrays.frame_count, start + count)
    video = av.video.model_copy(update={"frame_count": arrays.frame_count})
    prep = _prep(settings.cache_dir, job.outputs.tracking_prep.cache_key) if job.outputs.tracking_prep else None
    ident = (identity_results.read_arrays(settings.cache_dir, job.outputs.tracking.cache_key)
             if job.outputs.tracking and job.status not in (JobStatus.queued, JobStatus.running) else None)
    frames = [identity_results.annotated_frame(arrays, i, ident, prep.track_id if prep else None)
              for i in range(start, end)]
    return PoseChunk(job_id=job_id, data_origin="measured", video=video, start_frame=start, frames=frames)


@lru_cache(maxsize=4)
def _prep(cache_root: FsPath, key: str) -> prep_mod.PrepData | None:
    return prep_mod.read(cache_root, key, check_hashes=False)


def _pose_arrays(settings, job: Job) -> PoseArrays:
    if job.outputs.pose is None:
        raise ApiProblem(409, "poses_not_ready", "Poz verisi henüz hazır değil.")
    try:
        return _arrays(settings.cache_dir, job.outputs.pose.cache_key)
    except CacheCorrupt as exc:
        raise ApiProblem(410, "poses_missing", f"Poz önbelleği okunamadı: {exc}") from exc


@router.get("/{job_id}/candidates", response_model=SelectionCandidates)
def selection_candidates(store: StoreDep, settings: SettingsDep, job_id: JobId) -> SelectionCandidates:
    """Frames where both fighters are clearly visible, for the selection screen."""
    job = _job(store, job_id)
    av, tp = job.outputs.analysis_video, job.outputs.tracking_prep
    if av is None or tp is None:
        raise ApiProblem(409, "candidates_not_ready", "Aday kareler henüz hazırlanmadı.")
    prep = _prep(settings.cache_dir, tp.cache_key)
    if prep is None:
        raise ApiProblem(410, "candidates_missing", "Takip hazırlığı önbellekte bulunamadı.")
    arrays = _pose_arrays(settings, job)
    frames = [SelectionCandidate(frame_index=f, timestamp_ms=float(arrays.timestamp_ms[f]),
                                 shot_index=int(prep.shot_id[f]), score=min(1.0, max(0.0, sc)),
                                 detections=arrays.frame(f).detections)
              for f, sc in zip(prep.candidates, prep.candidate_scores)]
    return SelectionCandidates(job_id=job_id, video=av.video, frames=frames)


@router.post("/{job_id}/selection", response_model=Job, status_code=202)
def submit_selection(store: StoreDep, settings: SettingsDep, job_id: JobId, body: FighterSelection) -> Job:
    """Red and blue fighters on one or more frames; (re)runs identity tracking."""
    job = _job(store, job_id)
    if job.outputs.tracking_prep is None:
        raise ApiProblem(409, "selection_not_ready", "Seçim için poz ve takip hazırlığı tamamlanmalı.")
    arrays = _pose_arrays(settings, job)
    for a in body.anchors:
        if a.frame_index >= arrays.frame_count:
            raise ApiProblem(422, "invalid_selection", f"{a.frame_index}. kare videoda yok.")
        count = int(arrays.det_offsets[a.frame_index + 1] - arrays.det_offsets[a.frame_index])
        if any(d is not None and d >= count for d in a.detection_ids()):
            raise ApiProblem(422, "invalid_selection", f"{a.frame_index}. karede seçilen kişi bulunamadı.")
    updated = store.resubmit(job_id, allowed=("awaiting_selection", "completed", "failed"),
                             params_patch={"selection": body.model_dump(mode="json")},
                             clear_outputs=("tracking", "events", "scoring"),
                             message="Seçim alındı; kimlikler eşleniyor.")
    if updated is None:
        raise ApiProblem(409, "job_busy", "Analiz şu anda işleniyor; bitince yeniden seçebilirsiniz.")
    return updated


@router.put("/{job_id}/names", response_model=Job)
def set_names(store: StoreDep, job_id: JobId, body: FighterNames) -> Job:
    _job(store, job_id)
    return store.update_params(job_id, {"names": {"red": body.red.strip(), "blue": body.blue.strip()}})


@router.post("/{job_id}/retry", response_model=Job, status_code=202)
def retry_job(store: StoreDep, job_id: JobId) -> Job:
    """Run a failed/cancelled job again, or prepare selection data for older analyses."""
    job = _job(store, job_id)
    allowed = ("failed", "cancelled") + (("awaiting_selection",) if job.outputs.tracking_prep is None else ())
    updated = store.resubmit(job_id, allowed=allowed, message="Yeniden kuyruğa alındı.")
    if updated is None:
        raise ApiProblem(409, "job_not_retryable", "Bu analiz yeniden başlatılamaz.")
    return updated


@router.get("/{job_id}/tracking/timeline", response_model=TrackingTimeline)
def tracking_timeline(store: StoreDep, settings: SettingsDep, job_id: JobId) -> TrackingTimeline:
    job = _job(store, job_id)
    tr, av = job.outputs.tracking, job.outputs.analysis_video
    if tr is None or av is None:
        raise ApiProblem(409, "tracking_not_ready", "Kimlik takibi henüz yok.")
    ident = identity_results.read_arrays(settings.cache_dir, tr.cache_key)
    if ident is None:
        raise ApiProblem(410, "tracking_missing", "Takip sonucu önbellekte bulunamadı.")
    # the identity layer's shots include the cuts the preparation missed
    cuts = ([s.start_frame for s in tr.shots[1:]] if tr.shots
            else job.outputs.tracking_prep.cuts if job.outputs.tracking_prep else [])
    return TrackingTimeline(job_id=job_id, frame_count=int(ident["state"].shape[0]), fps=av.video.fps,
                            cuts=cuts, fighters=identity_results.timeline(ident))


@router.get("/{job_id}/tracking/quality", response_model=TrackQualityReport)
def tracking_quality(store: StoreDep, settings: SettingsDep, job_id: JobId) -> TrackQualityReport:
    """Data quality of both fighters for the whole bout and every round in effect (excluded
    parts are not fight time). The browser computes the same for the scope that follows the
    playhead from the tracking timeline."""
    job = _job(store, job_id)
    tr, av = job.outputs.tracking, job.outputs.analysis_video
    if tr is None or av is None:
        raise ApiProblem(409, "tracking_not_ready", "Kimlik takibi henüz yok.")
    ident = identity_results.read_arrays(settings.cache_dir, tr.cache_key)
    if ident is None:
        raise ApiProblem(410, "tracking_missing", "Takip sonucu önbellekte bulunamadı.")
    if "quality" not in ident or "change" not in ident:
        raise ApiProblem(409, "quality_outdated", "Bu analiz eski sürümle yapıldı; veri kalitesi için yeniden işleyin.")
    frames = int(ident["state"].shape[0])
    segments = job.outputs.scoring.exclusions if job.outputs.scoring else scoring_stage.excluded_parts(job)
    excluded = quality_mod.excluded_mask(segments, frames)
    spans = [(None, 0, frames - 1), *((r.index, r.start_frame, min(r.end_frame, frames - 1)) for r in job.rounds)]
    return TrackQualityReport(job_id=job_id, fps=av.video.fps, scopes=[
        QualityScope(round=index, start_frame=a, end_frame=b,
                     fighters=quality_mod.summarize(ident["state"], ident["quality"], ident["change"], a, b,
                                                    av.video.fps, excluded))
        for index, a, b in spans])


@lru_cache(maxsize=4)
def _events(cache_root: FsPath, key: str) -> motion_store.EventsData | None:
    return motion_store.read_events(cache_root, key)


def _events_of(settings, job: Job) -> motion_store.EventsData:
    ev = job.outputs.events
    if ev is None or job.outputs.analysis_video is None:
        raise ApiProblem(409, "events_not_ready", "Hareket ve olay analizi henüz yok.")
    data = _events(settings.cache_dir, ev.cache_key)
    if data is None:
        raise ApiProblem(410, "events_missing", "Olay sonuçları önbellekte bulunamadı.")
    return data


@router.get("/{job_id}/events", response_model=EventTimeline)
def event_timeline(store: StoreDep, settings: SettingsDep, job_id: JobId) -> EventTimeline:
    """Detected events (attempts, possible contact, possible knockdowns...)."""
    job = _job(store, job_id)
    data = _events_of(settings, job)
    return EventTimeline(job_id=job_id, data_origin=DataOrigin.measured, video=job.outputs.analysis_video.video,
                         fighters=job.fighters, events=data.events)


@router.get("/{job_id}/motion", response_model=MotionTimeline)
def motion_timeline(store: StoreDep, settings: SettingsDep, job_id: JobId) -> MotionTimeline:
    """Per-fighter motion signals on a fixed time grid (null = no valid measurement)."""
    job = _job(store, job_id)
    return motion_store.motion_timeline(job_id, _events_of(settings, job), settings.motion)


@router.get("/{job_id}/momentum", response_model=MomentumTimeline)
def momentum_timeline(store: StoreDep, settings: SettingsDep, job_id: JobId) -> MomentumTimeline:
    """Experimental momentum: ledger of points with their sources and the shares over time."""
    job = _job(store, job_id)
    sc = job.outputs.scoring
    if sc is None:
        raise ApiProblem(409, "momentum_not_ready", "Momentum henüz hesaplanmadı.")
    m = motion_store.read_momentum(settings.cache_dir, sc.cache_key)
    if m is None:
        raise ApiProblem(410, "momentum_missing", "Momentum sonucu önbellekte bulunamadı.")
    return motion_store.momentum_timeline(job_id, sc.parameters, m, settings.motion.sample_hz, sc.exclusions)


def _refresh_momentum(store, settings, job_id: str) -> Job:
    """After an edit that can change the excluded parts in effect (rounds, bout format, the
    ending, automatic parts turned off or on): when the list changed, the momentum is
    computed again right here, from the cached events and well under a second, so the
    statistics, cards, momentum and exports keep using one list and the result screen
    stays open. A job that is being processed gets the list from its scoring stage."""
    job = store.get_job(job_id)
    o = job.outputs
    if job.status != JobStatus.completed or o.scoring is None or o.events is None or o.analysis_video is None:
        return job
    segments = scoring_stage.excluded_parts(job)
    if segments == list(o.scoring.exclusions):
        return job
    data = _events(settings.cache_dir, o.events.cache_key)
    if data is None:  # events left the cache: the worker makes them again, then the momentum
        return store.resubmit(job_id, allowed=("completed",), clear_outputs=("scoring",),
                              message="Dışlanan bölümler değişti; momentum yeniden hesaplanıyor.") or job
    summary = scoring_stage.summarize(settings.cache_dir, o.events.cache_key, data, settings.momentum, segments,
                                      o.analysis_video.video.fps)
    return store.replace_scoring(job_id, summary) or store.get_job(job_id)


def _with_bout(job: Job, setup: dict) -> MatchSetup:
    """The setup with round count and length from the bout format (their source since 1.7.0)."""
    try:
        return MatchSetup.model_validate({**setup, "scheduled_rounds": job.bout.scheduled_rounds,
                                          "round_length_s": job.bout.round_length_s})
    except ValueError as exc:
        raise ApiProblem(422, "invalid_match", f"Maç bilgileri geçersiz: {exc}") from exc


@router.put("/{job_id}/match", response_model=Job)
def set_match(store: StoreDep, settings: SettingsDep, job_id: JobId, body: MatchSetup) -> Job:
    """Rounds, how the bout ended and point deductions (user input). Round count and length
    come from the bout format (PUT /bout). Rounds and an early ending decide what lies
    outside the fight: if the excluded parts change, the momentum is computed again."""
    job = _job(store, job_id)
    av = job.outputs.analysis_video
    if av is None:
        raise ApiProblem(409, "video_not_ready", "Analiz videosu henüz hazır değil.")
    if any(r.start_frame >= av.video.frame_count for r in body.rounds):
        raise ApiProblem(422, "invalid_match", "Raunt başlangıcı videonun dışında.")
    setup = _with_bout(job, body.model_dump(mode="json"))
    store.update_params(job_id, {"match": setup.model_dump(mode="json")})
    return _refresh_momentum(store, settings, job_id)


@router.put("/{job_id}/rounds", response_model=Job)
def set_rounds(store: StoreDep, settings: SettingsDep, job_id: JobId, body: RoundEdits) -> Job:
    """The user's round marks (each replaces the automatic round of its number) and the
    automatic rounds they removed; the ending and deductions are kept. Time outside the
    rounds is excluded automatically, so the momentum is computed again when that changes."""
    job = _job(store, job_id)
    av = job.outputs.analysis_video
    if av is None:
        raise ApiProblem(409, "video_not_ready", "Analiz videosu henüz hazır değil.")
    if any(r.end_frame >= av.video.frame_count for r in body.rounds):
        raise ApiProblem(422, "invalid_match", "Raunt videonun dışında.")
    current = job.match.model_dump(mode="json") if job.match else {}
    setup = _with_bout(job, {**current, "rounds": [r.model_dump(mode="json") for r in body.rounds],
                             "cleared_rounds": sorted(set(body.cleared_rounds))})
    store.update_params(job_id, {"match": setup.model_dump(mode="json")})
    return _refresh_momentum(store, settings, job_id)


@router.put("/{job_id}/bout", response_model=Job)
def set_bout(store: StoreDep, settings: SettingsDep, job_id: JobId, body: BoutConfig) -> Job:
    """Bout format ("Maç ayarları"), and the names when given. The round count decides which
    automatic rounds are used: if the excluded parts change, the momentum is computed again."""
    job = _job(store, job_id)
    if body.scheduled_rounds not in settings.ruleset.round_options:
        options = " / ".join(str(n) for n in settings.ruleset.round_options)
        raise ApiProblem(422, "invalid_bout", f"Raunt sayısı {options} olabilir.")
    if job.match is not None:
        n = body.scheduled_rounds
        used = ([r.number for r in job.match.rounds] + [d.round for d in job.match.deductions]
                + ([job.match.ending.round] if job.match.ending.round else []))
        if any(x > n for x in used):
            raise ApiProblem(409, "bout_conflict",
                             f"{n}. rauntun sonrasına girilmiş raunt, kesinti ya da bitiş var; önce onları kaldır.")
    patch: dict = {"bout": body.model_dump(mode="json", exclude={"names"})}
    if body.names is not None:
        patch["names"] = {"red": body.names.red.strip(), "blue": body.names.blue.strip()}
    if job.match is not None:
        patch["match"] = {**job.match.model_dump(mode="json"), "scheduled_rounds": body.scheduled_rounds,
                          "round_length_s": body.round_length_s}
    store.update_params(job_id, patch)
    return _refresh_momentum(store, settings, job_id)


@router.put("/{job_id}/scorebug", response_model=Job, status_code=202)
def set_scorebug(store: StoreDep, job_id: JobId, body: ScorebugRegion) -> Job:
    """The user's clock rectangle (null: find it automatically); the clock is read again."""
    job = _job(store, job_id)
    if job.outputs.tracking_prep is None:
        raise ApiProblem(409, "video_not_ready", "Önce poz ve takip hazırlığı tamamlanmalı.")
    roi = body.clock.model_dump(mode="json") if body.clock else None
    updated = store.resubmit(job_id, allowed=("awaiting_selection", "completed", "failed"),
                             params_patch={"scorebug_roi": roi}, clear_outputs=("broadcast",),
                             message="Scorebug alanı güncellendi; saat yeniden okunuyor.")
    if updated is None:
        raise ApiProblem(409, "job_busy", "Analiz şu anda işleniyor; bitince yeniden dene.")
    return updated


@router.post("/{job_id}/reprocess", response_model=Job, status_code=202)
def reprocess(store: StoreDep, job_id: JobId) -> Job:
    """Run the parts an older version did not make (poses and preparation come from the cache)."""
    job = _job(store, job_id)
    if job.outputs.tracking_prep is None:
        raise ApiProblem(409, "video_not_ready", "Önce poz ve takip hazırlığı tamamlanmalı.")
    clear = ("broadcast", "tracking", "events", "scoring") if job.selection else ("broadcast",)
    updated = store.resubmit(job_id, allowed=("awaiting_selection", "completed", "failed"), clear_outputs=clear,
                             message="Analiz yeni sürümle yeniden işleniyor (pozlar önbellekten).")
    if updated is None:
        raise ApiProblem(409, "job_busy", "Analiz şu anda işleniyor; bitince yeniden dene.")
    return updated


@router.get("/{job_id}/broadcast", response_model=BroadcastTimeline)
def broadcast_timeline(store: StoreDep, settings: SettingsDep, job_id: JobId) -> BroadcastTimeline:
    """The fight clock read from the scorebug (one sample per second) and the automatic rounds."""
    job = _job(store, job_id)
    b, av = job.outputs.broadcast, job.outputs.analysis_video
    if b is None or av is None:
        raise ApiProblem(409, "broadcast_not_ready", "Raunt bilgisi henüz hazır değil.")
    data = broadcast_store.read(settings.cache_dir, b.cache_key)
    if data is None:
        raise ApiProblem(410, "broadcast_missing", "Raunt bilgisi önbellekte bulunamadı.")
    duration = av.video.frame_count / av.video.fps
    found, _ = clock_mod.infer(data.reads, duration, settings.broadcast, settings.ruleset)
    hz = settings.broadcast.ocr_hz
    ts, rnd, rem, conf = clock_mod.timeline(found, duration, hz, settings.broadcast.max_interpolate_s)
    return BroadcastTimeline(job_id=job_id, fps=av.video.fps, sample_hz=hz, t_s=ts, round=rnd, remaining_s=rem,
                             confidence=conf, roi=data.roi, rounds=data.rounds)


@router.get("/{job_id}/scorecards", response_model=Scorecards)
def scorecards(store: StoreDep, settings: SettingsDep, job_id: JobId) -> Scorecards:
    """AI round scoring by three virtual judges and the decision estimate (not an official result)."""
    job = _job(store, job_id)
    data = _events_of(settings, job)
    av, tr = job.outputs.analysis_video, job.outputs.tracking
    ident = identity_results.read_arrays(settings.cache_dir, tr.cache_key) if tr else None
    # the same excluded parts as the statistics and the momentum on screen
    exclusions = job.outputs.scoring.exclusions if job.outputs.scoring else job.exclusions
    names = {f.fighter_id: f.display_name for f in job.fighters}
    inputs = judging.AnalysisInputs(
        events=data.events, runs=data.runs, signals=data.signals, sample_hz=settings.motion.sample_hz,
        ident_state=ident["state"] if ident is not None else None, fps=av.video.fps,
        frame_count=av.video.frame_count, exclusions=list(exclusions), names=names)
    setup = rounds_mod.judging_setup(job.match, job.bout, job.rounds)
    return judging.compute(job_id, job.fighters, setup, inputs)


@router.put("/{job_id}/exclusions", response_model=Job)
def set_exclusions(store: StoreDep, settings: SettingsDep, job_id: JobId, body: SegmentExclusions) -> Job:
    """Replace the user's excluded parts (replays, slow motion, breaks). Events are kept but
    those inside are not counted or scored; the momentum is computed again in this request,
    like for the automatic parts (which are not touched: PUT /exclusions/auto)."""
    job = _job(store, job_id)
    av = job.outputs.analysis_video
    if job.selection is None or av is None:
        raise ApiProblem(409, "no_selection", "Önce dövüşçüleri seçin.")
    if job.status in (JobStatus.queued, JobStatus.running):
        raise ApiProblem(409, "job_busy", "Analiz şu anda işleniyor; bitince bölümleri değiştirebilirsiniz.")
    mine = [x.model_copy(update={"source": ExclusionSource.manual, "auto_id": None, "confidence": None,
                                 "signals": []}) for x in body.segments]
    segments = excl.normalize(mine, av.video.frame_count)
    store.update_params(job_id, {"exclusions": [x.model_dump(mode="json") for x in segments]})
    return _refresh_momentum(store, settings, job_id)


@router.put("/{job_id}/exclusions/auto", response_model=Job)
def set_auto_exclusions(store: StoreDep, settings: SettingsDep, job_id: JobId, body: AutoExclusionEdits) -> Job:
    """The automatic excluded parts the user turned off ("Geri al"), by id: the complete
    list, the others apply ("Yeniden dışla"). Stored as frame ranges, so a part stays off
    when a round edit moves it a little. The momentum is computed again at once."""
    job = _job(store, job_id)
    known = {a.auto_id for a in job.auto_exclusions}
    if any(i not in known for i in body.dismissed):
        raise ApiProblem(409, "auto_exclusions_changed",
                         "Otomatik bölümler bu arada değişti; listeyi yenileyip yeniden dene.")
    stored = store.get_params(job_id).get("dismissed_auto") or []
    store.update_params(job_id, {"dismissed_auto": nonfight.dismissed_ranges(job.auto_exclusions, body.dismissed,
                                                                             stored)})
    return _refresh_momentum(store, settings, job_id)


@router.post("/{job_id}/swap", response_model=Job, status_code=202)
def swap_corners(store: StoreDep, job_id: JobId) -> Job:
    """Exchange the red and blue corners (selection and names together; the finish winner and
    point deductions stay with their fighter); identities, events, statistics and momentum
    are derived again from cached poses."""
    job = _job(store, job_id)
    if job.selection is None:
        raise ApiProblem(409, "no_selection", "Önce dövüşçüleri seçin.")
    updated = store.swap_corners(job_id, allowed=("completed", "failed"),
                                 clear_outputs=("tracking", "events", "scoring"),
                                 message="Taraflar değiştiriliyor; sonuçlar yeniden hesaplanıyor.")
    if updated is None:
        raise ApiProblem(409, "job_busy", "Analiz şu anda işleniyor; bitince taraflar değiştirilebilir.")
    return updated


@router.post("/{job_id}/exports", response_model=Job, status_code=202)
def create_export(store: StoreDep, job_id: JobId, body: ExportRequest) -> Job:
    """Queue an export (MP4 with overlay, per-frame CSV, JSON) of the results shown now.
    It runs in the worker as its own job; the analysis stays usable meanwhile."""
    job = _job(store, job_id)
    o = job.outputs
    if (job.status != JobStatus.completed or o.analysis_video is None or o.pose is None or o.tracking is None
            or o.events is None or o.scoring is None):
        raise ApiProblem(409, "export_not_ready",
                         "Dışa aktarmak için kimlik takibi, olay analizi ve momentum tamamlanmış olmalı.")
    if any(e.status in (JobStatus.queued, JobStatus.running) for e in store.list_exports(job_id)):
        raise ApiProblem(409, "export_running", "Bu analiz için bir dışa aktarma zaten sürüyor; bitmesini bekleyin.")
    return store.create_job(JobType.export, export_job.snapshot_params(job, body.options))


@router.get("/{job_id}/exports", response_model=JobList)
def list_exports(store: StoreDep, job_id: JobId) -> JobList:
    """Exports of one analysis, newest first."""
    _job(store, job_id)
    jobs = store.list_exports(job_id)
    return JobList(jobs=jobs, total=len(jobs))


@router.get("/{job_id}/files/{kind}", response_class=FileResponse)
def export_file(store: StoreDep, settings: SettingsDep, job_id: JobId, kind: ExportFileKind) -> FileResponse:
    """Download one file of a finished export."""
    job = _job(store, job_id, JobType.export)
    summary = job.outputs.export
    entry = next((f for f in summary.files if f.kind == kind), None) if summary else None
    path = export_job.stored_file(settings.jobs_dir / job_id, kind)
    if job.status != JobStatus.completed or entry is None:
        raise ApiProblem(409, "export_not_ready", "Dışa aktarma henüz tamamlanmadı.")
    if not path.is_file():
        raise ApiProblem(410, "export_missing", "Dışa aktarılan dosya bulunamadı.")
    return FileResponse(path, media_type=entry.content_type, filename=entry.name)
