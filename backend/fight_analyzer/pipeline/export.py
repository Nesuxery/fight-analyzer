"""Export job: MP4 with the overlay burned in, per-frame metrics CSV, JSON bundle.

An export is a job of its own (job_type "export") so it runs in the worker
while the result screen stays usable. When it is requested, the cache keys and
summaries the browser is showing are copied into the export's parameters; the
export then reads exactly those cache entries, through the same functions the
API serves the browser with, so the MP4/CSV numbers are the browser's numbers.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from pydantic import Field

from fight_analyzer.contracts import (
    AnalysisExport,
    AnalysisVideo,
    DataOrigin,
    EventsSummary,
    ExportFile,
    ExportFileKind,
    ExportOptions,
    ExportSummary,
    Fighter,
    FighterSelection,
    Job,
    PipelineStage,
    ProgressUnit,
    ScoringSummary,
    SourceKeys,
)
from fight_analyzer import judging
from fight_analyzer import rounds as rounds_mod
from fight_analyzer.contracts import MatchSetup
from fight_analyzer.contracts.common import Contract, utcnow
from fight_analyzer.export import files, frames, render, video
from fight_analyzer.export.style import STYLE_PATH, load_style
from fight_analyzer.jobs.store import CORNER_COLORS, DEFAULT_NAMES
from fight_analyzer.jobs.worker import JobContext, JobFailed
from fight_analyzer.media.analysis_video import video_path
from fight_analyzer.motion import damage as damage_mod
from fight_analyzer.motion import exclusions as excl
from fight_analyzer.motion import store as motion_store
from fight_analyzer.pose.cache import CacheCorrupt, load_arrays, read_manifest
from fight_analyzer.tracking import results as identity_results

from .base import RateMeter

STAGE = PipelineStage.export
REPORT_EVERY_S = 0.5
# kind -> (file in the export job's folder, content type, download name suffix)
OUTPUT = {
    ExportFileKind.video: ("overlay.mp4", "video/mp4", "analiz.mp4"),
    ExportFileKind.metrics: ("metrics.csv", "text/csv; charset=utf-8", "kareler.csv"),
    ExportFileKind.bundle: ("analysis.json", "application/json", "analiz.json"),
}


class ExportSnapshot(Contract):
    """What the browser shows when the export is requested (kept in the job's parameters)."""

    source_job_id: str
    analysis_video: AnalysisVideo
    pose_key: str
    tracking_key: str
    events: EventsSummary
    scoring: ScoringSummary
    names: dict[str, str] = Field(description="Display names: red, blue.")


def snapshot_params(job: Job, options: ExportOptions) -> dict:
    """Parameters of a new export job for a finished analysis."""
    o = job.outputs
    names = {"red": job.fighters[0].display_name, "blue": job.fighters[1].display_name} if job.fighters \
        else dict(DEFAULT_NAMES)
    snap = ExportSnapshot(source_job_id=job.job_id, analysis_video=o.analysis_video, pose_key=o.pose.cache_key,
                          tracking_key=o.tracking.cache_key, events=o.events, scoring=o.scoring, names=names)
    return {"source_job_id": job.job_id, "options": options.model_dump(mode="json"), "names": names,
            "selection": job.selection.model_dump(mode="json") if job.selection else None,
            "source": job.source.model_dump(mode="json") if job.source else None,
            # the setup the judges use on screen: bout format and effective rounds (manual over automatic)
            "match": rounds_mod.judging_setup(job.match, job.bout, job.rounds).model_dump(mode="json"),
            "snapshot": snap.model_dump(mode="json")}


def stored_file(job_dir: Path, kind: ExportFileKind) -> Path:
    return job_dir / OUTPUT[kind][0]


def download_name(names: dict[str, str], kind: ExportFileKind) -> str:
    def slug(text: str) -> str:
        text = text.translate(str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")).lower()
        cleaned = "".join(ch if ch.isascii() and ch.isalnum() else "-" for ch in text)
        return "-".join(part for part in cleaned.split("-") if part) or "dovuscu"
    return f"{slug(names['red'])}-{slug(names['blue'])}-{OUTPUT[kind][2]}"


def run_export(ctx: JobContext) -> None:
    params = ctx.params
    try:
        snap = ExportSnapshot.model_validate(params["snapshot"])
        options = ExportOptions.model_validate(params.get("options") or {})
    except (KeyError, ValueError) as exc:
        raise JobFailed("invalid_export", f"Dışa aktarma parametreleri okunamadı: {exc}", STAGE) from exc
    cache = ctx.settings.cache_dir
    av = snap.analysis_video
    vid = av.video
    meter = RateMeter(STAGE, ProgressUnit.frames, vid.frame_count, min_units=30)
    ctx.report(0.0, "Analiz verisi okunuyor", stage=STAGE, detail=meter.detail(0))
    ctx.store.set_video(ctx.job.job_id, ctx.worker_id, vid.model_dump_json())

    data = motion_store.read_events(cache, snap.events.cache_key)
    mom = motion_store.read_momentum(cache, snap.scoring.cache_key)
    ident = identity_results.read_arrays(cache, snap.tracking_key)
    manifest = read_manifest(cache, snap.pose_key)
    src = video_path(cache, av.cache_key)
    if data is None or mom is None or ident is None or manifest is None or not src.is_file():
        raise JobFailed("export_source_missing", "Analiz sonuçları önbellekte bulunamadı; analizi yeniden çalıştırın.", STAGE)
    try:
        poses = load_arrays(cache, manifest, check_hashes=False, mmap=True)
    except CacheCorrupt as exc:
        raise JobFailed("export_source_missing", f"Poz önbelleği okunamadı: {exc}", STAGE) from exc

    # The same contract objects the API serves to the result screen.
    job_id = snap.source_job_id
    motion = motion_store.motion_timeline(job_id, data, ctx.settings.motion)
    momentum = motion_store.momentum_timeline(job_id, snap.scoring.parameters, mom, ctx.settings.motion.sample_hz,
                                              snap.scoring.exclusions)
    events = data.events
    # the same damage signals as the result screen: output drops for the rounds the judges use
    match = MatchSetup.model_validate(params.get("match") or {})
    damage = damage_mod.with_output_drop(events, data.damage, data.signals, ctx.settings.motion.sample_hz,
                                         [(r.number, r.start_frame, r.end_frame) for r in match.rounds],
                                         momentum.exclusions, vid.fps, ctx.settings.features)
    frame_count = min(vid.frame_count, poses.frame_count)
    metrics = frames.compute(frame_count, vid.fps, events, motion, momentum)
    excluded_ids = excl.excluded_event_ids(events, momentum.exclusions)
    names = snap.names
    keys = SourceKeys(pose=snap.pose_key, tracking=snap.tracking_key, events=snap.events.cache_key,
                      scoring=snap.scoring.cache_key)

    out_dir = ctx.work_dir
    tmp = {kind: out_dir / f".{name}.partial" for kind, (name, _, _) in OUTPUT.items()}
    try:
        files.write_csv(tmp[ExportFileKind.metrics], metrics, motion, events, ident["state"])
        tracking = identity_results.read_summary(cache, snap.tracking_key)
        selection = params.get("selection")
        bundle = AnalysisExport(
            job_id=job_id, exported_at=utcnow(), data_origin=DataOrigin.measured, video=vid,
            fighters=[Fighter(fighter_id=fid, display_name=names[side], color=CORNER_COLORS[side])
                      for fid, side in (("fighter_a", "red"), ("fighter_b", "blue"))],
            selection=FighterSelection.model_validate(selection) if selection else None, source_keys=keys,
            settings={
                "pose": {"model": manifest.model.model_dump(mode="json"),
                         "settings": manifest.settings.model_dump(mode="json")},
                "tracking": {"method": tracking.method if tracking else None},
                "motion": (motion_store.key_inputs(cache, "events", keys.events) or {}).get("settings"),
                "momentum": (motion_store.key_inputs(cache, "momentum", keys.scoring) or {}).get("settings"),
                "overlay_style": json.loads(STYLE_PATH.read_text(encoding="utf-8")),
                "export_options": options.model_dump(mode="json"),
            },
            events=events, damage=damage, momentum_parameters=snap.scoring.parameters,
            momentum_contributions=mom.contributions,
            counts=snap.events.fighters, exclusions=momentum.exclusions,
            excluded_event_ids=sorted(excluded_ids), csv_columns=files.CSV_COLUMNS)
        fighters = bundle.fighters
        inputs = judging.AnalysisInputs(
            events=events, runs=data.runs, signals=data.signals, sample_hz=ctx.settings.motion.sample_hz,
            ident_state=ident["state"], fps=vid.fps, frame_count=frame_count, exclusions=list(momentum.exclusions),
            names={f.fighter_id: f.display_name for f in fighters})
        bundle.scorecards = judging.compute(job_id, fighters, match, inputs)
        files.write_bundle(tmp[ExportFileKind.bundle], bundle)

        style = load_style()
        renderer = render.Renderer(vid.width, vid.height, names, options, style)
        last_report = [time.monotonic()]

        def draw(i: int, img) -> None:
            if i >= frame_count:
                return
            j = int(metrics.motion_sample[i])
            renderer.draw(img, i, identity_results.annotated_frame(poses, i, ident), metrics,
                          frames.effects_at(events, float(metrics.t_ms[i]) / 1000, style, excluded_ids),
                          motion.distance[j] if j >= 0 else None)

        def progress(done: int) -> None:
            now = time.monotonic()
            if now - last_report[0] >= REPORT_EVERY_S:
                last_report[0] = now
                ctx.report(min(0.99, done / max(1, vid.frame_count)),
                           f"Video yazılıyor: {done}/{vid.frame_count} kare", detail=meter.detail(done))

        try:
            written = video.render(src, tmp[ExportFileKind.video], vid, ctx.settings.transcode, draw, progress)
        except video.ExportError as exc:
            raise JobFailed(exc.code, str(exc), STAGE) from exc
    except BaseException:
        for path in tmp.values():
            path.unlink(missing_ok=True)
        raise

    out: list[ExportFile] = []
    for kind, (name, content_type, _) in OUTPUT.items():
        final = out_dir / name
        tmp[kind].replace(final)
        out.append(ExportFile(kind=kind, name=download_name(names, kind), bytes=final.stat().st_size,
                              content_type=content_type))
    summary = ExportSummary(source_job_id=job_id, options=options, source_keys=keys, frames=written,
                            has_audio=vid.has_audio, events=len(events),
                            final_red_share=float(metrics.red_shown[frame_count - 1]) if frame_count else 50.0,
                            files=out)
    ctx.store.merge_outputs(ctx.job.job_id, ctx.worker_id, export=summary)
    ctx.report(1.0, "Dışa aktarma hazır", detail=meter.detail(written))
