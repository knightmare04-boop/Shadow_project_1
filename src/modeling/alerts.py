"""Audit-alert generation — the explainable deliverable (Build Step 5, layer 1).

For the top-k highest-scoring test-period transactions of a persisted model,
produce a two-layer explanation per alert:

  1. WHY the model scored it high — exact TreeSHAP feature attributions
     (modeling/explain.py), tagged by feature family (ordinary / topology / tgn).
  2. WHAT the evidence looks like — the actual suspicious structure from the
     as-of graph (topology/paths.py): the closed cycle's hops, or the fan-in
     senders behind the destination.

Output: results/<dataset>/alerts/alerts.json (machine) + alerts.txt (human).
This layer has ZERO Neo4j dependency — the Neo4j demo (src/graph/) only
*visualizes* what is already in alerts.json.

``ground_truth_label`` is included for research transparency (we know the
labels); a production alert would not have it.

Run:  python -m modeling.alerts ibm_aml [--artifact final] [--k 20]
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import date
from pathlib import Path

import numpy as np
import xgboost as xgb

from features.load import load_model_table, split_partition
from modeling.explain import top_drivers, tree_shap
from modeling.harness import REPO_ROOT, time_split
from modeling.objectives import sigmoid
from modeling.score import load_bundle
from topology.engine import AMOUNT_DERIVED_COLS

log = logging.getLogger(__name__)

# Auditor-facing glosses for the feature families' recurring names.
_GLOSS = {
    "in_cycle": "closes a money loop returning to its origin",
    "cycle_length": "number of hops in the closed loop",
    "in_cycle_ge3": "the loop is 3+ hops (not a simple back-and-forth)",
    "cycle_amount_ratio": "how much of the amount the loop conserves (1 = all)",
    "cycle_time_span": "how fast the loop closed",
    "fan_in": "distinct recent senders into the destination",
    "fan_out": "distinct recent recipients from the source",
    "dest_in_degree": "recent payment volume into the destination",
    "src_out_degree": "recent payment volume out of the source",
    "log_amount": "transaction amount (log scale)",
    "amount_zscore_src": "amount unusualness vs this sender's history",
    "time_since_prev_src": "time since the sender's previous transaction",
    "tgn_edge_expectedness": "how expected this sender->receiver pair is to the "
                             "learned temporal model (low = surprising)",
}


def _gloss(feature: str) -> str:
    if feature in _GLOSS:
        return _GLOSS[feature]
    if feature.startswith(("tgn_s", "tgn_d")):
        return "learned temporal-graph embedding component"
    if feature.startswith("lap_"):
        return "recurrence of near-equal amounts (lapping signature)"
    return ""


def _evidence_block(row, ev: dict | None) -> dict:
    """Resolve the alert's graph evidence, cross-checked against the stored features."""
    if ev is None:
        return {"type": "none", "note": "transaction not found in edge stream"}
    in_cycle = int(row.get("in_cycle", 0) or 0)
    stored_len = int(row.get("cycle_length", 0) or 0)
    if in_cycle and ev.get("cycle_path"):
        path = ev["cycle_path"]
        if stored_len and len(path) != stored_len:
            # The replay found a different loop than the feature pass (should not
            # happen — same BFS); never present unverified evidence.
            return {"type": "cycle", "cycle_length": stored_len, "path_nodes": None,
                    "path_edges": None, "window": ev["window"],
                    "note": f"path not reconstructed (replay length {len(path)} "
                            f"!= stored {stored_len})"}
        nodes = [path[0]["src"]] + [h["dst"] for h in path]
        amts = [h["amount"] for h in path]
        conserved = (min(amts) / max(amts)) if max(amts) > 0 else None
        span = ev["ts"] - min(h["ts"] for h in path)
        return {"type": "cycle", "cycle_length": len(path), "path_nodes": nodes,
                "path_edges": path, "amount_conservation": conserved,
                "time_span": span, "window": ev["window"]}
    if ev.get("fan_in_total", 0) >= 3:
        return {"type": "fan_in", "n_senders": ev["fan_in_total"],
                "senders": ev["fan_in_senders"], "window": ev["window"]}
    return {"type": "none", "note": "no cycle/fan-in structure behind this alert; "
                                    "see risk_drivers"}


def _text(a: dict) -> str:
    head = (f"ALERT {a['rank']} [score {a['score']:.4f}]: "
            f"{a['source_account']} -> {a['dest_account']} "
            f"for {a['amount']:.2f} at t={a['timestamp']}")
    drivers = "; ".join(
        f"{d['feature']}={d['value']} (SHAP {d['shap']:+.2f}, {d['family']}"
        f"{': ' + d['gloss'] if d.get('gloss') else ''})"
        for d in a["risk_drivers"])
    ev = a["graph_evidence"]
    if ev["type"] == "cycle" and ev.get("path_nodes"):
        cons = ev.get("amount_conservation")
        evtxt = (f"Evidence: closes a {ev['cycle_length']}-hop cycle "
                 f"{' -> '.join(ev['path_nodes'])}"
                 + (f", conserving {cons:.0%} of the amount" if cons else "")
                 + (f", within {ev['time_span']} time units." if ev.get("time_span")
                    is not None else "."))
    elif ev["type"] == "fan_in":
        evtxt = (f"Evidence: destination collected from {ev['n_senders']} distinct "
                 f"senders inside the window (mule-collection signature).")
    else:
        evtxt = f"Evidence: {ev.get('note', 'none')}"
    return f"{head}. Drivers: {drivers}. {evtxt}"


def generate_alerts(name: str, *, artifact: str = "final", k: int = 20,
                    top_features: int = 5) -> Path:
    sb = load_bundle(Path("artifacts") / name / artifact)
    df, manifest, tgn_cols = load_model_table(name)
    _, _, test = time_split(df["timestamp"], partition=split_partition(df))
    part = df[test].reset_index(drop=True)

    margin = sb.booster.predict(
        xgb.DMatrix(part[sb.features], feature_names=sb.features),
        output_margin=True, iteration_range=sb.iteration_range)
    scores = sigmoid(np.asarray(margin, dtype=np.float64))
    top_idx = np.argsort(-scores)[:k]
    top = part.iloc[top_idx].reset_index(drop=True)
    top_scores = scores[top_idx]

    families = sb.feature_families or {
        "ordinary": manifest["ordinary_cols"],
        "topology": manifest["topology_cols"],
        "tgn": tgn_cols,
    }
    contribs, _ = tree_shap(sb, top)
    from topology.paths import reconstruct_evidence  # deferred: reads the full edge CSV
    reconstruct = reconstruct_evidence(name, set(top["transaction_id"].astype(str)))

    alerts = []
    for r in range(len(top)):
        row = top.iloc[r]
        tx_id = str(row["transaction_id"])
        ev = reconstruct.get(tx_id)
        drivers = top_drivers(contribs[r], row, sb.features, families,
                              n=top_features)
        for d in drivers:
            # honest family tag (A.4d): amount-derived topology cols are NOT
            # structural evidence and must not read as such in an alert.
            if d["family"] == "topology" and d["feature"] in AMOUNT_DERIVED_COLS:
                d["family"] = "topology-amount-derived"
            g = _gloss(d["feature"])
            if g:
                d["gloss"] = g
        alert = {
            "alert_id": f"{name.upper()}-TEST-{r + 1:04d}",
            "rank": r + 1,
            "transaction_id": tx_id,
            "score": round(float(top_scores[r]), 6),
            "decision": "ALERT" if top_scores[r] >= sb.threshold else "REVIEW",
            "timestamp": (ev or {}).get("ts", float(row["timestamp"])),
            "source_account": (ev or {}).get("src"),
            "dest_account": (ev or {}).get("dst"),
            "amount": (ev or {}).get("amount"),
            "ground_truth_label": int(row["label"]),
            "risk_drivers": drivers,
            "graph_evidence": _evidence_block(row, ev),
        }
        alert["text"] = _text(alert) if alert["amount"] is not None else (
            f"ALERT {r + 1} [score {alert['score']:.4f}]: transaction {tx_id} "
            f"(not found in edge stream)")
        alerts.append(alert)

    out_dir = REPO_ROOT / "results" / name / "alerts"
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated": date.today().isoformat(),
        "dataset": name,
        "artifact": str(Path("artifacts") / name / artifact),
        "threshold": sb.threshold,
        "k": k,
        "n_true_fraud_in_topk": sum(a["ground_truth_label"] for a in alerts),
        "alerts": alerts,
    }
    with open(out_dir / "alerts.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    with open(out_dir / "alerts.txt", "w", encoding="utf-8") as f:
        f.write(f"AUDIT ALERTS - {name} (top {k} test-period scores, "
                f"threshold {sb.threshold:.4f})\n")
        f.write(f"{payload['n_true_fraud_in_topk']}/{k} are labelled fraud "
                f"(research transparency).\n\n")
        for a in alerts:
            f.write(a["text"] + "\n\n")
    log.info("[%s] wrote %d alerts -> %s", name, len(alerts), out_dir)
    return out_dir / "alerts.json"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--artifact", default="final")
    ap.add_argument("--k", type=int, default=20)
    ap.add_argument("--top-features", type=int, default=5)
    a = ap.parse_args()
    path = generate_alerts(a.dataset, artifact=a.artifact, k=a.k,
                           top_features=a.top_features)
    print(f"wrote {path}")
