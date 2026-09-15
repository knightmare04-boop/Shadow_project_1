"""Liveness/readiness endpoints — Module 8 (Uptime Kuma probes these).

``/health`` answers "is the process alive" (always 200 unless truly wedged).
``/ready`` answers "can this instance actually serve traffic": DB reachable,
Redis reachable, the fraud-scoring bundle loaded. Neo4j is deliberately
excluded — it is optional-by-design and its absence must never flip readiness.
"""
from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.db.redis_client import check_redis_connection
from app.db.session import check_db_connection

router = APIRouter(tags=["system"])


@router.get("/health")
async def health():
    return {"status": "alive"}


@router.get("/ready")
async def ready(response: Response):
    db_ok = await check_db_connection()
    redis_ok = await check_redis_connection()

    from app.services.scoring_registry import scoring_bundles_loaded
    scoring_ok = scoring_bundles_loaded()

    checks = {"database": db_ok, "redis": redis_ok, "scoring_bundles": scoring_ok}
    overall_ok = all(checks.values())
    if not overall_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ready" if overall_ok else "not_ready", "checks": checks}
