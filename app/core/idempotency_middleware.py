"""Wires app.services.idempotency into the request pipeline.

Applies only to POST/PUT/PATCH requests that carry an ``Idempotency-Key``
header — GET/DELETE are naturally idempotent (or, for DELETE, made
idempotent at the service layer) and don't need this. Requests WITHOUT the
header are not blocked (some endpoints are read-only or intentionally
non-idempotent, e.g. a search) — routes that require the header for safety
(payment posting, invoice submission) enforce that with a FastAPI dependency
at the route level, not here.
"""
from __future__ import annotations

import json

from redis.exceptions import RedisError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.errors import PROBLEM_JSON
from app.core.logging import get_logger
from app.db.redis_client import get_redis
from app.services.idempotency import (
    IdempotencyConflict, IdempotencyInProgress,
    claim_or_replay, hash_body, release_claim, store_result,
)

log = get_logger(__name__)

_IDEMPOTENT_METHODS = {"POST", "PUT", "PATCH"}
IDEMPOTENCY_HEADER = "Idempotency-Key"


class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        key = request.headers.get(IDEMPOTENCY_HEADER)
        if request.method not in _IDEMPOTENT_METHODS or not key:
            return await call_next(request)

        body = await request.body()
        body_hash = hash_body(body)
        redis = get_redis()

        try:
            replay = await claim_or_replay(redis, key, body_hash)
        except IdempotencyConflict as exc:
            return JSONResponse(
                status_code=409,
                media_type=PROBLEM_JSON,
                content={
                    "type": "https://errors.shadow-ledger.internal/idempotency_key_reuse",
                    "title": "Idempotency Key Reuse",
                    "status": 409,
                    "detail": str(exc),
                },
            )
        except IdempotencyInProgress as exc:
            return JSONResponse(
                status_code=409,
                media_type=PROBLEM_JSON,
                content={
                    "type": "https://errors.shadow-ledger.internal/idempotency_in_progress",
                    "title": "Request Still Processing",
                    "status": 409,
                    "detail": str(exc),
                },
            )
        except RedisError as exc:
            # Deliberate fail-CLOSED, not an accident of an uncaught
            # exception: a request carrying an Idempotency-Key is, by
            # definition, one the client considers unsafe to blindly retry
            # (a payment, most often). If Redis — the only thing standing
            # between "retry" and "duplicate side effect" here — is
            # unreachable, refusing the request is safer than silently
            # executing it without the safety net the client asked for.
            # (Found and fixed following the Module 11 architecture
            # review's question (f)/(g): the original code let this
            # propagate into a generic, undocumented 500.)
            log.error("idempotency_backend_unavailable", key=key, error=str(exc))
            return JSONResponse(
                status_code=503,
                media_type=PROBLEM_JSON,
                content={
                    "type": "https://errors.shadow-ledger.internal/upstream_unavailable",
                    "title": "Upstream Unavailable",
                    "status": 503,
                    "detail": (
                        "The idempotency-key store is temporarily unavailable. "
                        "This request was NOT executed — retry with the same "
                        "Idempotency-Key once the service recovers."
                    ),
                },
            )

        if replay is not None:
            log.info("idempotency_replay", key=key)
            return Response(
                content=replay.body, status_code=replay.status_code,
                headers={**replay.headers, "X-Idempotent-Replay": "true"},
                media_type=replay.headers.get("content-type", "application/json"),
            )

        # We hold the claim. Execute the real handler, then persist the
        # outcome (success OR the error response — a client retrying after a
        # 422 with the same key+body should get the same 422 back, not a
        # second validation pass with different side effects).
        try:
            response = await call_next(request)
        except Exception:
            await release_claim(redis, key)
            raise

        response_body = b""
        async for chunk in response.body_iterator:
            response_body += chunk if isinstance(chunk, bytes) else chunk.encode()

        await store_result(
            redis, key, body_hash,
            status_code=response.status_code,
            headers={"content-type": response.headers.get("content-type", "application/json")},
            response_body=response_body.decode("utf-8", errors="replace"),
        )

        return Response(
            content=response_body, status_code=response.status_code,
            headers=dict(response.headers), media_type=response.media_type,
        )
