"""FastAPI application factory."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.alerts import router as alerts_router
from app.api.auth import router as auth_router
from app.api.gl import router as gl_router
from app.api.invoices import router as invoices_router
from app.api.payments import router as payments_router
from app.api.system import router as system_router
from app.api.vendors import router as vendors_router
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.idempotency_middleware import IdempotencyMiddleware
from app.core.logging import configure_logging, get_logger
from app.core.metrics import MetricsMiddleware, metrics_endpoint
from app.core.middleware import CorrelationIdMiddleware

settings = get_settings()
configure_logging(json_logs=settings.is_production)
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("startup", env=settings.env)
    try:
        from app.services.scoring_registry import load_all_online_bundles
        results = load_all_online_bundles()
        log.info("scoring_bundles_startup", results=results)
    except Exception as exc:  # noqa: BLE001 — the ERP must boot even if scoring can't
        log.error("scoring_bundles_startup_failed", error=str(exc))
    yield
    log.info("shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="The Self-Auditing Ledger",
        description="Procure-to-Pay ERP with a leakage-free temporal-graph fraud audit console.",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Middleware executes outer-to-inner in ADD order reversed (Starlette
    # wraps each addition around the previous stack), so the order below
    # means: CORS runs first on the way in, then idempotency (needs the
    # correlation id already set for its own logging), then correlation id
    # innermost... Concretely what matters: correlation id must be set
    # before anything logs, and idempotency must wrap the actual route
    # handler so it can capture/replay the real response body.
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=500)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Correlation-ID"],
    )

    register_error_handlers(app)

    @app.get("/metrics", include_in_schema=False)
    async def _metrics():
        return metrics_endpoint()

    app.include_router(system_router)
    app.include_router(auth_router)
    app.include_router(vendors_router)
    app.include_router(gl_router)
    app.include_router(invoices_router)
    app.include_router(payments_router)
    app.include_router(alerts_router)

    return app


app = create_app()
