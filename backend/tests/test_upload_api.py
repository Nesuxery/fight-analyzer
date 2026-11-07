from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fight_analyzer.api.app import create_app
from fight_analyzer.config import Settings, UploadLimitSettings
from tests.support.media import make_video

HEADERS = {"X-Fight-Analyzer": "1", "Content-Type": "application/octet-stream"}


@pytest.fixture(scope="module")
def clip(tmp_path_factory) -> bytes:
    path = make_video(tmp_path_factory.mktemp("media") / "clip.mp4", seconds=2, audio=True)
    return path.read_bytes()


def _client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings), base_url="http://127.0.0.1")


def _upload(client: TestClient, data: bytes, name: str = "maç kaydı.mp4", headers=HEADERS):
    return client.post("/api/v1/jobs", params={"filename": name}, content=data, headers=headers)


def test_valid_upload_creates_queued_job(client: TestClient, settings: Settings, clip: bytes):
    resp = _upload(client, clip)
    assert resp.status_code == 201, resp.text
    job = resp.json()
    src = job["source"]
    assert job["status"] == "queued"
    assert src["filename"] == "maç kaydı.mp4" and (src["width"], src["height"]) == (320, 180)
    assert src["has_audio"] and abs(src["duration_ms"] - 2000) < 100
    stored = settings.uploads_dir / src["sha256"] / "source.mp4"
    assert stored.read_bytes() == clip
    # Same content again: stored once, new job.
    again = _upload(client, clip).json()
    assert again["job_id"] != job["job_id"] and again["source"]["sha256"] == src["sha256"]
    assert len(list(settings.uploads_dir.glob("*/source.mp4"))) == 1
    assert not any((settings.uploads_dir / ".incoming").iterdir())


@pytest.mark.parametrize("data, name, status, code", [
    (b"\x00" * 4096, "fake.mp4", 400, None),
    (b"hello", "notes.txt", 415, "unsupported_extension"),
    (b"", "empty.mp4", 400, "empty_file"),
])
def test_invalid_uploads_are_rejected(client: TestClient, settings, data, name, status, code):
    resp = _upload(client, data, name)
    assert resp.status_code == status, resp.text
    body = resp.json()
    assert body["message"]
    if code:
        assert body["code"] == code
    else:
        assert body["code"] in ("invalid_video", "no_video_stream", "undecodable_video")
    assert client.get("/api/v1/jobs").json()["total"] == 0
    incoming = settings.uploads_dir / ".incoming"
    assert not incoming.exists() or not any(incoming.iterdir())


def test_size_and_duration_limits(tmp_path: Path, clip: bytes):
    small = Settings(data_dir=tmp_path / "a", upload=UploadLimitSettings(max_bytes=1000))
    resp = _upload(_client(small), clip)
    assert resp.status_code == 413 and resp.json()["code"] == "file_too_large"

    short = Settings(data_dir=tmp_path / "b", upload=UploadLimitSettings(max_duration_s=1))
    resp = _upload(_client(short), clip)
    assert resp.status_code == 422 and resp.json()["code"] == "too_long"

    lowres = Settings(data_dir=tmp_path / "c",
                      upload=dataclasses.replace(UploadLimitSettings(), min_short_side=360))
    resp = _upload(_client(lowres), clip)
    assert resp.status_code == 422 and resp.json()["code"] == "resolution_too_low"


def test_state_changing_requests_need_local_client(client: TestClient, clip: bytes):
    resp = _upload(client, clip, headers={"Content-Type": "application/octet-stream"})
    assert resp.status_code == 403 and resp.json()["code"] == "missing_client_header"
    resp = _upload(client, clip, headers={**HEADERS, "Origin": "https://evil.example"})
    assert resp.status_code == 403 and resp.json()["code"] == "forbidden_origin"
    ok = _upload(client, clip, headers={**HEADERS, "Origin": "http://127.0.0.1:5173"})
    assert ok.status_code == 201


def test_cancel_and_not_ready_endpoints(client: TestClient, clip: bytes):
    job_id = _upload(client, clip).json()["job_id"]
    for path, code in [("video", 409), ("poses", 409), ("preview", 404)]:
        assert client.get(f"/api/v1/jobs/{job_id}/{path}").status_code == code
    cancelled = client.post(f"/api/v1/jobs/{job_id}/cancel", headers=HEADERS)
    assert cancelled.json()["status"] == "cancelled"
    again = client.post(f"/api/v1/jobs/{job_id}/cancel", headers=HEADERS)
    assert again.status_code == 409 and again.json()["code"] == "job_finished"
    assert client.post(f"/api/v1/jobs/{'f' * 32}/cancel", headers=HEADERS).status_code == 404


def test_upload_limits_endpoint(client: TestClient):
    limits = client.get("/api/v1/upload-limits").json()
    assert limits["max_bytes"] > 0 and "mp4" in limits["extensions"]
