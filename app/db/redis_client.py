"""Redis connection — backs idempotency keys (Module 4) and the response
cache (Module 7). One pooled client per process; degradation is explicit:
callers must decide what "Redis is down" means for them (cache miss is safe
to ignore, idempotency-key check is NOT — see app.services.idempotency).
"""
from __future__ import annotations

from redis.asyncio import ConnectionPool, Redis

from app.core.config import get_settings

settings = get_settings()

_pool = ConnectionPool.from_url(settings.redis_url, decode_responses=True, max_connections=50)


def get_redis() -> Redis:
    return Redis(connection_pool=_pool)


async def check_redis_connection() -> bool:
    try:
        r = get_redis()
        return bool(await r.ping())
    except Exception:
        return False
