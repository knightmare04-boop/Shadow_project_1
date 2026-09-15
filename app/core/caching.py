"""Redis response caching with ETag/304 support (hardening item #10).

Deliberately NOT a blanket middleware over every GET — caching is opt-in per
endpoint (`cached_json`) because correctness depends on the caller picking a
sane key (must include every parameter that affects the response) and TTL,
and because some GET endpoints (payments, alerts) need to be fresher than a
cache would allow. Vendors/GL-accounts are the good fit: read-heavy,
change rarely, and have a clear invalidation point (their own create/update
routes).
"""
from __future__ import annotations

import hashlib
import json

from fastapi import Request, Response, status

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.metrics import CACHE_HITS, CACHE_MISSES
from app.db.redis_client import get_redis

log = get_logger(__name__)
settings = get_settings()

_PREFIX = "http_cache:"


def _etag_for(body: str) -> str:
    return 'W/"' + hashlib.sha256(body.encode("utf-8")).hexdigest()[:16] + '"'


async def cached_json(
    request: Request, response: Response, *, cache_key: str, ttl: int | None = None,
    compute,
):
    """Serves `compute()` (an async callable returning a JSON-serializable
    value) through the cache. Handles If-None-Match -> 304 and sets
    Cache-Control/ETag on every response so the browser's own cache
    cooperates too, not just Redis server-side."""
    redis = get_redis()
    key = f"{_PREFIX}{cache_key}"

    try:
        cached_body = await redis.get(key)
    except Exception as exc:  # noqa: BLE001 — cache is an optimization, never a dependency
        log.warning("cache_read_failed", key=cache_key, error=str(exc))
        cached_body = None

    prefix = cache_key.split(":", 1)[0]
    if cached_body is None:
        CACHE_MISSES.labels(cache_key_prefix=prefix).inc()
        value = await compute()
        cached_body = json.dumps(value, default=str)
        try:
            await redis.set(key, cached_body, ex=ttl or settings.cache_default_ttl_seconds)
        except Exception as exc:  # noqa: BLE001
            log.warning("cache_write_failed", key=cache_key, error=str(exc))
    else:
        CACHE_HITS.labels(cache_key_prefix=prefix).inc()

    etag = _etag_for(cached_body)
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = f"private, max-age={ttl or settings.cache_default_ttl_seconds}"

    inm = request.headers.get("if-none-match")
    if inm and inm == etag:
        response.status_code = status.HTTP_304_NOT_MODIFIED
        return None

    return json.loads(cached_body)


async def invalidate_cache(pattern: str) -> int:
    """Delete every cached key matching `pattern` (e.g. 'vendors:*'). Called
    from the write side of a cached resource — see app/api/vendors.py."""
    redis = get_redis()
    n = 0
    async for key in redis.scan_iter(match=f"{_PREFIX}{pattern}"):
        await redis.delete(key)
        n += 1
    return n
