from __future__ import annotations

import os
import tempfile
from pathlib import Path

# Keep Ultralytics away from the user's profile and offline during tests,
# before anything can import it.
os.environ.setdefault("YOLO_CONFIG_DIR", tempfile.mkdtemp(prefix="fa-tests-ultralytics-"))
os.environ.setdefault("YOLO_OFFLINE", "1")
os.environ.setdefault("ULTRALYTICS_SAFE_LOAD", "1")

import pytest
from fastapi.testclient import TestClient

from fight_analyzer.api.app import create_app
from fight_analyzer.config import Settings
from fight_analyzer.jobs.store import JobStore


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    s = Settings(data_dir=tmp_path / "data", worker_heartbeat_interval_s=0.2)
    s.ensure_dirs()
    return s


@pytest.fixture
def store(settings: Settings) -> JobStore:
    store = JobStore(settings.db_path)
    store.initialize()
    return store


@pytest.fixture
def client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings), base_url="http://127.0.0.1")
