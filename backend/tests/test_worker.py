from __future__ import annotations

import pytest

from fight_analyzer.config import Settings
from fight_analyzer.contracts import JobStatus, JobType, PipelineStage
from fight_analyzer.jobs.store import JobStore
from fight_analyzer.jobs.worker import (
    JobAwaitingInput,
    JobContext,
    JobFailed,
    Worker,
    default_handlers,
)


def _worker(settings: Settings, store: JobStore, handler) -> Worker:
    return Worker(settings, store, {JobType.analysis: handler}, worker_id="test-worker")


def test_successful_job_reports_progress(settings, store):
    seen = []

    def handler(ctx: JobContext) -> None:
        ctx.report(0.5, "halfway", stage=PipelineStage.pose)
        seen.append(store.get_job(ctx.job.job_id))

    job = store.create_job()
    assert _worker(settings, store, handler).run_once() is True
    assert seen[0].status is JobStatus.running and seen[0].stage is PipelineStage.pose
    assert seen[0].progress == 0.5 and seen[0].message == "halfway"
    assert store.get_job(job.job_id).status is JobStatus.completed


def test_empty_queue_returns_false(settings, store):
    assert _worker(settings, store, lambda ctx: None).run_once() is False


def test_expected_and_unexpected_failures(settings, store):
    def expected(ctx):
        raise JobFailed("bad_video", "cannot decode", PipelineStage.video_prep)

    def crash(ctx):
        raise RuntimeError("boom")

    a = store.create_job()
    _worker(settings, store, expected).run_once()
    assert store.get_job(a.job_id).error.code == "bad_video"

    b = store.create_job()
    _worker(settings, store, crash).run_once()
    failed = store.get_job(b.job_id)
    assert failed.status is JobStatus.failed and failed.error.code == "internal_error"


def test_cancellation_is_honoured_at_next_report(settings, store):
    def handler(ctx):
        store.request_cancel(ctx.job.job_id)
        ctx.report(0.2)
        raise AssertionError("should have been cancelled")

    job = store.create_job()
    _worker(settings, store, handler).run_once()
    assert store.get_job(job.job_id).status is JobStatus.cancelled


def test_interrupt_requeues_running_job(settings, store):
    def handler(ctx):
        raise KeyboardInterrupt

    job = store.create_job()
    with pytest.raises(KeyboardInterrupt):
        _worker(settings, store, handler).run_once()
    assert store.get_job(job.job_id).status is JobStatus.queued


def test_analysis_job_without_source_fails_in_video_prep(settings, store):
    job = store.create_job()
    Worker(settings, store, default_handlers()).run_once()
    failed = store.get_job(job.job_id)
    assert failed.status is JobStatus.failed
    assert failed.error.code == "invalid_job"
    assert failed.error.stage is PipelineStage.video_prep


def test_awaiting_input_pauses_job_and_frees_worker(settings, store):
    def handler(ctx):
        ctx.report(0.7, "poses ready", stage=PipelineStage.pose)
        raise JobAwaitingInput("waiting for selection")

    job = store.create_job()
    worker = _worker(settings, store, handler)
    assert worker.run_once() is True
    paused = store.get_job(job.job_id)
    assert paused.status is JobStatus.awaiting_selection
    assert paused.message == "waiting for selection" and paused.finished_at is None
    assert worker.run_once() is False  # nothing left in the queue
    assert store.request_cancel(job.job_id).status is JobStatus.cancelled
