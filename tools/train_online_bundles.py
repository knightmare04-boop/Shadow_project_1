"""Module 5, Stage B ("now" path): train a scoring bundle the application can
actually serve online.

The committed champion bundles need 86-99 features including 65 TGN columns,
and `modeling.tgn.build_embeddings` discards its memory tensor after
`fit_transform` — there is no persisted state to extend with one new
transaction, so the champion CANNOT score a single live posting today (see
docs/BUILD_SPEC.md and the plan's Module 5). Separately, Module 2 found TGN
embeddings are not bit-reproducible across machines even with a fixed seed,
so this machine's champion wouldn't score-match the committed one anyway.

This trains on ordinary + hand-crafted topology features ONLY — both are
fully streaming-computable (WindowGraph/LapMemory read-then-insert, already
built for exactly this) with no whole-stream replay needed. On the
project's own ablation (results/<ds>/ablation.json), this is the
"topology" arm: on banksim it scores 0.9319 PR-AUC vs the champion's 0.9364
— a ~0.005 cost for being servable online at all, which the plan flagged
as the expected, acceptable trade.

Writes artifacts/<dataset>/online/{model.json,bundle.json} — same schema-v2
format `modeling.score.load_bundle` already knows how to read, so
score_frame() works against it unmodified.

Run:  python -m tools.train_online_bundles [dataset ...]   # default: all configured
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

log = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_DATASETS = ["banksim", "sap_wurzburg", "synth_erp", "ibm_aml_kaggle"]


def train_online_bundle(name: str, *, seeds=(42, 43, 44)) -> dict:
    from features.load import load_model_table, split_partition
    from modeling.harness import train_and_evaluate_seeds

    df, manifest, _ = load_model_table(name, with_tgn=False)
    feature_cols = manifest["ordinary_cols"] + manifest["topology_cols"]
    partition = split_partition(df)

    summary = train_and_evaluate_seeds(
        df, feature_cols, seeds=seeds, persist_as=f"{name}/online",
        partition=partition, imbalance="class_weight",
        bundle_extra={
            "dataset": name,
            "serving_tier": "online",
            # modeling.explain.feature_family(feature, families) does
            # `feature in cols` per family — these MUST be the actual
            # feature-name lists, not counts (counts silently break SHAP
            # driver labeling with "argument of type 'int' is not iterable").
            "feature_families": {"ordinary": manifest["ordinary_cols"],
                                  "topology": manifest["topology_cols"], "tgn": []},
            "note_serving": (
                "Ordinary+topology only, no TGN — fully streaming-computable, "
                "servable against one live transaction. See tools/train_online_bundles.py."
            ),
        },
    )

    out_dir = REPO_ROOT / "results" / name
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "online.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)

    log.info("[%s] online bundle: test PR-AUC %.4f +- %.4f (n_features=%d)",
              name, summary["test_pr_auc_mean"], summary["test_pr_auc_std"], summary["n_features"])
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("datasets", nargs="*", default=DEFAULT_DATASETS)
    a = ap.parse_args()

    results = {}
    for ds in a.datasets:
        try:
            results[ds] = train_online_bundle(ds)
        except FileNotFoundError as exc:
            log.warning("[%s] skipped: %s", ds, exc)

    print(json.dumps(
        {k: {"test_pr_auc_mean": v["test_pr_auc_mean"], "test_pr_auc_std": v["test_pr_auc_std"]}
         for k, v in results.items()},
        indent=2,
    ))
