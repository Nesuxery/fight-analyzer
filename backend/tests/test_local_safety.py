"""Local-use safety: paths stay inside their folders, job/disk limits, no CDN pages,
no hidden downloads and no outbound connections during analysis."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fight_analyzer.api.app import create_app
from fight_analyzer.config import Settings
from fight_analyzer.contracts import JobType
from fight_analyzer.fsutil import inside
from fight_analyzer.jobs.store import JobStore
from fight_analyzer.jobs.worker import Worker, default_handlers
from tests.support.media import make_video

HEADERS = {"X-Fight-Analyzer": "1", "Content-Type": "application/octet-stream"}
PROJECT_MODELS = Path(__file__).resolve().parents[2] / "data" / "models"


@pytest.fixture(scope="module")
def clip(tmp_path_factory) -> bytes:
    return make_video(tmp_path_factory.mktemp("media") / "clip.mp4", seconds=1).read_bytes()


def test_paths_cannot_leave_their_folder(tmp_path: Path):
    root = tmp_path / "jobs"
    root.mkdir()
    assert inside(root, "abc", "x.mp4") == (root / "abc" / "x.mp4").resolve()
    for bad in ("../x", "..\\..\\Windows", "C:\\Windows\\win.ini", "/etc/passwd", "a/../../b"):
        with pytest.raises(ValueError):
            inside(root, bad)


def test_tampered_source_path_is_refused(settings: Settings, store: JobStore, tmp_path: Path):
    outside = tmp_path / "secret.mp4"
    outside.write_bytes(b"x")
    job = store.create_job(params={"source": {"filename": "a.mp4", "size_bytes": 1, "sha256": "0" * 64,
                                              "width": 2, "height": 2, "duration_ms": 1000},
                                   "source_path": "../secret.mp4"})
    Worker(settings, store, default_handlers()).run_once()
    failed = store.get_job(job.job_id)
    assert failed.status == "failed" and failed.error.code == "invalid_job"


def test_upload_limits_jobs_and_disk(tmp_path: Path, clip: bytes):
    s = Settings(data_dir=tmp_path / "a", max_active_jobs=1)
    client = TestClient(create_app(s), base_url="http://127.0.0.1")
    assert client.post("/api/v1/jobs", params={"filename": "a.mp4"}, content=clip, headers=HEADERS).status_code == 201
    second = client.post("/api/v1/jobs", params={"filename": "b.mp4"}, content=clip, headers=HEADERS)
    assert second.status_code == 429 and second.json()["code"] == "too_many_jobs"
    assert "en fazla 1" in second.json()["message"]
    full = Settings(data_dir=tmp_path / "b", min_free_disk_bytes=1 << 60)
    resp = TestClient(create_app(full), base_url="http://127.0.0.1").post(
        "/api/v1/jobs", params={"filename": "a.mp4"}, content=clip, headers=HEADERS)
    assert resp.status_code == 507 and resp.json()["code"] == "insufficient_storage"
    assert not any((full.uploads_dir / ".incoming").glob("*"))  # nothing was stored


def test_no_cdn_docs_page_and_strict_ids(client: TestClient):
    assert client.get("/api/docs").status_code == 404  # Swagger UI would load scripts from a CDN
    assert client.get("/api/openapi.json").status_code == 200
    assert client.get("/api/v1/jobs/..%2F..%2Fdata/video").status_code in (404, 422)
    assert client.get(f"/api/v1/jobs/{'a' * 32}/files/..%2Fjobs.sqlite3").status_code in (404, 422)


def test_missing_model_fails_clearly_without_downloading(settings: Settings, store: JobStore, clip: bytes,
                                                          monkeypatch):
    import urllib.request

    def no_network(*args, **kwargs):
        raise AssertionError("the analysis must not download anything")

    monkeypatch.setattr(urllib.request, "urlopen", no_network)
    s = replace(settings, models_dir_override=settings.data_dir / "no-models")
    client = TestClient(create_app(s), base_url="http://127.0.0.1")
    job_id = client.post("/api/v1/jobs", params={"filename": "a.mp4"}, content=clip, headers=HEADERS).json()["job_id"]
    Worker(s, store, default_handlers()).run_once()
    job = store.get_job(job_id)
    assert job.status == "failed" and job.error.code == "model_missing"
    assert "python -m fight_analyzer.pose.models" in job.error.message


@pytest.mark.skipif(not (PROJECT_MODELS / "yolo26n-pose.pt").is_file(), reason="pose model not downloaded")
def test_pose_inference_makes_no_outbound_connection(tmp_path: Path):
    """Import Ultralytics and run the model in a fresh process where every non-loopback
    connection or name lookup is recorded and refused."""
    script = textwrap.dedent(f"""
        import os, socket, sys
        attempts = []
        real_connect, real_getaddrinfo = socket.socket.connect, socket.getaddrinfo
        def connect(self, addr):
            host = addr[0] if isinstance(addr, tuple) else str(addr)
            if host not in ("127.0.0.1", "::1", "localhost"):
                attempts.append(("connect", host)); raise OSError("blocked")
            return real_connect(self, addr)
        def getaddrinfo(host, *a, **k):
            if host not in ("127.0.0.1", "::1", "localhost", None):
                attempts.append(("dns", host)); raise OSError("blocked")
            return real_getaddrinfo(host, *a, **k)
        socket.socket.connect, socket.getaddrinfo = connect, getaddrinfo
        os.environ["FA_DATA_DIR"] = {str(tmp_path / "data")!r}
        from fight_analyzer.config import apply_runtime_env, load_settings
        s = load_settings(); apply_runtime_env(s); s.ensure_dirs()
        import numpy as np
        from fight_analyzer.contracts import PoseAnalysisSettings
        from fight_analyzer.pose.engine import PoseEngine
        engine = PoseEngine({str(PROJECT_MODELS / "yolo26n-pose.pt")!r}, "cpu",
                            PoseAnalysisSettings(imgsz=320, conf=0.25, iou=0.7, max_det=10))
        engine.infer([np.zeros((240, 320, 3), np.uint8)])
        print("ATTEMPTS", attempts)
    """)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}
    env.pop("YOLO_OFFLINE", None)  # the app must turn offline mode on by itself
    env.pop("YOLO_CONFIG_DIR", None)
    out = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, env=env, timeout=300)
    assert out.returncode == 0, out.stderr[-2000:]
    assert "ATTEMPTS []" in out.stdout, out.stdout[-2000:]
    # control: with offline mode forced off the guard does see Ultralytics' online check
    online = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                            env={**env, "YOLO_OFFLINE": "0"}, timeout=300)
    assert "('dns'" in online.stdout, online.stdout[-2000:]
