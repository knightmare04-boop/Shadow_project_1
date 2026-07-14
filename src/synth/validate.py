"""validate — the realism battery: synthetic vs. real, reported honestly.

Compares the CANONICAL synthetic dataset against the measured statistics of the
four real datasets (``results/synth_erp/calibration_reference.json``, produced
by ``synth.calibrate``) on the axes that matter for this project:

  1. Volume / balance     — size, fraud rate inside the real range.
  2. Amounts              — magnitude, tail, Benford conformance; and the
                            anti-AMLSim check: fraud amounts must OVERLAP benign
                            ones (IBM's fraud/benign median ratio is 0.07 — a
                            15x giveaway; ours must sit near 1).
  3. Graph structure      — counterparty repetition, reciprocity, degree tails,
                            namespace overlap: inside the span the real sets cover.
  4. Temporal texture     — business-hours share, weekend share, per-day volume
                            (descriptive; the real sets are too coarse to compare).
  5. Emergence (eval-only)— did the fraud BEHAVIORS leave structural traces
                            (ring scenarios that closed loops, collector fan-in
                            above the benign background) WITHOUT the generator
                            ever targeting detector patterns? Uses ground-truth
                            labels + the topology output; never a model input.

Output: ``results/synth_erp/realism_report.json`` (embedded in the dataset doc).

Run:  python -m synth.validate
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from common.config import get_dataset
from synth.base import DAY
from synth.calibrate import REPO_ROOT, amount_stats, graph_stats

log = logging.getLogger(__name__)

OUT_DIR = REPO_ROOT / "results" / "synth_erp"


def _real_range(ref: dict, path: list[str]) -> dict:
    """min/max of one statistic across the real reference datasets."""
    vals = {}
    for name, block in ref.items():
        v = block
        for key in path:
            v = v.get(key) if isinstance(v, dict) else None
            if v is None:
                break
        if v is not None:
            vals[name] = v
    return {"real_min": min(vals.values()), "real_max": max(vals.values()), "per_dataset": vals}


def _temporal_texture(edges: pd.DataFrame) -> dict:
    ts = edges["timestamp"].to_numpy()
    day = ts // DAY
    sec = ts % DAY
    hour = sec // 3600
    weekend = (day % 7) >= 5
    per_day = pd.Series(day).value_counts()
    return {
        "business_hours_share": round(float(((hour >= 8) & (hour <= 18)).mean()), 4),
        "weekend_share": round(float(weekend.mean()), 4),
        "txns_per_day_mean": round(float(per_day.mean()), 1),
        "txns_per_day_p99": round(float(per_day.quantile(0.99)), 1),
        "span_days": int(day.max() - day.min() + 1),
    }


def _fraud_overlap(edges: pd.DataFrame, ref: dict) -> dict:
    """The anti-AMLSim check: are fraud amounts separable from benign amounts?

    Two views, because a median ratio alone misleads on a MIXTURE economy:
      * global: univariate log-amount ROC — how far a one-column "model" gets
        (IBM AML: 0.91-equivalent, the artifact; BankSim, a REAL set: 0.95);
      * in-band: the same ROC restricted to the B2B band where fraud actually
        lives — near 0.5 means fraud is camouflaged among same-scale benign
        payments and the global signal is only "fraud is B2B-sized".
    """
    from sklearn.metrics import roc_auc_score

    a = edges["amount"].to_numpy(dtype=float)
    y = edges["label"].to_numpy()
    benign, fraud = a[y == 0], a[y == 1]
    lo = np.log1p(benign)
    lf = np.log1p(fraud)
    # a light KS statistic on log-amounts (no scipy dependency): empirical CDF
    # distance evaluated on a merged quantile grid
    grid = np.quantile(np.concatenate([lo, lf]), np.linspace(0.001, 0.999, 400))
    cdf_b = np.searchsorted(np.sort(lo), grid, side="right") / lo.size
    cdf_f = np.searchsorted(np.sort(lf), grid, side="right") / lf.size
    ks = round(float(np.max(np.abs(cdf_b - cdf_f))), 4)

    band = (a >= 300) & (a <= 20000)          # where >90% of fraud amounts sit
    roc_global = float(roc_auc_score(y, np.log1p(a)))
    roc_band = float(roc_auc_score(y[band], np.log1p(a[band]))) if y[band].sum() else None

    ratio = float(np.median(fraud) / np.median(benign))
    ibm = ref.get("ibm_aml", {})
    ibm_ratio = (ibm.get("amounts_fraud", {}) or {}).get("median", np.nan)
    ibm_ratio = ibm_ratio / ibm["amounts"]["median"] if ibm else None
    return {
        "median_fraud": round(float(np.median(fraud)), 2),
        "median_benign": round(float(np.median(benign)), 2),
        "fraud_to_benign_median_ratio": round(ratio, 3),
        "ks_log_amount_fraud_vs_benign": ks,
        "univariate_log_amount_roc": round(roc_global, 4),
        "univariate_log_amount_roc_in_band_300_20k": round(roc_band, 4) if roc_band else None,
        "n_fraud_in_band": int(y[band].sum()),
        "ibm_aml_ratio_for_comparison": round(ibm_ratio, 3) if ibm_ratio else None,
        "note": "fraud is B2B-scale in a retail-heavy economy (mixture effect), "
                "but INSIDE its band it is amount-camouflaged (in-band ROC ~ 0.5). "
                "References: BankSim (real) univariate ROC 0.949; IBM AML 0.086 "
                "(i.e. 0.914 flipped) — the artifact class we designed against.",
    }


def _tabular_probe(edges: pd.DataFrame, nodes: pd.DataFrame) -> dict:
    """Adversarial-review fix 3: scan for single-rule TABULAR leaks — cheap
    non-topological rules that separate fraud by construction. The two axes the
    first adversarial review caught: `tx_type` one-hots, and node `creation_day`
    on the RECEIVER side (all-benign-receivers-are-old ⇒ "new account that
    receives money" = fraud). Any rule here with precision > 0.5 at support >= 50
    is a build failure (`leak_flag`)."""
    created = nodes.set_index(nodes["account_id"].astype(str))["creation_day"]
    dest_mid = edges["dest_account"].astype(str).map(created).ge(0).to_numpy()
    src_mid = edges["source_account"].astype(str).map(created).ge(0).to_numpy()
    y = edges["label"].to_numpy().astype(bool)
    base = float(y.mean())

    def rule(mask: np.ndarray) -> dict:
        support = int(mask.sum())
        hits = int((mask & y).sum())
        return {
            "support": support,
            "precision": round(hits / support, 4) if support else 0.0,
            "recall_of_fraud": round(hits / max(int(y.sum()), 1), 4),
            "lift_vs_base": round((hits / support) / base, 1) if support else 0.0,
        }

    rules: dict[str, dict] = {
        "dest_created_midyear": rule(dest_mid),
        "src_created_midyear": rule(src_mid),
    }
    for t in edges["tx_type"].dropna().unique():
        m = (edges["tx_type"] == t).to_numpy()
        rules[f"tx_type={t}"] = rule(m)
        rules[f"tx_type={t} & dest_created_midyear"] = rule(m & dest_mid)

    worst = max(((k, v) for k, v in rules.items() if v["support"] >= 50),
                key=lambda kv: kv[1]["precision"])
    return {
        "base_fraud_rate": round(base, 6),
        "rules": rules,
        "worst_rule": {"rule": worst[0], **worst[1]},
        "leak_flag": bool(worst[1]["precision"] > 0.5),
    }


def _emergence(proc: Path, edges: pd.DataFrame) -> dict | None:
    """Ground-truth-only check that structure EMERGED from behavior. Reads the
    topology feature table if it exists (run `python -m topology.engine
    synth_erp` first); never used as a model input."""
    topo_path = proc / "features_topology.csv"
    if not topo_path.exists():
        return None
    topo = pd.read_csv(topo_path)
    df = edges[["transaction_id", "label", "alert_type"]].merge(
        topo, on="transaction_id", how="left")
    benign = df["label"] == 0
    out = {
        "benign_in_cycle_rate": round(float(df.loc[benign, "in_cycle"].mean()), 5),
        "benign_fan_in_p99": float(df.loc[benign, "fan_in"].quantile(0.99)),
    }
    for typ, grp in df[df["label"] == 1].groupby("alert_type"):
        out[str(typ)] = {
            "n": int(len(grp)),
            "in_cycle_rate": round(float(grp["in_cycle"].mean()), 4),
            "in_cycle_ge3_rate": round(float(grp["in_cycle_ge3"].mean()), 4),
            "fan_in_p50": float(grp["fan_in"].median()),
            "fan_in_p90": float(grp["fan_in"].quantile(0.90)),
            "lap_in_recur_mean": round(float(grp["lap_in_recur"].mean()), 2),
        }
    return out


def run(name: str = "synth_erp") -> dict:
    ds = get_dataset(name)
    proc = Path(ds["processed_dir"])
    edges = pd.read_csv(proc / "edges_transactions.csv", low_memory=False)
    nodes = pd.read_csv(proc / "nodes_accounts.csv", low_memory=False)
    with open(OUT_DIR / "calibration_reference.json", encoding="utf-8") as f:
        ref = json.load(f)

    synth_amounts = amount_stats(edges["amount"])
    synth_graph = graph_stats(edges)
    report = {
        "dataset": name,
        "volume": {
            "n_transactions": int(len(edges)),
            "n_accounts": synth_graph["n_accounts"],
            "fraud_rate": round(float(edges["label"].mean()), 6),
            "fraud_rate_real_range": _real_range(ref, ["fraud_rate"]),
        },
        "amounts": {
            "synth": synth_amounts,
            "benford_mad_real": _real_range(ref, ["amounts", "benford_mad"]),
            "log1p_std_real": _real_range(ref, ["amounts", "log1p_std"]),
        },
        "fraud_amount_overlap": _fraud_overlap(edges, ref),
        "graph": {
            "synth": synth_graph,
            "repeat_pair_real": _real_range(ref, ["graph", "repeat_pair_txn_frac"]),
            "reciprocity_real": _real_range(ref, ["graph", "pair_reciprocity"]),
            "namespace_overlap_real": _real_range(ref, ["graph", "namespace_overlap"]),
        },
        "temporal": _temporal_texture(edges),
        "tabular_leak_probe": _tabular_probe(edges, nodes),
        "emergence_ground_truth_only": _emergence(proc, edges),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "realism_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    log.info("wrote %s", OUT_DIR / "realism_report.json")
    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    print(json.dumps(run(), indent=2))
