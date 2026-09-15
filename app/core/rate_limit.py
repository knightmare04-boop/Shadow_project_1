"""Simple Redis-backed rate limiter. Built specifically for the login
endpoint after the Module 11 architecture review flagged it: bcrypt's own
work factor makes /auth/login a real, unthrottled DoS/brute-force vector
without one.

Fixed window, not sliding — good enough for "stop brute force," not
intended as a general-purpose API rate limiter (Redis INCR+EXPIRE, one key
per identity+window). Fails OPEN on Redis errors deliberately: unlike the
idempotency middleware (Section 11 finding — see
app/core/idempotency_middleware.py), a rate limiter's job is to shed
excess load, not to guard a financial invariant, so an unreachable Redis
should not turn into "nobody can log in."
"""
from __future__ import annotations

import time

from redis.exceptions import RedisError

from app.core.logging import get_logger
from app.db.redis_client import get_redis

log = get_logger(__name__)


async def check_rate_limit(*, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
    """Returns (allowed, retry_after_seconds). `key` should already include
    the identity being limited (e.g. f"login:{email}") — callers choose the
    granularity."""
    redis = get_redis()
    window = int(time.time()) // window_seconds
    redis_key = f"ratelimit:{key}:{window}"

    try:
        count = await redis.incr(redis_key)
        if count == 1:
            await redis.expire(redis_key, window_seconds)
        if count > limit:
            ttl = await redis.ttl(redis_key)
            return False, max(ttl, 1)
        return True, 0
    except RedisError as exc:
        log.warning("rate_limit_check_failed_open", key=key, error=str(exc))
        return True, 0
