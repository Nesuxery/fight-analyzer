from __future__ import annotations

from functools import lru_cache
from pathlib import Path as FsPath
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request
from fastapi.responses import FileResponse

from fight_analyzer.contracts import (
    TERMINAL_STATUSES,
    DataOrigin,
    EventTimeline,
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
    Scorecards,
    SegmentExclusions,
    SelectionCandidate,
    SelectionCandidates,
    TrackingTimeline,
)
from fight_analyzer.contracts.common import JOB_ID_PATTERN
from fight_analyzer.media.analysis_video import video_path
from fight_analyzer import judging
from fight_analyzer.motion import exclusions as excl
from fight_analyzer.motion import store as motion_store
from fight_analyzer.pipeline import export as export_job
from fight_analyzer.pose.cache import CacheCorrupt, PoseArrays, load_arrays, read_manifest
from fight_analyzer.pose.preview import image_name, read_preview
from fight_analyzer.tracking import prep as prep_mod
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
    cuts = job.outputs.tracking_prep.cuts if job.outputs.tracking_prep else []
    return TrackingTimeline(job_id=job_id, frame_count=int(ident["state"].shape[0]), fps=av.video.fps,
                            cuts=cuts, fighters=identity_results.timeline(ident))


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


@router.put("/{job_id}/match", response_model=Job)
def set_match(store: StoreDep, job_id: JobId, body: MatchSetup) -> Job:
    """Rounds, how the bout ended and point deductions (user input; nothing is recomputed)."""
    job = _job(store, job_id)
    av = job.outputs.analysis_video
    if av is None:
        raise ApiProblem(409, "video_not_ready", "Analiz videosu henüz hazır değil.")
    if any(r.start_frame >= av.video.frame_count for r in body.rounds):
        raise ApiProblem(422, "invalid_match", "Raund başlangıcı videonun dışında.")
    return store.update_params(job_id, {"match": body.model_dump(mode="json")})


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
    return judging.compute(job_id, job.fighters, job.match or MatchSetup(), inputs)


@router.put("/{job_id}/exclusions", response_model=Job, status_code=202)
def set_exclusions(store: StoreDep, job_id: JobId, body: SegmentExclusions) -> Job:
    """Replace the excluded parts (replays, slow motion, breaks). Events are kept but those
    inside are not counted or scored; the momentum is computed again (fast, from cache)."""
    job = _job(store, job_id)
    av = job.outputs.analysis_video
    if job.selection is None or av is None:
        raise ApiProblem(409, "no_selection", "Önce dövüşçüleri seçin.")
    segments = excl.normalize(body.segments, av.video.frame_count)
    updated = store.resubmit(job_id, allowed=("completed", "failed"),
                             params_patch={"exclusions": [x.model_dump(mode="json") for x in segments]},
                             clear_outputs=("scoring",),
                             message="Dışlanan bölümler güncellendi; momentum yeniden hesaplanıyor.")
    if updated is None:
        raise ApiProblem(409, "job_busy", "Analiz şu anda işleniyor; bitince bölümleri değiştirebilirsiniz.")
    return updated


@router.post("/{job_id}/swap", response_model=Job, status_code=202)
def swap_corners(store: StoreDep, job_id: JobId) -> Job:
    """Exchange the red and blue corners (selection and names together); identities, events,
    statistics and momentum are derived again from cached poses."""
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
