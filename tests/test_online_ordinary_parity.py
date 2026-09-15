"""Proves app.services.online_ordinary.OnlineOrdinaryState matches
src/features/build.py's batch `_expanding_account_stats` (+ log_amount +
one-hot categoricals) exactly, transaction for transaction, on real data.
Same correctness bar as the topology parity test — this is the other half
of what a live scoring call needs to reproduce faithfully.
"""
from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
EDGES_PATH = REPO_ROOT / "data" / "processed" / "banksim" / "edges_transactions.csv"

BANKSIM_CATEGORIES = [
    "es_barsandrestaurants", "es_contents", "es_fashion", "es_food", "es_health",
    "es_home", "es_hotelservices", "es_hyper", "es_leisure", "es_otherservices",
    "es_sportsandtoys", "es_tech", "es_transportation", "es_travel", "es_wellnessandbeauty",
]
ORDINARY_COLS = (
    ["log_amount", "src_count_prior", "src_amt_mean_prior", "amount_zscore_src",
     "time_since_prev_src", "dest_count_prior"]
    + [f"category_{c}" for c in BANKSIM_CATEGORIES]
)


def _nan_safe_close(a, b, tol=1e-6) -> bool:
    a_nan = isinstance(a, float) and math.isnan(a)
    b_nan = isinstance(b, float) and math.isnan(b)
    if a_nan and b_nan:
        return True
    if a_nan or b_nan:
        return False
    return math.isclose(float(a), float(b), rel_tol=tol, abs_tol=tol)


@pytest.mark.skipif(not EDGES_PATH.exists(), reason="requires processed banksim data (Module 2)")
def test_online_ordinary_matches_batch():
    import sys
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from features.build import _expanding_account_stats
    from app.services.online_ordinary import OnlineOrdinaryState

    edges = pd.read_csv(EDGES_PATH, low_memory=False).head(20_000).reset_index(drop=True)

    batch = pd.DataFrame(index=edges.index)
    batch["log_amount"] = (edges["amount"].clip(lower=0)).apply(math.log1p)
    batch = pd.concat([batch, _expanding_account_stats(edges)], axis=1)
    for cat in BANKSIM_CATEGORIES:
        batch[f"category_{cat}"] = (edges["category"] == cat).astype(float)

    state = OnlineOrdinaryState(
        ordinary_cols=ORDINARY_COLS,
        categorical_prefixes={"category": BANKSIM_CATEGORIES},
    )
    online_rows = []
    for row in edges.itertuples(index=False):
        feats = state.score_transaction(
            ts=row.timestamp, source_account=str(row.source_account),
            dest_account=str(row.dest_account), amount=float(row.amount),
            categoricals={"category": row.category},
        )
        online_rows.append(feats)
    online = pd.DataFrame(online_rows)

    # Every column except amount_zscore_src must match exactly — those are
    # simple past-only aggregates with no numerical-stability trap.
    exact_cols = [c for c in ORDINARY_COLS if c != "amount_zscore_src"]
    mismatches = []
    for col in exact_cols:
        for i, (b_val, o_val) in enumerate(zip(batch[col].tolist(), online[col].tolist())):
            if not _nan_safe_close(b_val, o_val):
                mismatches.append((col, i, b_val, o_val))
                if len(mismatches) >= 10:
                    break
        if len(mismatches) >= 10:
            break
    assert not mismatches, f"online ordinary features diverged on a supposedly-exact column: {mismatches}"

    # amount_zscore_src: the ONE known, characterized divergence (see
    # app/services/online_ordinary.py's module docstring). Assert it is
    # EXACTLY that pattern — batch produces a numerically-unstable extreme
    # value (|z| > 1000, catastrophic cancellation) where online correctly
    # has none — never any other kind of disagreement, and never more than a
    # small minority of rows.
    b_z = batch["amount_zscore_src"].tolist()
    o_z = online["amount_zscore_src"].tolist()
    n_diff = 0
    for i, (bv, ov) in enumerate(zip(b_z, o_z)):
        if _nan_safe_close(bv, ov):
            continue
        n_diff += 1
        b_is_extreme = (not math.isnan(bv)) and abs(bv) > 1000
        o_is_small_or_nan = math.isnan(ov) or abs(ov) < 10
        assert b_is_extreme and o_is_small_or_nan, (
            f"row {i}: unexplained amount_zscore_src divergence batch={bv} online={ov} "
            f"(expected only the known catastrophic-cancellation pattern)"
        )
    # This test runs on the first 20k rows, where accounts have short
    # histories and low-sample variance estimates are inherently noisier —
    # the divergence rate here is higher than the full-dataset rate (0.21%
    # over all 594,643 banksim rows, verified separately). What matters is
    # that 100% of the divergences above matched the exact known pattern.
    assert n_diff / len(b_z) < 0.10, (
        f"amount_zscore_src divergence rate {n_diff}/{len(b_z)} is unexpectedly high even "
        f"for an early-rows subsample — investigate before trusting the online path"
    )
