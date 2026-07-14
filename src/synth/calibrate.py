"""calibrate — measure reference statistics from the REAL datasets.

The synthetic generator must be *calibrated*, not guessed: its parameters
(amount magnitudes and tails, activity density, counterparty repetition,
graph-degree shape, fraud rate) are anchored to numbers measured here from the
four real canonical datasets. This module is the auditable first stage of the
"verifiable process" — its output JSON is cited by ``docs/SYNTHETIC_DATASET.md``
and consumed by ``synth.validate`` as the comparison baseline.

Everything is computed from the CANONICAL processed files (post-ETL), so the
statistics describe exactly what the downstream pipeline sees.

Run:  python -m synth.calibrate            # writes results/synth_erp/calibration_reference.json
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from common.config import get_dataset

log = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[2]

# Benford's law: expected first-significant-digit frequencies, P(d) = log10(1 + 1/d).
BENFORD_P = np.log10(1 + 1 / np.arange(1, 10))


def first_digit(amounts: np.ndarray) -> np.ndarray:
    """First significant digit (1-9) of each positive amount."""
    a = np.abs(amounts)
    a = a[a > 0]
    # scale each amount into [1, 10) by dividing by 10^floor(log10(a))
    exp = np.floor(np.log10(a))
    lead = (a / np.power(10.0, exp)).astype(int)
    return np.clip(lead, 1, 9)


def benford_mad(amounts: np.ndarray) -> tuple[float, list[float]]:
    """Mean absolute deviation of the observed first-digit distribution from
    Benford's law (Nigrini's MAD statistic), plus the observed distribution."""
    d = first_digit(amounts)
    obs = np.bincount(d, minlength=10)[1:10].astype(float)
    obs = obs / obs.sum() if obs.sum() else obs
    return float(np.abs(obs - BENFORD_P).mean()), [round(float(x), 4) for x in obs]


def amount_stats(amounts: pd.Series) -> dict:
    a = pd.to_numeric(amounts, errors="coerce").dropna().to_numpy(dtype=float)
    pos = a[a > 0]
    logs = np.log1p(pos)
    mad, digits = benford_mad(a)
    return {
        "n": int(a.size),
        "median": round(float(np.median(a)), 2),
        "mean": round(float(a.mean()), 2),
        "p90": round(float(np.percentile(a, 90)), 2),
        "p99": round(float(np.percentile(a, 99)), 2),
        "max": round(float(a.max()), 2),
        "log1p_mean": round(float(logs.mean()), 4),
        "log1p_std": round(float(logs.std()), 4),
        "benford_mad": round(mad, 4),
        "first_digit_dist": digits,
    }


def graph_stats(edges: pd.DataFrame) -> dict:
    """Structure statistics on the canonical edge list (dataset-agnostic)."""
    src = edges["source_account"].astype(str)
    dst = edges["dest_account"].astype(str)
    n = len(edges)

    out_deg = src.value_counts()          # txns sent per source (with multiplicity)
    in_deg = dst.value_counts()
    fan_out = edges.groupby("source_account")["dest_account"].nunique()  # distinct receivers
    fan_in = edges.groupby("dest_account")["source_account"].nunique()   # distinct senders

    # Factorize into integer codes over ONE shared namespace, then pack each
    # (src, dst) pair into a single int. (String-concat keys are unsafe: pandas 3
    # Arrow strings dropped a \x00 separator, silently corrupting pair identity.)
    codes = pd.factorize(pd.concat([src, dst], ignore_index=True))[0]
    n_ids = int(codes.max()) + 1
    s_codes, d_codes = codes[:n], codes[n:]
    pair_ids = s_codes.astype(np.int64) * n_ids + d_codes
    _, pair_counts = np.unique(pair_ids, return_counts=True)
    repeat_frac = float(pair_counts[pair_counts > 1].sum() / n) if n else 0.0

    pair_set = set(np.unique(pair_ids).tolist())
    recip = sum(1 for p in pair_set if (p % n_ids) * n_ids + (p // n_ids) in pair_set)
    reciprocity = recip / len(pair_set) if pair_set else 0.0

    s, r = set(src.unique()), set(dst.unique())

    def _pct(sr: pd.Series) -> dict:
        return {"p50": float(sr.median()), "p99": float(sr.quantile(0.99)), "max": int(sr.max())}

    return {
        "n_transactions": n,
        "n_accounts": int(len(s | r)),
        "namespace_overlap": round(len(s & r) / max(len(s | r), 1), 4),
        "unique_pairs": int(len(pair_set)),
        "repeat_pair_txn_frac": round(repeat_frac, 4),   # share of txns on an already-used (src,dst) pair
        "pair_reciprocity": round(reciprocity, 4),       # share of pairs whose reverse pair also exists
        "out_degree": _pct(out_deg),
        "in_degree": _pct(in_deg),
        "fan_out_distinct": _pct(fan_out),
        "fan_in_distinct": _pct(fan_in),
    }


def temporal_stats(edges: pd.DataFrame, time_unit: str) -> dict:
    ts = pd.to_numeric(edges["timestamp"], errors="coerce").dropna()
    span = float(ts.max() - ts.min())
    per_unit = edges.groupby(edges["timestamp"]).size()
    return {
        "time_unit": time_unit,
        "span_units": span,
        "txns_per_unit_mean": round(float(per_unit.mean()), 1),
        "txns_per_unit_p99": round(float(per_unit.quantile(0.99)), 1),
    }


def calibrate_dataset(name: str) -> dict:
    ds = get_dataset(name)
    proc = Path(ds["processed_dir"])
    log.info("[%s] loading canonical edges", name)
    edges = pd.read_csv(proc / "edges_transactions.csv", low_memory=False)
    out = {
        "kind": ds.get("kind"),
        "fraud_rate": round(float(edges["label"].mean()), 6),
        "n_fraud": int(edges["label"].sum()),
        "amounts": amount_stats(edges["amount"]),
        "amounts_fraud": amount_stats(edges.loc[edges["label"] == 1, "amount"])
        if edges["label"].sum() else None,
        "graph": graph_stats(edges),
        "temporal": temporal_stats(edges, ds.get("time_unit", "?")),
    }
    return out


def run(datasets=("ibm_aml", "banksim", "sap_wurzburg", "paysim")) -> dict:
    ref = {}
    for name in datasets:
        try:
            ref[name] = calibrate_dataset(name)
        except FileNotFoundError as e:  # dataset not built locally -> skip, keep going
            log.warning("[%s] skipped: %s", name, e)
    out_dir = REPO_ROOT / "results" / "synth_erp"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "calibration_reference.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ref, f, indent=2)
    log.info("wrote %s", path)
    return ref


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    r = run()
    print(json.dumps({k: {"fraud_rate": v["fraud_rate"],
                          "amount_median": v["amounts"]["median"],
                          "repeat_pair_frac": v["graph"]["repeat_pair_txn_frac"],
                          "reciprocity": v["graph"]["pair_reciprocity"]}
                      for k, v in r.items()}, indent=2))
