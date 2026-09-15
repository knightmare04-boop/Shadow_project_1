"""Cross-cutting HTTP middleware: correlation-id propagation and structured
access logging. Compression (hardening #9) is handled by Starlette's
GZipMiddleware plus a brotli pass registered in app.main.
"""
from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.logging import get_logger, new_correlation_id

log = get_logger(__name__)

CORRELATION_ID_HEADER = "X-Correlation-ID"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Accepts an inbound correlation id (for traces that span multiple
    services) or mints a fresh one; always echoes it back on the response so
    the frontend can show it in an error toast for support purposes."""

    async def dispatch(self, request: Request, call_next):
        inbound = request.headers.get(CORRELATION_ID_HEADER)
        cid = inbound or new_correlation_id()
        if inbound:
            from app.core.logging import set_correlation_id
            set_correlation_id(inbound)

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        response.headers[CORRELATION_ID_HEADER] = cid
        log.info(
            "request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )
        return response
