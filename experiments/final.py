"""The FINAL model — TGN embeddings + topology + ordinary features -> XGBoost.

Promotes the best architecture from the modernization experiment (arm D: ordinary
+ hand-crafted topology + TGN embeddings, see results/<ds>/modern.json) to the
project's single production model, under the honest protocol:

  * fixed feature set (the arm-D columns) — the science lives in ablation.py and
    modern.py; this script productizes, it does not re-litigate.
  * BOTH imbalance mechanisms are trained (class weights, focal loss) — each is a
    separate model with exactly ONE mechanism (rule 1) — and the winner is chosen
    on multi-seed mean VALIDATION PR-AUC (never test; rule 5). Both arms' test
    metrics are published for transparency.
  * light HPO (modeling/hpo.py) per mechanism, selected on validation only,
    skipped automatically when the val split holds < 20 frauds (SAP).
  * multi-seed final numbers (mean +- std), champion persisted as a
    self-describing bundle v2 under artifacts/<ds>/final/.
  * global importances for the champion are exact TreeSHAP (mean |SHAP| on a
    validation sample), not gain.

Run:  python -m experiments.final banksim [--seeds 42 43 44] [--n-configs 20]
                                          [--skip-hpo] [--tgn-epochs 3]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import shutil
from pathlib import Path

import numpy as np

from common.config import get_dataset
from features.load import load_model_table, split_partition
from modeling.explain import global_importance
from modeling.harness import DEFAULT_XGB_PARAMS, time_split, train_and_evaluate_seeds
from modeling.hpo import random_search
from modeling.score import load_bundle

log = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[1]

MECHANISMS = ("class_weight", "focal")
SHAP_SAMPLE = 50_000  # val rows used for global TreeSHAP (deterministic subsample)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _caveats(name: str, split_frauds: dict, hpo_skipped: bool) -> list[str]:
    c = []
    if name == "ibm_aml":
        c.append("baseline is amount-saturated (PR-AUC ~1.0): margins here are "
                 "uninformative; see ablation.json amount-blind probes")
    if split_frauds.get("test", 0) < 50:
        c.append(f"only {split_frauds['test']} test frauds - metrics are "
                 "high-variance, treat as inconclusive")
    if hpo_skipped:
        c.append("HPO skipped (validation frauds below guard) - locked default "
                 "hyperparameters used")
    if name == "synth_erp":
        c.append("synthetic dataset - sanity/demo only, NEVER thesis evidence "
                 "(see docs/SYNTHETIC_DATASET.md section 11)")
    return c


def run_final(name: str, seeds=(42, 43, 44), n_configs: int = 20,
              skip_hpo: bool = False, tgn_epochs: int = 3) -> dict:
    df, manifest, tgn_cols = load_model_table(name, tgn_epochs=tgn_epochs)
    ordinary = manifest["ordinary_cols"]
    topology = manifest["topology_cols"]
    cols = ordinary + topology + tgn_cols
    partition = split_partition(df)
    families = {"ordinary": ordinary, "topology": topology, "tgn": tgn_cols}

    proc = Path(get_dataset(name)["processed_dir"])
    tgn_parquet = proc / "features_tgn.parquet"
    with open(proc / "features_tgn_manifest.json", encoding="utf-8") as f:
        tgn_manifest = json.load(f)
    bundle_common = {
        "dataset": name,
        "feature_families": families,
        "split": {"train_frac": 0.6, "val_frac": 0.2, "ts_col": "timestamp",
                  "partition_col": "run_id" if partition is not None else None},
        "data": {"features_manifest": "features_manifest.json",
                 "features_output": manifest["output"],
                 "tgn_parquet": tgn_parquet.name,
                 "tgn_parquet_sha256": _sha256(tgn_parquet),
                 "tgn_manifest": tgn_manifest},
    }

    hpo_out, arms = {}, {}
    for mech in MECHANISMS:
        if skip_hpo:
            hpo = {"hpo_skipped": True, "best_params": dict(DEFAULT_XGB_PARAMS),
                   "best_focal_gamma": 2.0, "best_val_pr_auc": None,
                   "n_configs": 0, "trials": [], "val_frauds": None}
            log.info("[%s] %s: HPO skipped by flag", name, mech)
        else:
            log.info("[%s] %s: HPO screen (%d configs)", name, mech, n_configs)
            hpo = random_search(df, cols, imbalance=mech, partition=partition,
                                n_configs=n_configs)
        hpo_out[mech] = hpo
        log.info("[%s] %s: final multi-seed fit (%d seeds)", name, mech, len(seeds))
        arms[mech] = train_and_evaluate_seeds(
            df, cols, seeds=tuple(seeds), partition=partition, imbalance=mech,
            focal_gamma=hpo["best_focal_gamma"], xgb_params=hpo["best_params"],
            persist_as=f"{name}/final_{mech}", bundle_extra=bundle_common)

    # --- select the winner on multi-seed mean VALIDATION PR-AUC (never test) ---
    val_means = {m: arms[m]["val_pr_auc_mean"] for m in MECHANISMS}
    winner = max(val_means, key=val_means.get)
    val_frauds = arms[winner]["split_frauds"]["val"]
    selection = {
        "metric": "val_pr_auc_mean",
        "candidates": {m: {"mean": arms[m]["val_pr_auc_mean"],
                           "std": arms[m]["val_pr_auc_std"]} for m in MECHANISMS},
        "winner": winner,
        "reliable": val_frauds >= 20,
    }

    # --- promote the winner to artifacts/<name>/final/ with the selection block ---
    src_dir = REPO_ROOT / "artifacts" / name / f"final_{winner}"
    final_dir = REPO_ROOT / "artifacts" / name / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_dir / "model.json", final_dir / "model.json")
    with open(src_dir / "bundle.json", encoding="utf-8") as f:
        bundle = json.load(f)
    bundle["selection"] = selection
    with open(final_dir / "bundle.json", "w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=2)

    # --- champion global importances: exact TreeSHAP on a validation sample ---
    sb = load_bundle(final_dir)
    _, val_mask, _ = time_split(df["timestamp"], partition=partition)
    val_rows = df[val_mask]
    if len(val_rows) > SHAP_SAMPLE:
        idx = np.random.default_rng(0).choice(len(val_rows), SHAP_SAMPLE,
                                              replace=False)
        val_rows = val_rows.iloc[np.sort(idx)]
    shap_top = global_importance(sb, val_rows, top=20)

    hpo_skipped = bool(hpo_out[winner]["hpo_skipped"])
    out = {
        "dataset": name,
        "seeds": list(seeds),
        "n_features": len(cols),
        "feature_families": {k: len(v) for k, v in families.items()},
        "selection": selection,
        "hpo": hpo_out,
        "arms": arms,
        "champion": {
            "imbalance": arms[winner]["imbalance"],
            "xgb_params": arms[winner]["xgb_params"],
            "test_pr_auc": {"mean": arms[winner]["test_pr_auc_mean"],
                            "std": arms[winner]["test_pr_auc_std"]},
            "test_precision@100": {"mean": arms[winner]["test_precision@100_mean"],
                                   "std": arms[winner]["test_precision@100_std"]},
            "artifact_dir": str(final_dir.relative_to(REPO_ROOT)),
        },
        "shap_global_top20": shap_top,
        "shap_sample_rows": int(len(val_rows)),
        "caveats": _caveats(name, arms[winner]["split_frauds"], hpo_skipped),
    }
    out_dir = REPO_ROOT / "results" / name
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "final.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    return out


def _print(s: dict) -> None:
    # ASCII only: cp1252 consoles choke on +-/gamma glyphs.
    print("\n" + "=" * 72)
    print(f"FINAL MODEL - {s['dataset']}   (features: {s['n_features']}, "
          f"seeds: {s['seeds']})")
    print("=" * 72)
    for m, v in s["selection"]["candidates"].items():
        arm = s["arms"][m]
        tag = " <- champion" if m == s["selection"]["winner"] else ""
        print(f"  {m:<14} val PR-AUC {v['mean']:.4f} +- {v['std']:.4f}   "
              f"test {arm['test_pr_auc_mean']:.4f} +- {arm['test_pr_auc_std']:.4f}{tag}")
    print(f"  selection metric: {s['selection']['metric']} "
          f"(reliable: {s['selection']['reliable']})")
    ch = s["champion"]
    print(f"  champion: {ch['imbalance']}  test PR-AUC "
          f"{ch['test_pr_auc']['mean']:.4f} +- {ch['test_pr_auc']['std']:.4f}  "
          f"p@100 {ch['test_precision@100']['mean']:.4f}")
    print(f"  artifact: {ch['artifact_dir']}")
    top5 = list(s["shap_global_top20"].items())[:5]
    print("  top SHAP features: " + ", ".join(f"{k} ({v:.3f})" for k, v in top5))
    for c in s["caveats"]:
        print(f"  CAVEAT: {c}")
    print("=" * 72 + "\n")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44])
    ap.add_argument("--n-configs", type=int, default=20)
    ap.add_argument("--skip-hpo", action="store_true")
    ap.add_argument("--tgn-epochs", type=int, default=3)
    a = ap.parse_args()
    _print(run_final(a.dataset, seeds=tuple(a.seeds), n_configs=a.n_configs,
                     skip_hpo=a.skip_hpo, tgn_epochs=a.tgn_epochs))
