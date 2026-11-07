from __future__ import annotations

import sqlite3
import time

from fight_analyzer.contracts import JobError, JobStatus, PipelineStage
from fight_analyzer.jobs.store import MIGRATIONS, JobStore


def test_initialize_is_idempotent_and_versioned(store: JobStore):
    assert store.initialize() == len(MIGRATIONS)
    with sqlite3.connect(store.db_path) as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_job_lifecycle_and_persistence(store: JobStore):
    job = store.create_job(params={"note": "x"})
    assert job.status is JobStatus.queued and job.attempts == 0

    claimed = store.claim_next("w1")
    assert claimed and claimed.job_id == job.job_id
    assert claimed.status is JobStatus.running and claimed.attempts == 1
    assert store.claim_next("w2") is None  # nothing else queued

    stop = store.report_progress(job.job_id, "w1", stage=PipelineStage.pose, progress=0.4,
                                 message="frame 40/100")
    assert stop is False
    store.finish(job.job_id, "w1", JobStatus.completed)

    # A fresh store instance (e.g. after an app restart) sees the same state.
    reopened = JobStore(store.db_path).get_job(job.job_id)
    assert reopened.status is JobStatus.completed
    assert reopened.progress == 1.0 and reopened.finished_at is not None
    assert JobStore(store.db_path).get_params(job.job_id) == {"note": "x"}


def test_claim_is_fifo(store: JobStore):
    first = store.create_job()
    second = store.create_job()
    assert store.claim_next("w").job_id == first.job_id
    assert store.claim_next("w").job_id == second.job_id


def test_other_worker_cannot_finish_job(store: JobStore):
    job = store.create_job()
    store.claim_next("w1")
    store.finish(job.job_id, "intruder", JobStatus.failed,
                 error=JobError(code="x", message="y"))
    assert store.get_job(job.job_id).status is JobStatus.running


def test_cancel_queued_and_running(store: JobStore):
    queued = store.create_job()
    assert store.request_cancel(queued.job_id).status is JobStatus.cancelled

    running = store.create_job()
    store.claim_next("w1")
    flagged = store.request_cancel(running.job_id)
    assert flagged.status is JobStatus.running and flagged.cancel_requested
    assert store.report_progress(running.job_id, "w1", stage=None, progress=0.1) is True


def test_stale_running_job_is_requeued_then_failed(store: JobStore):
    job = store.create_job()
    store.claim_next("dead-worker")
    time.sleep(0.05)
    assert store.recover_stale(stale_after_s=0.01, max_attempts=2) == 1
    requeued = store.get_job(job.job_id)
    assert requeued.status is JobStatus.queued and requeued.attempts == 1

    store.claim_next("dead-again")
    time.sleep(0.05)
    store.recover_stale(stale_after_s=0.01, max_attempts=2)
    failed = store.get_job(job.job_id)
    assert failed.status is JobStatus.failed
    assert failed.error.code == "worker_lost"


def test_fresh_running_job_is_not_recovered(store: JobStore):
    store.create_job()
    store.claim_next("w1")
    assert store.recover_stale(stale_after_s=60, max_attempts=2) == 0
