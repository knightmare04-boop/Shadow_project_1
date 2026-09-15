"""Prometheus metrics — RED (Rate, Errors, Duration) per endpoint, plus the
app-specific counters Module 9's load tests and the paper's latency numbers
both read from: scoring latency, cache hit rate, and the
duplicate-payment-attempt counter (should be non-zero under the Module 9
race test and always zero in steady-state production traffic).
"""
from __future__ import annotations

import time

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "path", "status"],
)
HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds", "HTTP request duration", ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0),
)
SCORING_LATENCY = Histogram(
    "fraud_scoring_latency_seconds", "Live fraud-scoring latency (topology+ordinary+XGBoost+SHAP)",
    ["dataset"], buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.2, 0.5),
)
CACHE_HITS = Counter("http_cache_hits_total", "Response cache hits", ["cache_key_prefix"])
CACHE_MISSES = Counter("http_cache_misses_total", "Response cache misses", ["cache_key_prefix"])
DUPLICATE_PAYMENT_ATTEMPTS = Counter(
    "duplicate_payment_attempts_total",
    "Payment requests rejected by the duplicate-payment defence (any layer) — "
    "nonzero under the Module 9 race test is expected; nonzero in steady-state "
    "production traffic means something upstream is retrying without an idempotency key.",
)
DB_POOL_IN_USE = Gauge("db_pool_connections_in_use", "SQLAlchemy pool connections currently checked out")


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Route template, not the raw path, so /api/v1/vendors/<uuid> doesn't
        # explode into one Prometheus series per vendor.
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        route = request.scope.get("route")
        path = route.path if route is not None else request.url.path
        HTTP_REQUESTS_TOTAL.labels(method=request.method, path=path, status=response.status_code).inc()
        HTTP_REQUEST_DURATION.labels(method=request.method, path=path).observe(duration)
        return response


def metrics_endpoint() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
