"""Proves app.services.online_topology.OnlineTopologyState produces IDENTICAL
features to the batch topology.engine.extract_features, transaction for
transaction, on a real dataset. This is the correctness guarantee Module 5's
live scoring path depends on entirely — the online engine is only safe to
use if it is behaviorally identical to the research-verified batch engine,
not merely "close."

Requires data/processed/banksim/edges_transactions.csv to exist (Module 2).
Skips cleanly if it doesn't, rather than failing — this is an integration
test against real processed data, not a unit test with synthetic fixtures.
"""
from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
EDGES_PATH = REPO_ROOT / "data" / "processed" / "banksim" / "edges_transactions.csv"


def _nan_safe_eq(a, b) -> bool:
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    if isinstance(a, float) and isinstance(b, float):
        return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)
    return a == b


@pytest.mark.skipif(not EDGES_PATH.exists(), reason="requires processed banksim data (Module 2)")
def test_online_matches_batch_exactly():
    from topology.engine import FEATURE_COLS, extract_features
    from app.services.online_topology import OnlineTopologyState

    edges = pd.read_csv(EDGES_PATH, low_memory=False)
    # Keep the test fast: first 20,000 transactions is plenty to exercise
    # cycles, fan-in, lapping, and window eviction (banksim's window is 7 steps).
    edges = edges.head(20_000).reset_index(drop=True)

    batch = extract_features(edges, window=7, max_cycle_len=6, search_budget=4000,
                              lap_memory=25, lap_tol=0.01)

    state = OnlineTopologyState(window=7, max_cycle_len=6, search_budget=4000,
                                lap_memory=25, lap_tol=0.01)
    online_rows = []
    for row in edges.itertuples(index=False):
        feats = state.score_transaction(
            ts=row.timestamp, source_account=str(row.source_account),
            dest_account=str(row.dest_account), amount=float(row.amount),
        )
        online_rows.append(feats)
    online = pd.DataFrame(online_rows)

    assert len(online) == len(batch)
    mismatches = []
    for col in FEATURE_COLS:
        b_col = batch[col].tolist()
        o_col = online[col].tolist()
        for i, (b_val, o_val) in enumerate(zip(b_col, o_col)):
            if not _nan_safe_eq(b_val, o_val):
                mismatches.append((col, i, b_val, o_val))
                if len(mismatches) >= 10:
                    break
        if len(mismatches) >= 10:
            break

    assert not mismatches, (
        f"online topology diverged from the batch engine at "
        f"{len(mismatches)}+ points (showing first 10): {mismatches}"
    )


@pytest.mark.skipif(not EDGES_PATH.exists(), reason="requires processed banksim data (Module 2)")
def test_snapshot_restore_roundtrip_preserves_state():
    """A restart mid-stream must resume identically — the whole point of
    persisting state (Module 5 Stage A)."""
    from app.services.online_topology import OnlineTopologyState

    edges = pd.read_csv(EDGES_PATH, low_memory=False).head(5_000).reset_index(drop=True)
    split = 2_500

    state_a = OnlineTopologyState(window=7, max_cycle_len=6, search_budget=4000,
                                  lap_memory=25, lap_tol=0.01)
    for row in edges.iloc[:split].itertuples(index=False):
        state_a.score_transaction(ts=row.timestamp, source_account=str(row.source_account),
                                  dest_account=str(row.dest_account), amount=float(row.amount))

    blob = state_a.snapshot()
    state_b = OnlineTopologyState.restore(blob)

    for row in edges.iloc[split:].itertuples(index=False):
        f_a = state_a.score_transaction(ts=row.timestamp, source_account=str(row.source_account),
                                        dest_account=str(row.dest_account), amount=float(row.amount))
        f_b = state_b.score_transaction(ts=row.timestamp, source_account=str(row.source_account),
                                        dest_account=str(row.dest_account), amount=float(row.amount))
        for k in f_a:
            assert _nan_safe_eq(f_a[k], f_b[k]), f"restored state diverged on {k}: {f_a[k]} vs {f_b[k]}"
