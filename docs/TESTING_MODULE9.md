# Module 9 — Testing, Concurrency, and Disaster Drills

Every number below is from an actual run, not a projection. Reproduction
commands are given for each.

## 1. Duplicate-payment race (formal, k6) — `tests/load/payment_race.js`

30 virtual users fire truly concurrent `POST /api/v1/payments` at the SAME
invoice, each with a **different** idempotency key (the scenario a single
retried request's idempotency key alone cannot cover).

```bash
docker run --rm -i --add-host=host.docker.internal:host-gateway \
  -e API_BASE=http://host.docker.internal:8000 -e VUS=30 \
  grafana/k6 run - < tests/load/payment_race.js
```

**Result: exactly 1 success, 29/29 correctly rejected with `duplicate_payment`.**

```
payment_race_success..............: 1
payment_race_duplicate_rejected...: 29
✓ 409 body names duplicate_payment  (29/29 checks passed)
http_req_duration (successful)....: avg=267ms  p95=807ms
```

Database confirms exactly one `payments` row for the target invoice after
the run. This is the automated, repeatable version of the earlier manual
curl-based proof (20 concurrent requests, same result) from Module 4.

## 2. Simultaneous users — staged ramp — `tests/load/mixed_workload.js`

70% browse / 20% invoice submission / 10% alert-queue reads, ramped
0→50→200→500 concurrent VUs over ~5 minutes against a single dev-mode
`uvicorn` process (no worker pool) with a 40-connection DB pool
(`db_pool_size=20 + db_max_overflow=20`).

```bash
docker run --rm -i --add-host=host.docker.internal:host-gateway \
  -e API_BASE=http://host.docker.internal:8000 \
  grafana/k6 run - < tests/load/mixed_workload.js
```

| Stage | p95 latency | Error rate |
|---|---|---|
| Overall (all stages combined) | 8.18 s | 4.42% |
| Threshold check (`p95<1000ms`) | **FAILED** | `http_req_failed rate<0.05` passed (4.42% < 5%) |

**Honest finding, not a pass**: the system clearly degrades well before 500
VUs — 39,727 requests attempted, 28,642 iterations completed, p95 latency
rose to 8+ seconds with i/o timeouts appearing during the highest-VU stage.
This is expected and worth stating plainly: **a single uvicorn process with
a 40-connection pool is a dev-mode configuration, not a production
deployment**. The degradation point itself is the useful number — it tells
you exactly where horizontal scaling (`--workers N`, a larger pool, or
multiple app instances behind a load balancer) becomes necessary, which is
more actionable than a binary pass/fail gate would have been. Not
re-tuned and re-run in this session given the scope already covered;
recorded here as the concrete next step for a production rollout.

## 3. Backup / restore drill — `tools/drills/backup_restore.py`

```bash
python -m tools.drills.backup_restore
```

Takes a `pg_dump -Fc` of the live database, restores into a clean
throwaway database (`shadow_ledger_restore_drill`, dropped after
comparison — the live database is never touched by the restore step),
fingerprints both (row counts across every financially-relevant table +
total payment amount), and asserts they match exactly.

**Result: PASSED.**

```json
{
  "before": {"row_counts": {"vendors": 5001, "ap_invoices": 45284, "ap_invoice_lines": 45284,
             "payments": 23930, "gl_accounts": 13, "audit_alerts": 5001, "audit_log": 5304},
             "total_payment_amount": "60370370.20"},
  "after":  { /* identical, verified programmatically */ },
  "match": true,
  "dump":    {"seconds": 0.95, "size_mb": 6.99},
  "restore": {"seconds": 2.12},
  "rto_seconds": 3.07
}
```

**RTO = 3.07 s** at this data volume (~74k rows across the audited tables).
**RPO** depends on schedule, not this drill: an on-demand dump has RPO≈0;
a nightly cron dump has RPO up to 24h; continuous WAL archiving (already
enabled in `infra/docker-compose.yml`'s `archive_mode=on`) enables
point-in-time recovery with a much tighter RPO than daily dumps allow —
not exercised end-to-end in this session (PITR replay is a longer drill
than time permitted here), noted as the natural next drill.

**A real methodology finding from running this twice**: the first attempt
(taken while the k6 mixed-workload test was still writing concurrently)
correctly reported a fingerprint MISMATCH — not a backup/restore bug, but
a demonstration that `pg_dump` does not block concurrent writers (Postgres
MVCC), so a fingerprint taken via a separate query before the dump can
legitimately diverge from what the dump itself captured a moment later.
Re-run on quiescent data for a clean comparison; the drill script's docstring
notes the more rigorous fix (a shared `pg_export_snapshot()`) as a known
simplification.

## 4. Duplicate-invoice and three-way-match correctness

Covered by `tests/test_matching_service.py` (clean match / price variance /
missing receipt, all three verified — see Module 6) and the duplicate-invoice
partial unique index (Module 3, proven via direct SQL test).

## 5. Not yet formalized as pytest / testcontainers CI suite

The domain-logic tests in this repo (`tests/test_matching_service.py`,
the online-topology/ordinary parity tests) run against the live dev
Postgres via `app.db.session`, not an isolated testcontainers database —
a pragmatic choice given the scope already covered this session. A CI-ready
suite would spin an ephemeral Postgres per test run
(`pip install -e ".[test]"` already includes `testcontainers[postgres]`
for exactly this) rather than depending on `docker compose up` having been
run first.
