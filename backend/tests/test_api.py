from __future__ import annotations

from fastapi.testclient import TestClient

from fight_analyzer.contracts import SCHEMA_VERSION, HealthResponse, JobList
from fight_analyzer.jobs.store import JobStore


def test_health_on_clean_start(client: TestClient):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = HealthResponse.model_validate(resp.json())
    assert body.schema_version == SCHEMA_VERSION
    assert body.database.status == "ok"
    assert body.ffmpeg.status == "ok" and body.ffmpeg.version
    assert body.jobs.total == 0
    assert body.pose_model.present is False
    # No worker process in this test.
    assert body.worker.status == "unavailable"
    assert body.status == "degraded"


def test_health_is_ok_with_live_worker(client: TestClient, store: JobStore):
    compute = {"device": "cpu", "device_name": "Test CPU", "requested": "auto",
               "cuda_available": False, "torch_version": "x", "cpu_threads": 4}
    store.register_worker("w1", 1234, {"compute": compute})
    body = client.get("/api/v1/health").json()
    assert body["worker"]["status"] == "ok"
    assert body["worker"]["compute"]["device"] == "cpu"
    assert body["status"] == "ok"


def test_jobs_endpoints(client: TestClient, store: JobStore):
    empty = JobList.model_validate(client.get("/api/v1/jobs").json())
    assert empty.jobs == [] and empty.total == 0

    job = store.create_job()
    listed = client.get("/api/v1/jobs").json()
    assert listed["total"] == 1 and listed["jobs"][0]["job_id"] == job.job_id
    assert client.get(f"/api/v1/jobs/{job.job_id}").json()["status"] == "queued"
    assert client.get(f"/api/v1/jobs/{'f' * 32}").status_code == 404
    assert client.get("/api/v1/jobs/not-an-id").status_code == 422


def test_non_local_host_header_is_rejected(client: TestClient):
    resp = client.get("/api/v1/health", headers={"host": "evil.example"})
    assert resp.status_code == 400
