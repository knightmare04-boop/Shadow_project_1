"""The Temporal Topology Engine — leakage-free, streaming per-transaction features.

This is the heart of the project (Build Step 2). It turns the canonical edge list
into a per-transaction *topology* feature table, computed **as-of** each
transaction's own time so the future can never leak in.

The golden rule (CLAUDE.md rule 4): a transaction's features depend only on
transactions with ``timestamp <= its own``. We realise this *structurally* by
streaming:

    process transactions in (timestamp, transaction_id) order; for each one,
    read its features from the window graph (which holds only past edges), THEN
    add it to the graph and move on.

Because the edge for transaction *i* is inserted only *after* its features are
read, and rows arrive in time order (the ETL sorts by ``timestamp`` with a stable
sort, and ``transaction_id`` is monotonic within a timestamp), a transaction can
see same-day transactions with a *smaller* id but never a larger / later one.
That is the "``<= T``, id-order tie-break" rule decided on 2026-06-29.

Ships the **cycle** and **fan-in** detectors plus structural degrees — the shapes
that match IBM AML's labelled frauds (936 cycles, 783 fan-ins), so the output can
be validated against ground truth. The cycle detector is *discriminative*, not just
membership: besides ``in_cycle`` / ``cycle_length`` it reports **amount-conservation**
(``cycle_amount_ratio``) and **tightness** (``cycle_time_span``) around the closed
loop, which separate benign reciprocal pairs (a sale + a small refund) from
laundering / wash trades (the same amount returning fast).

Also ships a **lapping** detector (``lap_*``): per-account rolling memory of recent
near-equal amounts and how many *distinct* counterparties they came from — a
"robbing Peter to pay Paul" signature. Unlike the cycle / fan-in detectors it does
NOT use the graph window; it uses cheap count-based per-account memory (see
``lap_memory.LapMemory`` and PROJECT_OVERVIEW A.8 rule 1). Rapid chain / real
centrality follow in the next increment.

Output: ``data/processed/<dataset>/features_topology.csv`` — keyed by
``transaction_id``, topology columns only, kept separable from ordinary features
so the ablation can switch them on and off.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from common.config import get_dataset
from topology.lap_memory import LapMemory
from topology.window_graph import WindowGraph

log = logging.getLogger(__name__)

# Topology feature columns this increment produces (besides transaction_id).
FEATURE_COLS = (
    "in_cycle",            # 1 if this transaction closes a directed cycle within the window
    "cycle_length",        # length (edges) of the shortest such cycle, else 0
    "in_cycle_ge3",        # 1 if that shortest cycle has length >= 3 (excludes self-loops + reciprocal pairs)
    "cycle_amount_ratio",  # min/max amount around the loop (~1 => conserved => laundering); NaN if no cycle
    "cycle_time_span",     # closing ts - earliest loop edge ts (small => tight => suspicious); NaN if no cycle
    "fan_in",              # distinct accounts that sent to the dest in the window (past only)
    "fan_out",             # distinct accounts the source sent to in the window (past only)
    "dest_in_degree",      # total in-edges to the dest in the window (with multiplicity)
    "src_out_degree",      # total out-edges from the source in the window (with multiplicity)
    # --- lapping (per-account rolling memory; NOT the graph window — A.8 rule 1) ---
    "lap_in_recur",        # # of dest's recent INCOMING amounts within tol of this amount (past only)
    "lap_in_payers",       # distinct senders among those near-equal incoming amounts (lapping vs recurring-billing)
    "lap_out_recur",       # # of source's recent OUTGOING amounts within tol of this amount (past only)
    "lap_out_payees",      # distinct recipients among those near-equal outgoing amounts
)

# Which topology features are AMOUNT-derived (computed from transaction amounts) vs
# pure graph STRUCTURE. This split matters for the ablation: the "amount-blind" probe
# must EXCLUDE amount-derived features, otherwise it silently re-introduces the amount
# signal it means to remove — exactly what made lapping look like a topology win when
# it is really an amount feature (see PROJECT_OVERVIEW A.4d). cycle_time_span is *time*-
# derived, so it counts as structure, not amount.
AMOUNT_DERIVED_COLS = (
    "cycle_amount_ratio",
    "lap_in_recur", "lap_in_payers", "lap_out_recur", "lap_out_payees",
)
STRUCTURE_COLS = tuple(c for c in FEATURE_COLS if c not in AMOUNT_DERIVED_COLS)

# Defaults, overridable per dataset via a `topology:` block in datasets.yaml.
_DEFAULT_MAX_CYCLE_LEN = 6
_DEFAULT_SEARCH_BUDGET = 4000
_DEFAULT_LAP_MEMORY = 25      # per-account rolling history length for the lapping detector
_DEFAULT_LAP_TOL = 0.01       # relative tolerance for "near-equal" amounts (1%)
# Default trailing window by time unit (native units). None => unbounded.
_DEFAULT_WINDOW_BY_UNIT = {
    "day": 7,        # IBM AML / BankSim: a week of trailing history
    "step": 7,       # generic integer step
    "synthetic": None,  # SAP runs are short and reset per run -> unbounded within run
}


def resolve_params(ds: dict) -> dict:
    """Resolve topology parameters for a dataset (config overrides defaults)."""
    topo = dict(ds.get("topology") or {})
    unit = ds.get("time_unit")
    window = topo.get("window", _DEFAULT_WINDOW_BY_UNIT.get(unit, None))
    return {
        "window": window,
        "max_cycle_len": int(topo.get("max_cycle_len", _DEFAULT_MAX_CYCLE_LEN)),
        "search_budget": int(topo.get("search_budget", _DEFAULT_SEARCH_BUDGET)),
        "lap_memory": int(topo.get("lap_memory", _DEFAULT_LAP_MEMORY)),
        "lap_tol": float(topo.get("lap_tol", _DEFAULT_LAP_TOL)),
        "partition_col": ds.get("partition_col"),  # e.g. "run_id" for sap_wurzburg
    }


def extract_features(
    edges: pd.DataFrame,
    *,
    window: int | float | None,
    max_cycle_len: int = _DEFAULT_MAX_CYCLE_LEN,
    search_budget: int = _DEFAULT_SEARCH_BUDGET,
    lap_memory: int = _DEFAULT_LAP_MEMORY,
    lap_tol: float = _DEFAULT_LAP_TOL,
    partition_col: str | None = None,
) -> pd.DataFrame:
    """Compute as-of topology features for an already time-sorted edge table.

    ``edges`` must be sorted by ``timestamp`` (with stable, id-preserving order)
    exactly as the ETL writes it. Returns one row per input transaction with
    ``transaction_id`` + ``FEATURE_COLS``, in the same order as ``edges``.

    If ``partition_col`` is given (e.g. ``run_id``), the window graph is reset at
    every partition boundary so features never cross it — required for SAP
    Würzburg, whose synthetic time axis must not be compared across runs.
    """
    n = len(edges)
    # Factorize the unified account namespace into dense int ids (fast dict keys).
    cat = pd.factorize(
        pd.concat([edges["source_account"], edges["dest_account"]], ignore_index=True)
    )[0]
    src = cat[:n].tolist()
    dst = cat[n:].tolist()
    ts = edges["timestamp"].to_numpy().tolist()
    amt = edges["amount"].to_numpy(dtype=float).tolist()
    if partition_col and partition_col in edges.columns:
        part = edges[partition_col].to_numpy()
    else:
        part = None

    in_cycle = np.zeros(n, dtype=np.int8)
    cycle_length = np.zeros(n, dtype=np.int16)
    in_cycle_ge3 = np.zeros(n, dtype=np.int8)
    cycle_amount_ratio = np.full(n, np.nan, dtype=np.float32)  # NaN where no cycle closes
    cycle_time_span = np.full(n, np.nan, dtype=np.float32)     # NaN where no cycle closes
    fan_in = np.zeros(n, dtype=np.int32)
    fan_out = np.zeros(n, dtype=np.int32)
    dest_in_degree = np.zeros(n, dtype=np.int32)
    src_out_degree = np.zeros(n, dtype=np.int32)
    lap_in_recur = np.zeros(n, dtype=np.int32)
    lap_in_payers = np.zeros(n, dtype=np.int32)
    lap_out_recur = np.zeros(n, dtype=np.int32)
    lap_out_payees = np.zeros(n, dtype=np.int32)

    g = WindowGraph(window)
    in_lap = LapMemory(lap_memory, lap_tol)   # dest's recent INCOMING amounts (per account)
    out_lap = LapMemory(lap_memory, lap_tol)  # source's recent OUTGOING amounts (per account)
    cur_part = None
    for i in range(n):
        if part is not None and part[i] != cur_part:
            g = WindowGraph(window)          # new partition -> fresh graph (no cross-run leak)
            in_lap = LapMemory(lap_memory, lap_tol)   # reset per-account memory too (no cross-run leak)
            out_lap = LapMemory(lap_memory, lap_tol)
            cur_part = part[i]
        t = ts[i]
        u = src[i]
        v = dst[i]
        a = amt[i]
        g.evict(t)

        # --- read features from the PAST-ONLY state (before inserting this edge) ---
        fan_in[i] = g.fan_in(v)
        fan_out[i] = g.fan_out(u)
        dest_in_degree[i] = g.in_degree(v)
        src_out_degree[i] = g.out_degree(u)
        if u == v:
            # self-payment: a degenerate length-1 loop. No multi-edge conservation
            # to measure, and not a "real" (>=3) loop -> leave ratio/span/ge3 alone.
            in_cycle[i] = 1
            cycle_length[i] = 1
        else:
            res = g.cycle_features(v, u, max_cycle_len, search_budget)
            if res is not None:
                length, p_min_amt, p_max_amt, p_min_ts = res
                in_cycle[i] = 1
                cycle_length[i] = length
                if length >= 3:
                    in_cycle_ge3[i] = 1
                lo = a if a < p_min_amt else p_min_amt    # fold in the closing edge
                hi = a if a > p_max_amt else p_max_amt
                if hi > 0:
                    cycle_amount_ratio[i] = lo / hi
                cycle_time_span[i] = t - p_min_ts          # closing ts is the newest

        # --- lapping: recurrence of near-equal amounts in each account's memory ---
        lap_in_recur[i], lap_in_payers[i] = in_lap.recurrence(v, a)
        lap_out_recur[i], lap_out_payees[i] = out_lap.recurrence(u, a)

        g.add(t, u, v, a)            # the transaction joins the graph only now
        in_lap.record(v, a, u)      # ...and its memory (recorded AFTER reading: past-only)
        out_lap.record(u, a, v)

    return pd.DataFrame({
        "transaction_id": edges["transaction_id"].to_numpy(),
        "in_cycle": in_cycle,
        "cycle_length": cycle_length,
        "in_cycle_ge3": in_cycle_ge3,
        "cycle_amount_ratio": cycle_amount_ratio,
        "cycle_time_span": cycle_time_span,
        "fan_in": fan_in,
        "fan_out": fan_out,
        "dest_in_degree": dest_in_degree,
        "src_out_degree": src_out_degree,
        "lap_in_recur": lap_in_recur,
        "lap_in_payers": lap_in_payers,
        "lap_out_recur": lap_out_recur,
        "lap_out_payees": lap_out_payees,
    })


def _round_or_none(x, ndigits: int = 4):
    """Round for the audit JSON, mapping NaN (e.g. a dataset with no cycles) to None."""
    return None if x is None or pd.isna(x) else round(float(x), ndigits)


_LAP_COLS = ("lap_in_recur", "lap_in_payers", "lap_out_recur", "lap_out_payees")


def _lapping_separation(edges: pd.DataFrame, feats: pd.DataFrame) -> dict | None:
    """Quick read on the lapping features: mean per fraud vs background. There is no
    'lapping' ground-truth typology in our datasets, so this is just a directional
    fraud-vs-benign separation — the ablation is the real test of value."""
    if "label" not in edges.columns:
        return None
    lab = edges[["transaction_id", "label"]].merge(
        feats[["transaction_id", *_LAP_COLS]], on="transaction_id", how="left"
    )
    is_fraud = lab["label"].astype(bool)
    if not is_fraud.any():
        return None
    out = {}
    for c in _LAP_COLS:
        out[c] = {
            "fraud_mean": _round_or_none(lab.loc[is_fraud, c].mean()),
            "background_mean": _round_or_none(lab.loc[~is_fraud, c].mean()),
        }
    return out


def _validate_against_truth(edges: pd.DataFrame, feats: pd.DataFrame) -> dict | None:
    """When a dataset carries ground-truth shape labels (IBM AML's ``alert_type`` /
    ``alert_id``), measure whether the cycle detector actually fires on the known
    fraud cycles. We do NOT measure precision against fraud — most cycles in a
    real ledger are benign — only *recall over labelled cycle alerts* and the
    *enrichment* of ``in_cycle`` among cycle-frauds vs. the background.
    """
    if "alert_type" not in edges.columns:
        return None
    cols = ["transaction_id", "in_cycle", "in_cycle_ge3",
            "cycle_amount_ratio", "cycle_time_span"]
    df = edges[["transaction_id", "label", "alert_type"]].merge(
        feats[cols], on="transaction_id", how="left"
    )
    is_cycle_fraud = df["alert_type"].astype(str).str.lower().eq("cycle")
    n_cycle_fraud = int(is_cycle_fraud.sum())
    if n_cycle_fraud == 0:
        return None
    is_bg = ~df["label"].astype(bool)

    bg_rate = float(df.loc[is_bg, "in_cycle"].mean())
    cyc_rate = float(df.loc[is_cycle_fraud, "in_cycle"].mean())
    out = {
        "n_cycle_fraud_txns": n_cycle_fraud,
        "in_cycle_rate_background": round(bg_rate, 6),
        "in_cycle_rate_cycle_fraud": round(cyc_rate, 6),
        "cycle_enrichment_lift": round(cyc_rate / bg_rate, 2) if bg_rate else None,
    }

    # Do the DISCRIMINATIVE cycle features separate cycle-fraud from *benign* cycles?
    # Compare only among rows that actually closed a cycle (in_cycle == 1) — this is
    # the question raw membership couldn't answer (background in_cycle rate is high).
    icy = df["in_cycle"] == 1
    bg_cyc = icy & is_bg
    fr_cyc = icy & is_cycle_fraud

    def _mean(mask, col):
        s = df.loc[mask, col]
        return round(float(s.mean()), 4) if len(s) and s.notna().any() else None

    out["among_cycles"] = {
        "n_background_cycles": int(bg_cyc.sum()),
        "n_cycle_fraud_cycles": int(fr_cyc.sum()),
        "amount_ratio_background": _mean(bg_cyc, "cycle_amount_ratio"),
        "amount_ratio_cycle_fraud": _mean(fr_cyc, "cycle_amount_ratio"),
        "time_span_background": _mean(bg_cyc, "cycle_time_span"),
        "time_span_cycle_fraud": _mean(fr_cyc, "cycle_time_span"),
        "ge3_rate_background": _mean(bg_cyc, "in_cycle_ge3"),
        "ge3_rate_cycle_fraud": _mean(fr_cyc, "in_cycle_ge3"),
    }
    # Recall over *distinct* cycle alerts: did we flag >=1 closer per alert group?
    if "alert_id" in edges.columns:
        a = edges[["transaction_id", "alert_type", "alert_id"]].merge(
            feats[["transaction_id", "in_cycle"]], on="transaction_id", how="left"
        )
        a = a[a["alert_type"].astype(str).str.lower().eq("cycle")]
        per_alert = a.groupby("alert_id")["in_cycle"].max()
        out["n_cycle_alerts"] = int(per_alert.size)
        out["cycle_alerts_recovered"] = int((per_alert > 0).sum())
        out["cycle_alert_recall"] = round(float((per_alert > 0).mean()), 4)
    return out


def build_topology(name: str, config_path: str | None = None) -> dict:
    """Run the topology engine for one dataset and write the feature table + audit."""
    ds = get_dataset(name, config_path)
    out_dir = Path(ds["processed_dir"])
    edges_path = out_dir / "edges_transactions.csv"
    if not edges_path.exists():
        raise FileNotFoundError(f"{edges_path} not found — run `python -m etl.build {name}` first")

    params = resolve_params(ds)
    log.info("[%s] topology params: %s", name, params)
    edges = pd.read_csv(edges_path, low_memory=False)

    feats = extract_features(
        edges,
        window=params["window"],
        max_cycle_len=params["max_cycle_len"],
        search_budget=params["search_budget"],
        lap_memory=params["lap_memory"],
        lap_tol=params["lap_tol"],
        partition_col=params["partition_col"],
    )
    feats.to_csv(out_dir / "features_topology.csv", index=False)

    audit = {
        "dataset": name,
        "params": params,
        "n_transactions": int(len(feats)),
        "n_in_cycle": int(feats["in_cycle"].sum()),
        "n_in_cycle_ge3": int(feats["in_cycle_ge3"].sum()),
        "cycle_length_counts": feats.loc[feats["in_cycle"] == 1, "cycle_length"]
            .value_counts().sort_index().to_dict(),
        "cycle_amount_ratio_p50": _round_or_none(feats["cycle_amount_ratio"].median()),
        "cycle_amount_ratio_p90": _round_or_none(feats["cycle_amount_ratio"].quantile(0.90)),
        "fan_in_max": int(feats["fan_in"].max()),
        "fan_in_p99": float(np.percentile(feats["fan_in"], 99)),
        "lap_in_payers_max": int(feats["lap_in_payers"].max()),
        "lapping_separation": _lapping_separation(edges, feats),
        "validation": _validate_against_truth(edges, feats),
    }
    with open(out_dir / "topology_audit.json", "w", encoding="utf-8") as f:
        json.dump(audit, f, indent=2, default=str)
    log.info("[%s] wrote %d topology rows -> %s", name, len(feats), out_dir)
    return audit


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    target = sys.argv[1] if len(sys.argv) > 1 else "ibm_aml"
    print(json.dumps(build_topology(target), indent=2, default=str))
