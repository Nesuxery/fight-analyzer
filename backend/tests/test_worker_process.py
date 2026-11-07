"""The real worker entry point must report pipeline failures with their own
error codes (regression: running worker.py as __main__ loaded it twice and
turned every JobFailed into internal_error)."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from fight_analyzer.contracts import JobStatus
from fight_analyzer.jobs.store import JobStore

BACKEND = Path(__file__).resolve().parents[1]


def test_worker_entry_point_keeps_stage_error_codes(tmp_path: Path):
    data = tmp_path / "data"
    store = JobStore(data / "jobs.sqlite3")
    store.initialize()
    job_id = store.create_job().job_id
    env = {**os.environ, "FA_DATA_DIR": str(data), "PYTHONPATH": str(BACKEND)}
    worker = subprocess.Popen([sys.executable, "-m", "fight_analyzer.jobs"], cwd=BACKEND, env=env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 90
        job = store.get_job(job_id)
        while job.status is JobStatus.queued or job.status is JobStatus.running:
            assert time.monotonic() < deadline, "worker did not finish the job"
            time.sleep(0.3)
            job = store.get_job(job_id)
    finally:
        worker.terminate()
        worker.wait(timeout=10)
    assert job.status is JobStatus.failed
    assert job.error.code == "invalid_job"  # raised by video_prep: job has no source
    assert job.error.stage == "video_prep"
