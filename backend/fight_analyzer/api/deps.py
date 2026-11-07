from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from fight_analyzer.config import Settings
from fight_analyzer.jobs.store import JobStore


def get_store(request: Request) -> JobStore:
    return request.app.state.store


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


StoreDep = Annotated[JobStore, Depends(get_store)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
