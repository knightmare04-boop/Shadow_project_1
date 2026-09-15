# Module 8 — Observability

## What's running and verified

```bash
docker compose -f infra/docker-compose.yml -f infra/docker-compose.observability.yml up -d
```

| Service | URL | Verified |
|---|---|---|
| Prometheus | http://localhost:9090 | ✅ `shadow-ledger-api` target healthy, scraping `/metrics` every 10s; confirmed real `http_requests_total` series present via `/api/v1/query` |
| Grafana | http://localhost:3000 (admin / `GRAFANA_ADMIN_PASSWORD` in `.env`, default `admin_dev_password`) | ✅ Prometheus datasource + "Shadow Ledger — Overview" dashboard both auto-provisioned on container start, confirmed via `/api/search` |
| Uptime Kuma | http://localhost:3001 | ✅ container healthy; monitors NOT auto-provisioned (see below) |

## Metrics exposed (`app/core/metrics.py`)

- `http_requests_total{method,path,status}` / `http_request_duration_seconds` — RED metrics, labeled by **route template** (`/api/v1/vendors/{vendor_id}`, not the raw UUID) so cardinality stays bounded
- `fraud_scoring_latency_seconds{dataset}` — the live-scoring latency histogram (Module 5); this is where the paper's <200ms p95 claim gets its number
- `http_cache_hits_total` / `http_cache_misses_total{cache_key_prefix}` — Module 7's cache, hit-rate derivable as `hits/(hits+misses)`
- `duplicate_payment_attempts_total` — should be non-zero only during the Module 9 race drill; non-zero in steady-state traffic is a real incident signal (something is retrying payments without an idempotency key)

Dashboard panels (`infra/observability/grafana/provisioning/dashboards/json/shadow-ledger-overview.json`):
request rate by path, 5xx error rate, p95 latency by path, fraud-scoring
latency p50/p95/p99, cache hit rate, duplicate-payment attempts.

## Uptime Kuma — one-time manual setup

Uptime Kuma has no file-based provisioning (its monitor API is
socket.io-driven, not a simple REST/config surface suited to
docker-compose-time automation). After first boot, add two HTTP monitors
via the UI (http://localhost:3001):

1. **Liveness** — `http://host.docker.internal:8000/health`, interval 30s.
2. **Readiness** — `http://host.docker.internal:8000/ready`, interval 30s,
   "Upside Down Mode" off, expected status 200 (Module 1's `/ready` already
   returns 503 the instant DB/Redis/scoring are unavailable — see
   `app/api/system.py` — so Uptime Kuma just needs to alert on non-200).

A synthetic-transaction monitor (post + reconcile a canary invoice) is a
Module 9 concern, not a passive uptime check — see the backup/restore drill
and `tools/reconcile_payments.py`.

## GlitchTip — deliberately not deployed here

GlitchTip (Sentry-compatible error tracking) is a full Django application
needing its own Postgres database, Redis, and a Celery worker — a
standalone deployment, not a docker-compose add-on line. The project's
actual error-logging mechanism, live since Module 1 and exercised
throughout every module since, is structured JSON logging
(`app/core/logging.py`) with correlation-id propagation from the access log
through every service call — every bug found during Modules 3-7 was
diagnosed from these logs, not a hunch. `GLITCHTIP_DSN` is already read by
`app/core/config.py`; wiring a real GlitchTip instance is a drop-in change
whenever one exists to point at.

## Verification commands

```bash
curl -s http://localhost:8000/metrics | grep http_requests_total
curl -s http://localhost:9090/api/v1/targets | python -m json.tool
curl -s -u admin:admin_dev_password http://localhost:3000/api/search
```
