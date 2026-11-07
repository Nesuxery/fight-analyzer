"""FastAPI application factory.

Run: uvicorn fight_analyzer.api.app:create_app --factory --host 127.0.0.1 --port 8000

The API only reads/writes job state and files; analysis runs in the
separate worker process, so long jobs never block requests.
"""

from __future__ import annotations

from fastapi import FastAPI
from starlette.middleware.trustedhost import TrustedHostMiddleware

from fight_analyzer import __version__
from fight_analyzer.config import Settings, apply_runtime_env, load_settings
from fight_analyzer.jobs.store import JobStore

from .errors import ApiProblem, LocalClientGuard, api_problem_handler
from .routes import health, jobs
from .uploads import clear_incoming


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    apply_runtime_env(settings)
    settings.ensure_dirs()
    clear_incoming(settings)
    store = JobStore(settings.db_path)
    store.initialize()

    app = FastAPI(
        title="MMA Fight Analyzer API",
        version=__version__,
        # No Swagger page: it would load scripts from a CDN. The schema stays available.
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.state.settings = settings
    app.state.store = store
    app.add_exception_handler(ApiProblem, api_problem_handler)
    app.add_middleware(LocalClientGuard)
    # Local-only app: reject requests whose Host is not loopback (DNS rebinding).
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(jobs.router, prefix="/api/v1")
    return app
