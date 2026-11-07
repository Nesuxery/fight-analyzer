"""Background worker process.

Runs separately from the API (python -m fight_analyzer.jobs) so that
CPU/GPU-heavy analysis never blocks HTTP requests. It claims queued jobs from
the shared SQLite store one at a time, reports progress and heartbeats, and
recovers jobs left behind by a crashed worker.
"""

from __future__ import annotations

import logging
import os
import signal
import threading
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from fight_analyzer.config import Settings, apply_runtime_env, load_settings
from fight_analyzer.contracts import (
    ComputeInfo,
    Job,
    JobError,
    JobStatus,
    JobType,
    PipelineStage,
    StageProgress,
)
from fight_analyzer.fsutil import inside
from fight_analyzer.jobs.store import JobStore

log = logging.getLogger("fight_analyzer.worker")


class JobCancelled(Exception):
    """Raised inside a handler when the job was cancelled or lost."""


class JobAwaitingInput(Exception):
    """Raised by a handler when the job must wait for the user (e.g. fighter
    selection). The job leaves the worker and keeps its outputs."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class JobFailed(Exception):
    """Raised by a handler for an expected failure with a stable error code."""

    def __init__(self, code: str, message: str, stage: PipelineStage | None = None) -> None:
        super().__init__(message)
        self.error = JobError(code=code, message=message, stage=stage)


@dataclass
class JobContext:
    job: Job
    store: JobStore
    settings: Settings
    worker_id: str
    stage: PipelineStage | None = field(default=None)
    compute: ComputeInfo | None = None
    # Values handed from one stage to the next within a run.
    state: dict = field(default_factory=dict)

    @property
    def device(self) -> str:
        return "cuda:0" if self.compute and self.compute.device == "cuda" else "cpu"

    @property
    def work_dir(self) -> Path:
        path = inside(self.settings.jobs_dir, self.job.job_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def params(self) -> dict:
        return self.store.get_params(self.job.job_id)

    def report(self, progress: float, message: str | None = None,
               stage: PipelineStage | None = None, detail: StageProgress | None = None) -> None:
        """Persist progress; raises JobCancelled if the job should stop."""
        if stage is not None:
            self.stage = stage
        if self.store.report_progress(self.job.job_id, self.worker_id, stage=self.stage,
                                      progress=progress, message=message, detail=detail):
            raise JobCancelled()


Handler = Callable[[JobContext], None]


def default_handlers() -> dict[JobType, Handler]:
    from fight_analyzer.pipeline import run_analysis
    from fight_analyzer.pipeline.export import run_export

    return {JobType.analysis: run_analysis, JobType.export: run_export}


class Worker:
    def __init__(self, settings: Settings, store: JobStore,
                 handlers: Mapping[JobType, Handler], worker_id: str | None = None,
                 compute: ComputeInfo | None = None) -> None:
        self.settings = settings
        self.compute = compute
        self.store = store
        self.handlers = dict(handlers)
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.stop_event = threading.Event()
        self._current_job_id: str | None = None
        self._heartbeat_thread: threading.Thread | None = None

    # ---- lifecycle ----------------------------------------------------

    def start(self, info: dict) -> None:
        self.store.prune_workers(self.settings.worker_stale_after_s)
        self.store.register_worker(self.worker_id, os.getpid(), info)
        recovered = self.store.recover_stale(self.settings.job_stale_after_s,
                                             self.settings.job_max_attempts)
        if recovered:
            log.warning("recovered %d abandoned job(s)", recovered)
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop,
                                                  name="heartbeat", daemon=True)
        self._heartbeat_thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=5)
        self.store.remove_worker(self.worker_id)

    def _heartbeat_loop(self) -> None:
        interval = self.settings.worker_heartbeat_interval_s
        while not self.stop_event.wait(interval):
            try:
                self.store.heartbeat_worker(self.worker_id)
                if job_id := self._current_job_id:
                    self.store.heartbeat_job(job_id, self.worker_id)
            except Exception:  # keep heartbeating through transient DB errors
                log.exception("heartbeat failed")

    def run_forever(self) -> None:
        log.info("%s waiting for jobs", self.worker_id)
        stale_check_every = max(1, int(self.settings.job_stale_after_s
                                       / self.settings.worker_poll_interval_s))
        idle_polls = 0
        while not self.stop_event.is_set():
            if self.run_once():
                continue
            idle_polls += 1
            if idle_polls % stale_check_every == 0:
                self.store.recover_stale(self.settings.job_stale_after_s,
                                         self.settings.job_max_attempts)
            self.stop_event.wait(self.settings.worker_poll_interval_s)

    # ---- job execution ------------------------------------------------

    def run_once(self) -> bool:
        """Claim and run one job. Returns False when the queue was empty."""
        job = self.store.claim_next(self.worker_id)
        if job is None:
            return False
        log.info("job %s started (attempt %d)", job.job_id, job.attempts)
        self._current_job_id = job.job_id
        ctx = JobContext(job=job, store=self.store, settings=self.settings,
                         worker_id=self.worker_id, compute=self.compute)
        try:
            handler = self.handlers.get(job.job_type)
            if handler is None:
                raise JobFailed("unsupported_job_type", f"No handler for job type {job.job_type}")
            handler(ctx)
        except JobAwaitingInput as exc:
            self.store.pause(job.job_id, self.worker_id, exc.message)
            log.info("job %s waiting for user input", job.job_id)
        except JobCancelled:
            self.store.finish(job.job_id, self.worker_id, JobStatus.cancelled,
                              message="Kullanıcı tarafından iptal edildi.")
            log.info("job %s cancelled", job.job_id)
        except JobFailed as exc:
            self.store.finish(job.job_id, self.worker_id, JobStatus.failed, error=exc.error)
            log.warning("job %s failed: %s", job.job_id, exc.error.message)
        except (KeyboardInterrupt, SystemExit):
            # Shutting down mid-job: hand it back so the next start resumes it.
            self.store.requeue(job.job_id, self.worker_id,
                               "İşçi durdurulduğu için yeniden kuyruğa alındı.")
            log.info("job %s requeued (worker stopping)", job.job_id)
            raise
        except Exception as exc:
            log.exception("job %s crashed", job.job_id)
            self.store.finish(job.job_id, self.worker_id, JobStatus.failed,
                              error=JobError(code="internal_error",
                                             message=f"{type(exc).__name__}: {exc}",
                                             stage=ctx.stage))
        else:
            self.store.finish(job.job_id, self.worker_id, JobStatus.completed)
            log.info("job %s completed", job.job_id)
        finally:
            self._current_job_id = None
        return True


def main(handlers: Mapping[JobType, Handler] | None = None) -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        datefmt="%H:%M:%S")
    settings = load_settings()
    apply_runtime_env(settings)
    settings.ensure_dirs()
    store = JobStore(settings.db_path)
    store.initialize()

    from fight_analyzer.system.compute import detect_compute

    compute = detect_compute(settings.device)
    log.info("compute device: %s (%s), torch %s", compute.device, compute.device_name,
             compute.torch_version)
    worker = Worker(settings, store, handlers or default_handlers(), compute=compute)
    # SIGTERM / Ctrl+Break (sent by scripts/launch.py on Windows) take the same
    # path as Ctrl+C, so a running job is requeued instead of lost.
    signal.signal(signal.SIGTERM, signal.default_int_handler)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, signal.default_int_handler)
    worker.start({"compute": compute.model_dump(mode="json")})
    try:
        worker.run_forever()
    except KeyboardInterrupt:
        log.info("stopping")
    finally:
        worker.stop()
