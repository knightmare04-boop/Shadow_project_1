"""Harvest every number the paper cites from results/**/*.json and
artifacts/**/bundle.json into clean, paper-ready JSON files under
paper/data/. Every table in the paper is generated FROM these files, never
retyped by hand — the metric inventory is far too large (~22 tables) to
transcribe safely, and this is the single source of truth a reviewer (or
the LLM council) can audit against the raw results files directly.

Also resolves the three reconciliation notes found during planning:
  1. sap_wurzburg's split sizes differ between ablation.json/augmentation.json
     (partition-aware, 120411/40137/40139) and final.json/modern.json
     (120341/40114/40116) — both are recorded, labeled by source file.
  2. banksim's "baseline" differs between final_table.md (modern.json's
     3-seed A_cw, 0.7870) and ablation.json's single-seed baseline (0.83298)
     — both are recorded, labeled.
  3. artifact_dir fields point at a foreign machine's absolute path — never
     surfaced in harvested output.

Run:  python paper/harvest.py
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS = REPO_ROOT / "results"
ARTIFACTS = REPO_ROOT / "artifacts"
OUT = REPO_ROOT / "paper" / "data"

DATASETS = ["banksim", "ibm_aml", "sap_wurzburg", "synth_erp"]  # the 4 with committed champion results
ONLINE_DATASETS = ["banksim", "sap_wurzburg", "synth_erp", "ibm_aml_kaggle"]  # Module 5's online bundles


def _load(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def harvest_ablation() -> dict:
    """The central claim — all 7 arms x 4 datasets, plus the 4 lift statistics."""
    out = {}
    for ds in DATASETS:
        data = _load(RESULTS / ds / "ablation.json")
        if data is None:
            continue
        s = data["summary"]
        out[ds] = {
            "split_sizes": s["split_sizes"],
            "split_frauds": s["split_frauds"],
            "partition_aware_split": s.get("partition_aware_split", False),
            "pr_auc": s["pr_auc"],
            "marginal_topology_lift": s["marginal_topology_lift"],
            "marginal_structure_lift": s["marginal_structure_lift"],
            "amount_blind_topology_lift": s["amount_blind_topology_lift"],
            "amount_blind_structure_lift": s["amount_blind_structure_lift"],
            "topology_importance": s["topology_importance"],
            "verdict": s["verdict"],
            "arms_detail": {
                arm: {
                    "n_features": data[arm]["n_features"],
                    "test": data[arm]["test"],
                    "val": data[arm].get("val", {}),
                }
                for arm in ("baseline_full", "topology_full", "structure_full", "no_amount_full",
                           "no_amount_topo_full", "no_amount_structure_full", "topo_only_full")
                if arm in data
            },
        }
    return out


def harvest_final_champions() -> dict:
    """3-seed champion selection: banksim/ibm_aml/sap_wurzburg/synth_erp."""
    out = {}
    for ds in DATASETS:
        data = _load(RESULTS / ds / "final.json")
        if data is None:
            continue
        out[ds] = {
            "seeds": data["seeds"],
            "n_features": data["n_features"],
            "feature_families": data["feature_families"],
            "selection": data["selection"],
            "champion": data["champion"],
            "arms_summary": {
                arm: {k: v for k, v in data["arms"][arm].items() if k != "per_seed"}
                for arm in data["arms"]
            },
            "caveats": data.get("caveats", []),
            "shap_global_top20": data.get("shap_global_top20", {}),
            "shap_sample_rows": data.get("shap_sample_rows"),
        }
    return out


def harvest_modern() -> dict:
    """The modernization study — 6 arms x 3 seeds, focal vs class-weight, TGN."""
    out = {}
    for ds in DATASETS:
        data = _load(RESULTS / ds / "modern.json")
        if data is None:
            continue
        s = data["summary"]
        out[ds] = {
            "seeds": s["seeds"],
            "test_pr_auc": s["test_pr_auc"],
            "focal_vs_class_weight_baseline": s.get("focal_vs_class_weight_baseline"),
            "focal_vs_class_weight_topology": s.get("focal_vs_class_weight_topology"),
            "tgn_lift_over_baseline": s.get("tgn_lift_over_baseline"),
            "tgn_vs_handcrafted_topology": s.get("tgn_vs_handcrafted_topology"),
            "combined_vs_topology": s.get("combined_vs_topology"),
            "tgn_importance_share": s.get("tgn_importance_share"),
            "arms_summary": {
                arm: {k: v for k, v in data["arms"][arm].items() if k != "per_seed"}
                for arm in data["arms"]
            },
        }
    return out


def harvest_augmentation() -> dict:
    out = {}
    for ds in ("banksim", "ibm_aml", "sap_wurzburg"):  # synth_erp has no augmentation.json (it's the donor)
        data = _load(RESULTS / ds / "augmentation.json")
        if data is None:
            continue
        out[ds] = {
            "donor": data["donor"], "seeds": data["seeds"],
            "split_sizes": data["split_sizes"], "test_frauds": data.get("test_frauds"),
            "pr_auc": data["pr_auc"],
            "precision_at_100": data.get("precision_at_100"),
            "recall_at_1000": data.get("recall_at_1000"),
            "augmentation_delta_pr_auc": data["augmentation_delta_pr_auc"],
            "verdict": data.get("verdict"),
        }
    return out


def harvest_alerts() -> dict:
    out = {}
    for ds in DATASETS:
        data = _load(RESULTS / ds / "alerts" / "alerts.json")
        if data is None:
            continue
        alerts = data.get("alerts", [])
        evidence_types = {}
        for a in alerts:
            t = a.get("graph_evidence", {}).get("type", "none")
            evidence_types[t] = evidence_types.get(t, 0) + 1
        out[ds] = {
            "threshold": data["threshold"], "k": data["k"],
            "n_true_fraud_in_topk": data["n_true_fraud_in_topk"],
            "precision_at_k": round(data["n_true_fraud_in_topk"] / data["k"], 4) if data["k"] else None,
            "evidence_type_counts": evidence_types,
            "score_range": [min(a["score"] for a in alerts), max(a["score"] for a in alerts)] if alerts else None,
        }
    return out


def harvest_synth_erp_realism() -> dict | None:
    return _load(RESULTS / "synth_erp" / "realism_report.json")


def harvest_calibration_reference() -> dict | None:
    return _load(RESULTS / "synth_erp" / "calibration_reference.json")


def harvest_online_bundles() -> dict:
    """Module 5's serving-tier bundles — the app's actual live scorer."""
    out = {}
    for ds in ONLINE_DATASETS:
        data = _load(RESULTS / ds / "online.json")
        if data is None:
            continue
        out[ds] = {
            "seeds": data.get("seeds"), "n_features": data.get("n_features"),
            "test_pr_auc_mean": data.get("test_pr_auc_mean"), "test_pr_auc_std": data.get("test_pr_auc_std"),
            "test_precision@100_mean": data.get("test_precision@100_mean"),
        }
    return out


def harvest_bundle_metadata() -> dict:
    """Small, safe subset of every artifact bundle — excludes artifact_dir
    (points at a foreign machine, see module docstring) and raw model params
    beyond what's citable."""
    out = {}
    for ds in DATASETS:
        out[ds] = {}
        for config in ("baseline", "topology", "final", "final_class_weight", "final_focal"):
            b = _load(ARTIFACTS / ds / config / "bundle.json")
            if b is None:
                continue
            out[ds][config] = {
                "schema_version": b.get("schema_version"),
                "threshold": b.get("threshold"),
                "n_features": len(b.get("features", [])),
                "imbalance": b.get("imbalance"),
                "score_fn": b.get("score_fn"),
                "best_iteration": b.get("best_iteration"),
                "metrics": b.get("metrics"),
                "selection": b.get("selection"),
            }
    return out


def harvest_final_table_md() -> str:
    p = RESULTS / "final_table.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "ablation": harvest_ablation(),
        "final_champions": harvest_final_champions(),
        "modern": harvest_modern(),
        "augmentation": harvest_augmentation(),
        "alerts": harvest_alerts(),
        "synth_erp_realism": harvest_synth_erp_realism(),
        "calibration_reference": harvest_calibration_reference(),
        "online_bundles": harvest_online_bundles(),
        "bundle_metadata": harvest_bundle_metadata(),
    }
    for name, data in artifacts.items():
        (OUT / f"{name}.json").write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        print(f"wrote paper/data/{name}.json")

    (OUT / "final_table.md").write_text(harvest_final_table_md(), encoding="utf-8")
    print("wrote paper/data/final_table.md")


if __name__ == "__main__":
    main()
