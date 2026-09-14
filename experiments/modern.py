"""The modernization experiment — champion–challenger under the honest protocol.

Extends the locked ablation (experiments/ablation.py, untouched) with the two
modernization arms, everything else held identical (same chronological split,
same threshold discipline, same PR-AUC-first metrics, ONE imbalance mechanism
per arm, multi-seed mean ± std):

  imbalance mechanism comparison (rule 1 — one at a time, both recorded):
    A_cw     baseline tabular, class weight        (the locked champion)
    A_focal  baseline tabular, focal loss (γ=2)
    B_cw     + hand-crafted topology, class weight (the current thesis model)
    B_focal  + hand-crafted topology, focal loss
  learned-structure challenger (TGN embeddings: label-free, amount-blind,
  zero-lookahead — see modeling/tgn.py):
    C_tgn    baseline + TGN embeddings
    D_both   baseline + topology + TGN embeddings

The scientific questions, in order:  does focal loss beat class weighting?
does learned temporal-graph structure (C) beat engineered structure (B)?
are they complementary (D > B)?  We report whichever way it lands.

Run:  python -m experiments.modern banksim [--seeds 42 43 44] [--tgn-epochs 3]
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from features.load import load_model_table, split_partition
from modeling.harness import train_and_evaluate_seeds

log = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[1]


def run_modern(name: str, seeds=(42, 43, 44), tgn_epochs: int = 3) -> dict:
    df, manifest, tgn_cols = load_model_table(name, tgn_epochs=tgn_epochs)
    ordinary = manifest["ordinary_cols"]
    topology = manifest["topology_cols"]
    partition = split_partition(df)
    kw = {"seeds": tuple(seeds), "partition": partition}

    arms = {
        "A_cw":    dict(cols=ordinary,                        imbalance="class_weight"),
        "A_focal": dict(cols=ordinary,                        imbalance="focal"),
        "B_cw":    dict(cols=ordinary + topology,             imbalance="class_weight"),
        "B_focal": dict(cols=ordinary + topology,             imbalance="focal"),
        "C_tgn":   dict(cols=ordinary + tgn_cols,             imbalance="class_weight"),
        "D_both":  dict(cols=ordinary + topology + tgn_cols,  imbalance="class_weight"),
    }
    results = {}
    for arm, spec in arms.items():
        log.info("[%s] arm %s — %d features, %s, %d seeds",
                 name, arm, len(spec["cols"]), spec["imbalance"], len(seeds))
        results[arm] = train_and_evaluate_seeds(
            df, spec["cols"], imbalance=spec["imbalance"], **kw)

    pr = lambda a: results[a]["test_pr_auc_mean"]
    sd = lambda a: results[a]["test_pr_auc_std"]
    summary = {
        "dataset": name,
        "seeds": list(seeds),
        "split_frauds": results["A_cw"]["split_frauds"],
        "test_pr_auc": {a: {"mean": pr(a), "std": sd(a)} for a in arms},
        "focal_vs_class_weight_baseline": round(pr("A_focal") - pr("A_cw"), 5),
        "focal_vs_class_weight_topology": round(pr("B_focal") - pr("B_cw"), 5),
        "tgn_lift_over_baseline": round(pr("C_tgn") - pr("A_cw"), 5),
        "tgn_vs_handcrafted_topology": round(pr("C_tgn") - pr("B_cw"), 5),
        "combined_vs_topology": round(pr("D_both") - pr("B_cw"), 5),
        "tgn_importance_share": _tgn_importance_share(results["D_both"], tgn_cols),
    }
    out_dir = REPO_ROOT / "results" / name
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "modern.json", "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "arms": results}, f, indent=2)
    return summary


def _tgn_importance_share(arm_result: dict, tgn_cols: list[str]) -> float:
    """Fraction of total feature importance carried by embedding columns in the
    combined model (first seed's model) — a coarse 'did the trees even use it'."""
    imp = arm_result["per_seed"][0]["feature_importance"]
    total = sum(imp.values()) or 1.0
    return round(sum(v for k, v in imp.items() if k in tgn_cols) / total, 4)


def _print(s: dict) -> None:
    print("\n" + "=" * 70)
    print(f"MODERNIZATION — {s['dataset']}   (test frauds: {s['split_frauds']['test']}, "
          f"seeds: {s['seeds']})")
    print("=" * 70)
    print(f"{'arm':<10}{'features':<34}{'test PR-AUC (mean ± std)':>26}")
    label = {
        "A_cw": "tabular, class-weight", "A_focal": "tabular, focal",
        "B_cw": "+topology, class-weight", "B_focal": "+topology, focal",
        "C_tgn": "+TGN embeddings, class-weight", "D_both": "+topology+TGN, class-weight",
    }
    for a, v in s["test_pr_auc"].items():
        print(f"{a:<10}{label[a]:<34}{v['mean']:>16.4f} ± {v['std']:.4f}")
    print("-" * 70)
    print(f"  focal vs class-weight (baseline)   : {s['focal_vs_class_weight_baseline']:+.4f}")
    print(f"  focal vs class-weight (+topology)  : {s['focal_vs_class_weight_topology']:+.4f}")
    print(f"  TGN lift over tabular baseline     : {s['tgn_lift_over_baseline']:+.4f}")
    print(f"  TGN vs hand-crafted topology       : {s['tgn_vs_handcrafted_topology']:+.4f}")
    print(f"  combined vs topology (complement?) : {s['combined_vs_topology']:+.4f}")
    print(f"  TGN importance share in combined   : {s['tgn_importance_share']:.1%}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44])
    ap.add_argument("--tgn-epochs", type=int, default=3)
    a = ap.parse_args()
    _print(run_modern(a.dataset, seeds=tuple(a.seeds), tgn_epochs=a.tgn_epochs))
