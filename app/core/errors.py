"""RFC 9457 (application/problem+json) error envelope — hardening item #1.

Every error the API returns, whether raised deliberately (``AppError`` and its
subclasses) or an unhandled exception, is normalized to this shape. No stack
trace or internal detail ever reaches the client; the full detail (with
correlation id) goes to the structured log only.
"""
from __future__ import annotations

import uuid

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_correlation_id, get_logger

log = get_logger(__name__)

PROBLEM_JSON = "application/problem+json"


class AppError(Exception):
    """Base for every deliberately-raised application error.

    ``error_code`` is a stable, typed string the frontend and tests can switch
    on (never parse ``detail`` text). ``status_code`` follows RFC 9457 usage of
    HTTP status as the primary signal.
    """

    status_code: int = status.HTTP_400_BAD_REQUEST
    error_code: str = "bad_request"

    def __init__(self, detail: str, *, error_code: str | None = None, extra: dict | None = None):
        super().__init__(detail)
        self.detail = detail
        if error_code:
            self.error_code = error_code
        self.extra = extra or {}


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "not_found"


class ConflictError(AppError):
    """Raised on unique-constraint violations the app recognizes semantically
    (duplicate invoice, duplicate payment, closed-period posting, etc.)."""

    status_code = status.HTTP_409_CONFLICT
    error_code = "conflict"


class DuplicatePaymentError(ConflictError):
    error_code = "duplicate_payment"


class DuplicateSubmissionError(ConflictError):
    error_code = "duplicate_submission"


class ValidationAppError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    error_code = "validation_error"


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "unauthorized"


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "forbidden"


class RateLimitedError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "rate_limited"


class UpstreamUnavailableError(AppError):
    """The fraud-scoring service (or another dependency) is down/circuit-open.
    Distinguishes "we refused" (4xx) from "the system degraded" (503) so
    dashboards and alerting can tell the two apart."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "upstream_unavailable"


def _problem(request: Request, *, status_code: int, error_code: str, detail: str,
             extra: dict | None = None) -> JSONResponse:
    cid = get_correlation_id() or str(uuid.uuid4())
    body = {
        "type": f"https://errors.shadow-ledger.internal/{error_code}",
        "title": error_code.replace("_", " ").title(),
        "status": status_code,
        "detail": detail,
        "instance": str(request.url.path),
        "correlation_id": cid,
    }
    if extra:
        body.update(extra)
    return JSONResponse(status_code=status_code, content=body, media_type=PROBLEM_JSON)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error_handler(request: Request, exc: AppError):
        log.warning("app_error", error_code=exc.error_code, detail=exc.detail, path=str(request.url.path))
        return _problem(request, status_code=exc.status_code, error_code=exc.error_code,
                         detail=exc.detail, extra=exc.extra)

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError):
        return _problem(
            request, status_code=422, error_code="validation_error",
            detail="Request failed validation.",
            extra={"errors": exc.errors()},
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception_handler(request: Request, exc: StarletteHTTPException):
        return _problem(request, status_code=exc.status_code,
                         error_code=f"http_{exc.status_code}", detail=str(exc.detail))

    @app.exception_handler(Exception)
    async def _unhandled_handler(request: Request, exc: Exception):
        cid = get_correlation_id() or str(uuid.uuid4())
        log.error("unhandled_exception", exc_info=exc, path=str(request.url.path), correlation_id=cid)
        return _problem(
            request, status_code=500, error_code="internal_error",
            detail="An internal error occurred. It has been logged.",
        )
