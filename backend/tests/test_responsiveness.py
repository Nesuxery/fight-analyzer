"""End-to-end: real API and worker processes. While the worker keeps every CPU
core busy, health and job requests must still be answered quickly."""

from __future__ import annotations

import os
import socket
import statistics
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

from fight_analyzer.jobs.store import JobStore

BACKEND = Path(__file__).resolve().parents[1]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait(predicate, timeout: float, what: str):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if result := predicate():
                return result
        except httpx.HTTPError:
            pass
        time.sleep(0.2)
    pytest.fail(f"timed out waiting for {what}")


@pytest.fixture
def services(tmp_path: Path):
    port = _free_port()
    env = {**os.environ, "FA_DATA_DIR": str(tmp_path / "data"), "PYTHONPATH": str(BACKEND),
           "FA_TEST_BUSY_SECONDS": "5", "PYTHONUNBUFFERED": "1"}
    api = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "fight_analyzer.api.app:create_app", "--factory",
         "--host", "127.0.0.1", "--port", str(port), "--no-access-log"],
        cwd=BACKEND, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    worker = subprocess.Popen(
        [sys.executable, str(BACKEND / "tests" / "support" / "busy_worker.py")],
        cwd=BACKEND, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        yield f"http://127.0.0.1:{port}/api/v1", tmp_path / "data" / "jobs.sqlite3"
    finally:
        for proc in (worker, api):
            proc.terminate()
            proc.wait(timeout=10)


def test_api_stays_responsive_during_long_job(services):
    base, db_path = services
    with httpx.Client(timeout=5) as http:
        _wait(lambda: http.get(f"{base}/health").json()["status"] == "ok", 90,
              "API + worker to be healthy")

        job_id = JobStore(db_path).create_job().job_id
        _wait(lambda: http.get(f"{base}/jobs/{job_id}").json()["status"] == "running", 30,
              "job to start")

        latencies, progress = [], []
        while True:
            t0 = time.perf_counter()
            health = http.get(f"{base}/health")
            job = http.get(f"{base}/jobs/{job_id}").json()
            latencies.append(time.perf_counter() - t0)
            assert health.status_code == 200
            if job["status"] != "running":
                break
            progress.append(job["progress"])
            time.sleep(0.1)

    assert job["status"] == "completed", job
    assert len(progress) >= 5, "job finished before the API could be sampled"
    assert progress == sorted(progress) and progress[-1] > progress[0]
    # Two requests per sample; generous bounds for a loaded laptop.
    assert statistics.median(latencies) < 0.25, latencies
    assert max(latencies) < 1.5, latencies
