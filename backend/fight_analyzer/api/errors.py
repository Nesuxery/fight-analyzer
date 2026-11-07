"""API error responses and request guards."""

from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from fight_analyzer.contracts import ErrorResponse

# Required on state-changing requests. A custom header makes browsers send a
# CORS preflight for cross-site requests, which this API never approves, so
# other web pages cannot upload or cancel jobs on this machine.
CLIENT_HEADER = "X-Fight-Analyzer"
_LOCAL_HOSTS = {"127.0.0.1", "localhost"}


class ApiProblem(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def problem_response(status: int, code: str, message: str) -> JSONResponse:
    body = ErrorResponse(code=code, message=message).model_dump(mode="json")
    return JSONResponse(body, status_code=status)


async def api_problem_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ApiProblem)
    return problem_response(exc.status, exc.code, exc.message)


class LocalClientGuard(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("origin")
            if origin and urlsplit(origin).hostname not in _LOCAL_HOSTS:
                return problem_response(403, "forbidden_origin", "İstek bu bilgisayardan gelmiyor.")
            if request.headers.get(CLIENT_HEADER) != "1":
                return problem_response(403, "missing_client_header",
                                        f"{CLIENT_HEADER} başlığı gerekli.")
        return await call_next(request)
