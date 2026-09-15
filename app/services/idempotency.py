"""Idempotency-Key store, backed by Redis.

Contract: a client sends ``Idempotency-Key: <opaque-string>`` on any
state-changing request. Same key + same request body -> the ORIGINAL
response is replayed, the handler never runs twice. Same key + a DIFFERENT
body -> rejected (409) as a key-reuse error, since silently accepting that
would let a client accidentally replay the wrong payload under an old key.

Concurrency: two requests with the same key arriving at the same instant
(the literal double-click case) are serialized by a Redis SETNX claim — the
second waits briefly for the first to finish and then replays its result,
rather than racing the handler twice.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass

from redis.asyncio import Redis

from app.core.config import get_settings

settings = get_settings()

_KEY_PREFIX = "idempotency:"
_CLAIM_POLL_INTERVAL_S = 0.1
_CLAIM_MAX_WAIT_S = 8.0


def _redis_key(idempotency_key: str) -> str:
    return f"{_KEY_PREFIX}{idempotency_key}"


def hash_body(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


@dataclass
class StoredResponse:
    status_code: int
    headers: dict
    body: str  # already-serialized JSON text


class IdempotencyConflict(Exception):
    """Same key, different body — the client reused a key incorrectly."""


class IdempotencyInProgress(Exception):
    """Same key, same body, but the original request is still executing and
    did not finish within the wait budget. The client should retry the GET
    of the resulting resource, or retry the same request later — never with
    a NEW key, which would create a duplicate side effect."""


async def claim_or_replay(redis: Redis, idempotency_key: str, body_hash: str) -> StoredResponse | None:
    """Returns a StoredResponse to replay immediately, or None if this call
    successfully claimed the key and the caller should execute the handler
    and then call `store_result`. Raises IdempotencyConflict / InProgress."""
    rkey = _redis_key(idempotency_key)

    claimed = await redis.set(
        rkey,
        json.dumps({"status": "in_progress", "body_hash": body_hash, "claimed_at": time.time()}),
        nx=True,
        ex=settings.idempotency_key_ttl_seconds,
    )
    if claimed:
        return None  # we own it — caller executes the handler

    # Someone else holds (or held) this key. Poll until it resolves.
    deadline = time.monotonic() + _CLAIM_MAX_WAIT_S
    while time.monotonic() < deadline:
        raw = await redis.get(rkey)
        if raw is None:
            # Expired/evicted between our GET and now — safe to re-claim.
            return await claim_or_replay(redis, idempotency_key, body_hash)
        record = json.loads(raw)
        if record.get("body_hash") != body_hash:
            raise IdempotencyConflict(
                f"idempotency key {idempotency_key!r} was already used with a different request body"
            )
        if record.get("status") == "completed":
            return StoredResponse(
                status_code=record["status_code"], headers=record["headers"], body=record["response_body"],
            )
        await asyncio.sleep(_CLAIM_POLL_INTERVAL_S)

    raise IdempotencyInProgress(
        f"request with idempotency key {idempotency_key!r} is still being processed"
    )


async def store_result(redis: Redis, idempotency_key: str, body_hash: str, *,
                        status_code: int, headers: dict, response_body: str) -> None:
    rkey = _redis_key(idempotency_key)
    await redis.set(
        rkey,
        json.dumps({
            "status": "completed",
            "body_hash": body_hash,
            "status_code": status_code,
            "headers": headers,
            "response_body": response_body,
        }),
        ex=settings.idempotency_key_ttl_seconds,
    )


async def release_claim(redis: Redis, idempotency_key: str) -> None:
    """Called when the handler itself raised — release the claim so a retry
    with the same key is treated as a fresh attempt, not stuck 'in_progress'
    until TTL expiry."""
    await redis.delete(_redis_key(idempotency_key))
