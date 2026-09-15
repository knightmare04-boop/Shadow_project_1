# Module 7 — Query Optimization: Before/After

Measured against a bulk-seeded dev database (`tools/seed_volume.py`, seed=42,
reproducible): 5,000 vendors, 40,000 invoices, 23,929 payments, 5,000 audit
alerts. `ANALYZE` run after each bulk load so planner statistics are current
— skipping this step is itself a common source of bad plans, worth noting.

## 1. Paid invoices, newest first (`WHERE status='paid' ORDER BY invoice_date DESC LIMIT 50`)

The alert-queue-equivalent pattern for invoices — "show me the latest N
matching rows" — is the single most common shape of query this app runs.

| | Before | After |
|---|---|---|
| Plan | Bitmap Heap Scan (23,929 rows) → Sort (top-N heapsort) | Index Scan Backward, no sort |
| Buffer hits | 875 | 50 |
| Execution time | 6.331 ms | 0.301 ms |
| **Speedup** | | **~21×** |

Fix: `Index("ix_ap_invoices_status_invoice_date", "status", "invoice_date")`
(`app/models/invoice.py`). The single-column `status` index let Postgres
find matching rows fast, but it then had to sort **all 23,929** of them to
answer "give me the top 50 by date" — the composite index makes the rows
already arrive in the needed order, so `LIMIT 50` stops after 50 rows, not
after touching every match.

## 2. Alert queue (`ORDER BY score DESC LIMIT 50`)

No index existed on `score` at all before Module 7 — the query would have
been a full seq-scan-and-sort as the table grew past a few hundred rows
(the table was empty during Module 5/6 testing, so this was never
measured until bulk data existed).

| | Before | After |
|---|---|---|
| Plan (5,000 rows) | Seq Scan → Sort | Index Scan (DESC) |
| Execution time | *(not measured — no index existed; would degrade linearly with table size)* | 0.236 ms |

Fix: `Index("ix_audit_alerts_score", "score", postgresql_ops={"score": "DESC"})`.

## 3. Vendor-scoped invoice listing (`WHERE vendor_id=? ORDER BY id LIMIT 50`)

| | Before | After |
|---|---|---|
| Plan | Bitmap Index Scan (`ix_ap_invoices_vendor_id`) → Sort | **same** — planner did not switch to the new composite index |
| Execution time | 0.253 ms | 0.317 ms (no meaningful change) |

**Honest finding, not a win**: `Index("ix_ap_invoices_vendor_id_id", "vendor_id", "id")`
was added expecting the same pattern as #1, but at this dataset's
distribution (~8 invoices/vendor average, 40k invoices / 5k vendors) the
planner correctly judges the existing single-column index + a tiny sort of
~8 rows cheap enough already — the composite index isn't selected. Kept in
the schema anyway: it costs little to maintain and becomes the right choice
the moment vendor invoice volume is skewed (a high-volume vendor with
thousands of invoices would hit the same bottleneck as #1). Reported here
rather than silently dropped or claimed as a win it isn't — that's the
whole point of measuring rather than guessing.

## 4. `pg_stat_statements` — top query by total time

Enabled from Module 1 (`infra/docker-compose.yml`'s `shared_preload_libraries`).
Query:

```sql
SELECT query, calls, total_exec_time, mean_exec_time
FROM pg_stat_statements ORDER BY total_exec_time DESC LIMIT 20;
```

Available for ongoing monitoring via Grafana (Module 8) — not reproduced
here as a static table since it reflects whatever traffic has hit this dev
instance, not a stable benchmark.

## Reproduction

```bash
docker compose -f infra/docker-compose.yml up -d postgres redis
python -m tools.seed_core
python -m tools.seed_volume            # 5000/40000/25000, seed=42
```

Then run the `EXPLAIN (ANALYZE, BUFFERS)` queries above via `docker exec
ledger-postgres psql -U ledger -d shadow_ledger -c "..."`.

## Migration

`alembic/versions/7f796bc977a2_module7_performance_indexes.py` — 4 indexes,
all `CREATE INDEX` (not `CONCURRENTLY`; acceptable for this dev-scale
migration, but a production rollout against a live table under write load
should use `postgresql_concurrently=True` outside a transaction block to
avoid locking writes for the duration of the build).
