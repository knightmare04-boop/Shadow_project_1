# Build Specification — The Self-Auditing Ledger Application + Research Paper

Generated 2026-09-15. This is the optimized form of the original request: every ask converted into
a numbered, independently verifiable acceptance criterion, plus explicit non-goals. No skill for
prompt engineering is installed on this machine (only `skill-creator`, which authors skills, not
prompts) — this document does that work by hand and is the artifact both implementation and review
are driven from. It supersedes the informal wording of the request; where they conflict, this
document and the approved plan (`sleepy-pebble.md`) govern.

## 0. Ground truth (do not re-derive — verified during planning + Module 0)

| Fact | Verified |
|---|---|
| `torch`, `fastapi`, `sqlalchemy`, `pyarrow`, `shap`, `sklearn`, `xgboost` (3.4.1), `lightgbm`, `neo4j` driver all install cleanly via `pip install -e ".[test,explain]"` | ✅ Module 0 |
| `kaggle==2.2.4` authenticates via `~/.kaggle/access_token` (new-format `KGAT_` token) with **zero kaggle.json needed** | ✅ Module 0 — `kaggle datasets list -s banksim` returned 4 results |
| Docker Desktop 29.8.0 running | ✅ Module 0 — `docker ps` responds |
| MiKTeX (`pdflatex`, `latexmk`) present | ✅ Planning |
| `pytest -q` → 6 passed | ✅ Module 0 |
| `artifacts/banksim/final/{bundle.json,model.json}` loads: 99 features, threshold 0.46208053827285767, best_iteration 228, booster intact | ✅ Module 0 |
| Full `modeling.score --verify` needs `data/processed/<ds>/features_manifest.json`, which needs Module 2's pipeline run first | ✅ Module 0 — confirmed exact dependency, not a defect |
| **ETL + topology engine are bit-for-bit reproducible**: fresh banksim/sap_wurzburg downloads reprocess to audit numbers matching the committed metrics EXACTLY (594,643/4,162/7,200 and 200,629/59,883/248) | ✅ Module 2 |
| **TGN embeddings are NOT bit-reproducible** across runs, even with `seed=42` fixed: re-running `modeling.tgn` on freshly-downloaded (same-source) banksim/sap_wurzburg data and then `modeling.score --verify` against the *committed* champion bundle fails (banksim recomputed test PR-AUC 0.845 vs bundle's 0.938; sap_wurzburg 0.098 vs 0.140) — PyTorch CPU training picks up small floating-point differences across machines that compound over epochs and propagate through a component that is 17-42% of the champion's feature importance | ✅ Module 2 — **paper §XII citable finding**; Module 5 trains fresh bundles from this machine's own processed data rather than assuming committed bundles will score-match |
| **`_expanding_account_stats`'s z-score formula (`cum_sq/count - mean²`) is numerically unstable** (textbook catastrophic cancellation): for accounts with near-identical historical amounts, it produces spurious extreme z-scores (observed up to ~10⁸) instead of ~0/undefined. Quantified on the full banksim dataset: 1,238/594,643 rows (0.21%), **every one** matching the exact pattern (batch \|z\|>1000, a numerically-stable Welford computation gives NaN/small). Module 5's online engine uses Welford's algorithm and does NOT reproduce this bug — deliberately propagating a known instability into new code is the wrong call, even though it costs a small, disclosed train/serve skew on 0.21% of rows | ✅ Module 5 — **paper §XII citable finding**, `app/services/online_ordinary.py` |
| `raw_root` in `config/datasets.yaml` points at another machine; **zero raw data ships in the repo** | ✅ Planning |
| SAP Würzburg source is a public Google Drive file (190 MB), no auth | ✅ Planning |
| IBM AML repo schema (`TX_ID/SENDER_ACCOUNT_ID/...`) is AMLSim-generator output, not the Kaggle `HI-Small_Trans.csv` layout — needs a schema adapter | ✅ Planning |

## 1. Hardening requirements — one row per ask, each with a named verification

| # | Requirement (as given) | Concrete acceptance criterion | Verified by |
|---|---|---|---|
| 1 | Error handling | Every API error returns RFC 9457 `application/problem+json` with a typed code; no stack trace leaves the process boundary | Contract tests, one per error class |
| 2 | Loading states | Every async UI surface shows a skeleton/spinner before data arrives; no unstyled blank flash | Playwright, per screen |
| 3 | Empty states | Every list/table has a typed empty state naming a next action, not just "no data" | Playwright, per screen |
| 4 | Handle failed requests | Timeout + bounded backoff + circuit breaker on every outbound call; ERP stays postable when the scorer is down | Chaos test: kill scorer, assert postings still succeed and alerts queue |
| 5 | Prevent dupe submissions | Idempotency-Key middleware: replay returns the original stored response, never re-executes | Integration test: same key twice → one side effect, two 200s |
| 6 | Prevent dupe payments | 5-layer defence (idempotency key, row lock, partial unique index, advisory lock, reconciliation job) | k6 race test: 50 concurrent identical payment requests → exactly 1 posted payment |
| 7 | Optimize DB queries | Every hot-path query has a captured `EXPLAIN (ANALYZE, BUFFERS)` before/after; N+1s eliminated | Committed before/after table, Module 7 |
| 8 | Add DB indexes | Indexes justified by an actual query plan, not guessed | Same before/after table shows index used, row estimate accurate |
| 9 | Compress files | gzip/brotli on API responses over threshold; brotli-precompressed hashed frontend assets | Response header check + bundle size report |
| 10 | Cache repeat requests | Redis response cache keyed on route+params+tenant+role, ETag/304 support, explicit invalidation on write | Cache hit-rate metric in Grafana; integration test for a 304 |
| 11 | Uptime monitoring | Uptime Kuma probing `/health` + `/ready` + a synthetic canary transaction | Kill Postgres → `/ready` flips red and an alert fires within 60s |
| 12 | Error logging | Structured JSON logs, correlation-id threaded through every layer, self-hosted GlitchTip ingesting them | Trigger a 500, confirm it appears in GlitchTip with the same correlation id as the access log |
| 13 | Test simultaneous users | k6 at 50/200/500 VUs across browse/create/pay mixes; report p50/p95/p99, error rate, degradation point | Committed k6 output, Module 9 |
| 14 | Test backup/restore | Scheduled `pg_dump`, documented restore into a clean volume, trial-balance + payment-count parity check, measured RTO/RPO | Drill actually run, output committed, not merely described |

## 2. Dataset acquisition — explicit ladder (your instruction: download first, generate only if unobtainable)

| Dataset | Primary | Fallback | Last resort |
|---|---|---|---|
| SAP Würzburg | Google Drive direct (public, 190 MB) | — | — |
| BankSim | Kaggle `ealaxi/banksim1` (token confirmed working) | — | — |
| IBM AML | Kaggle `ealtman2019/ibm-transactions-for-anti-money-laundering-aml` + schema adapter | AMLSim regeneration (Java 8 + Maven) | — |
| synth_erp | `python -m synth.generate` (deterministic, seeded, in-repo) | — | n/a — this dataset is *defined* as generated |
| PaySim | out of scope (repo has no results/artifacts for it — see plan) | | |

Every acquired dataset must pass `python -m topology.leakage_test` (hard gate) before its features or
models are used anywhere in the app or the paper.

## 3. Paper — non-negotiable content (from the project's own `CLAUDE.md` honesty rules)

The paper MUST include, not omit or soften:
- SAP Würzburg's negative topology lift (marginal_structure_lift = **−0.08288**)
- IBM AML's saturated baseline (PR-AUC 0.990) and the resulting "uninformative in the full model" framing
- The ablation's single-seed design and the explicit statement that ibm_aml's +0.00792 structure lift is *below* the project's own stated noise floor (~0.01 PR-AUC)
- Cycle features scoring ~0.0 gain importance on 3 of 4 datasets despite being the headline "shadow ledger" motif
- Synthetic augmentation hurting PR-AUC on all three real datasets
- The three reconciliation notes found during planning (SAP split-size mismatch between files, the two different "banksim baseline" numbers, foreign `artifact_dir` paths)
- Which datasets the *application* actually ran on live vs which the *paper's headline results* came from (these may differ — e.g. a Kaggle IBM AML re-download is a different simulator instance than the one behind the committed metrics, and must be labelled as a reproduction check, never merged into headline numbers)

## 4. Explicit non-goals (carried from the repo's own architecture docs)

- No production deployment inside a real SAP ABAP server or live bank settlement gateway
- No claim of millisecond production-hardened latency beyond the measured <200ms p95 target
- Neo4j remains visualization-only, optional, never load-bearing for scoring
- No federated learning implementation (documented as future work in the source project)

## 4a. Module 11 — LLM council review record

Two council reviews run (5 advisors + anonymized peer review + chairman synthesis each), full transcripts in `paper_council_chairman.md` and `arch_council_chairman.md` at repo root.

**Paper review — key verdict:** the central thesis as stated outruns the evidence (carried mainly by banksim; ibm_aml below the paper's own noise floor; sap_wurzburg negative on 25 frauds). Statistics need ≥5 seeds + bootstrap CIs before the ablation claim is submission-ready. **The council's top-priority "one thing to do first"** — rerun banksim on a second machine because the TGN irreproducibility swing (0.093) is suspiciously close to the headline lift (0.097) — **was checked and found to rest on a factual mix-up**: verified directly against `results/banksim/ablation.json`'s raw `features` lists and `experiments/ablation.py`'s source (`grep` for "tgn" returns nothing) that **the ablation arms contain zero `tgn_*` columns** — the ablation is pure ordinary+hand-crafted-topology XGBoost, entirely independent of the TGN pipeline the reproducibility finding is about. Re-ran the ablation fresh anyway to test the right thing (XGBoost-level reproducibility): marginal_structure_lift **+0.0885 vs committed +0.09736 (Δ0.009)** — within the paper's own ~0.01 noise floor, an order of magnitude more stable than TGN's 0.09 swing. The central claim is not a reproducibility artifact of that kind. Multi-seed ablation with real CIs remains the correct, un-actioned next step given remaining scope. (The fresh re-run transiently overwrote `results/banksim/ablation.json`; restored to the original committed values via `git checkout` immediately after recording the comparison — the committed research artifact is unchanged.)

**Architecture review — key verdict:** DB-level triggers for financial invariants unanimously endorsed as correct. Real, confirmed gaps found and **fixed in this session**: (1) the original k6 duplicate-payment test used distinct idempotency keys per VU and never exercised the SETNX claim/replay layer at all — **written and run** `tests/load/idempotency_replay_race.js` (same key, 25 concurrent VUs): exactly 1 original execution, 24 correct replays, 0 errors; (2) Redis-unavailable during an idempotency check fell through to an undocumented 500 — **fixed**: `app/core/idempotency_middleware.py` now fails closed with an explicit 503 `upstream_unavailable`; (3) `/auth/login` had no rate limiting against bcrypt-cost-factor brute force — **fixed**: `app/core/rate_limit.py` + wired into `app/api/auth.py`, tested live (10 attempts pass, 11th+ correctly 429, scoped per-email); (4) the double-entry trigger was only proven via raw `psql`, not the actual async FastAPI/SQLAlchemy commit path — **verified**: reran through `app.db.session.session_scope()` directly, correctly rejected with the same `CheckViolationError`. **Not fixed, documented as a known constraint**: the online `FraudScoringService` holds `WindowGraph`/`LapMemory` state in single-process memory (`app/services/scoring_registry.py`'s module docstring now states this explicitly) — the k6 degradation past ~200 VUs cannot be solved with `--workers N` because that would give each worker a diverging, incorrect graph; state externalization is required first and is out of scope for this session. Also flagged, not yet acted on: pickle trust-boundary hardening (currently no untrusted input reaches the unpickler, but this should remain a stated invariant, not an assumption), and a save→crash→restore parity test for the pickled `LapMemory` state (the existing parity test proves batch-vs-online equivalence, not crash-recovery equivalence).

## 5. Module execution order

`0(done) → 1 → 2 → {3,4,5,6} → {7,8} → 9 → 10 → 11`, per `sleepy-pebble.md`. Module 10 (paper) may
start in parallel with 3–9 since it depends only on committed `results/`/`artifacts/`.
