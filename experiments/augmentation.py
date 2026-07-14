"""The augmentation experiment — does SYNTHETIC training data help on REAL data?

The synthetic dataset (`synth_erp`, docs/SYNTHETIC_DATASET.md) is licensed for
one purpose: training/augmentation. This experiment is the measurable version of
"the synthetic data is useful", run under the project's honesty rules and
reported either way:

    Arms (per real dataset, per seed) — identical shared feature space:
      real_only        train = the real train split
      real_plus_synth  train = the real train split + ALL synth_erp rows
      synth_only       train = synth_erp only (zero-shot transfer probe)

Honesty invariants (CLAUDE.md rules 1-5):
  * The real dataset keeps its chronological 60/20/20 split. Validation and test
    are ALWAYS 100% real and strictly later than the real train rows. Synthetic
    rows are appended to TRAIN ONLY — they never enter validation, test, the
    threshold choice, or early stopping (both run on the real validation split).
    Synthetic data is not part of the real timeline, so appending it to train
    leaks nothing about the real future.
  * One imbalance mechanism: `scale_pos_weight` computed on whatever the arm's
    training set is (recorded per arm).
  * Multi-seed (default 3): XGBoost is stochastic and augmentation deltas are
    small; a single-seed delta would be noise (MODERNIZATION_REPORT §1.2).
  * PR-AUC primary + precision@k on the real test set; threshold tuned on the
    real validation split and frozen.

Feature space: datasets differ in one-hots / node attributes, so arms compare on
the INTERSECTION of ordinary columns (the 6 expanding core features) plus the 13
shared topology columns. Time-dimension features are converted to DAYS first —
synth ticks in seconds, IBM/BankSim in days, PaySim in hours — otherwise a tree
just splits the domains apart on units. Graph windows already align at 7 days
for ibm/banksim/synth (PaySim's is 24h — noted if run).

Run:  python -m experiments.augmentation banksim
      python -m experiments.augmentation ibm_aml --seeds 42 43 44
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from common.config import get_dataset
from modeling.harness import _fit_xgb, time_split
from modeling.metrics import evaluate, tune_threshold

log = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[1]

SYNTH = "synth_erp"

# native time unit -> days, per dataset (see module docstring).
TIME_SCALE = {
    "ibm_aml": 1.0,           # day
    "banksim": 1.0,           # step = day
    "paysim": 1.0 / 24.0,     # step = hour
    "sap_wurzburg": 1.0 / 86400.0,  # synthetic seconds-scale axis (within-run)
    SYNTH: 1.0 / 86400.0,     # seconds
}
TIME_COLS = ("time_since_prev_src", "cycle_time_span")


def _load(name: str) -> tuple[pd.DataFrame, dict]:
    proc = Path(get_dataset(name)["processed_dir"])
    with open(proc / "features_manifest.json", encoding="utf-8") as f:
        manifest = json.load(f)
    path = proc / manifest["output"]
    df = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
    scale = TIME_SCALE[name]
    for c in TIME_COLS:
        if c in df.columns:
            df[c] = df[c] * scale
    return df, manifest


def _fit_eval(Xtr, ytr, Xval, yval, Xte, yte, seed: int) -> dict:
    model, spw = _fit_xgb(Xtr, ytr, Xval, yval, seed)
    p_val = model.predict_proba(Xval)[:, 1]
    threshold = tune_threshold(yval, p_val)           # real val only, then frozen
    out = evaluate(yte, model.predict_proba(Xte)[:, 1], threshold)
    out["scale_pos_weight"] = round(spw, 2)
    out["train_rows"] = int(len(Xtr))
    out["train_frauds"] = int(ytr.sum())
    return out


def run_augmentation(name: str, seeds=(42, 43, 44)) -> dict:
    if name == SYNTH:
        raise ValueError("augmentation targets a REAL dataset; synth_erp is the donor")
    real, mreal = _load(name)
    synth, msynth = _load(SYNTH)

    synth_ord = set(msynth["ordinary_cols"])
    shared_ord = [c for c in mreal["ordinary_cols"] if c in synth_ord]
    synth_topo = set(msynth["topology_cols"])
    shared_topo = [c for c in mreal["topology_cols"] if c in synth_topo]
    feats = shared_ord + shared_topo
    log.info("[%s] shared feature space: %d ordinary + %d topology",
             name, len(shared_ord), len(shared_topo))

    partition = real["run_id"] if "run_id" in real.columns else None
    train, val, test = time_split(real["timestamp"], partition=partition)

    X_real = real[feats]
    y_real = real["label"].astype(int).to_numpy()
    X_synth = synth[feats]
    y_synth = synth["label"].astype(int).to_numpy()

    X_aug = pd.concat([X_real[train], X_synth], ignore_index=True)
    y_aug = np.concatenate([y_real[train], y_synth])

    arms = {
        "real_only": (X_real[train], y_real[train]),
        "real_plus_synth": (X_aug, y_aug),
        "synth_only": (X_synth, y_synth),
    }
    per_seed: dict[str, list[dict]] = {a: [] for a in arms}
    for seed in seeds:
        for arm, (Xtr, ytr) in arms.items():
            r = _fit_eval(Xtr, ytr, X_real[val], y_real[val],
                          X_real[test], y_real[test], seed)
            log.info("[%s] seed=%d %-16s test PR-AUC=%.4f", name, seed, arm, r["pr_auc"])
            per_seed[arm].append(r)

    def agg(arm: str, key: str) -> dict:
        vals = np.array([r[key] for r in per_seed[arm]], dtype=float)
        return {"mean": round(float(vals.mean()), 5), "std": round(float(vals.std()), 5)}

    # paired per-seed deltas (same seed, same split -> the honest error bar)
    deltas = np.array([per_seed["real_plus_synth"][i]["pr_auc"] - per_seed["real_only"][i]["pr_auc"]
                       for i in range(len(seeds))])
    summary = {
        "dataset": name,
        "donor": SYNTH,
        "seeds": list(seeds),
        "shared_features": {"ordinary": shared_ord, "topology": shared_topo},
        "split_sizes": {"train": int(train.sum()), "val": int(val.sum()), "test": int(test.sum()),
                        "synth_added_to_train": int(len(X_synth))},
        "test_frauds": int(y_real[test].sum()),
        "pr_auc": {a: agg(a, "pr_auc") for a in arms},
        "precision_at_100": {a: agg(a, "precision@100") for a in arms},
        "recall_at_1000": {a: agg(a, "recall@1000") for a in arms},
        "augmentation_delta_pr_auc": {
            "mean": round(float(deltas.mean()), 5),
            "std": round(float(deltas.std()), 5),
            "per_seed": [round(float(d), 5) for d in deltas],
        },
        "arms_detail": per_seed,
        "verdict": _verdict(deltas, agg("real_only", "pr_auc"), agg("synth_only", "pr_auc"),
                            int(y_real[test].sum())),
    }
    out_dir = REPO_ROOT / "results" / name
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "augmentation.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    return summary


def _verdict(deltas: np.ndarray, base: dict, zero_shot: dict, test_frauds: int) -> str:
    if test_frauds < 20:
        return f"INCONCLUSIVE — only {test_frauds} test frauds."
    m, s = float(deltas.mean()), float(deltas.std())
    if m > 0 and (s == 0 or m > 2 * s):
        head = f"AUGMENTATION HELPS: +{m:.4f} PR-AUC (paired over seeds, std {s:.4f})"
    elif m < 0 and (s == 0 or -m > 2 * s):
        head = f"AUGMENTATION HURTS: {m:.4f} PR-AUC (paired over seeds, std {s:.4f})"
    else:
        head = f"NO RELIABLE EFFECT: {m:+.4f} PR-AUC vs seed noise (std {s:.4f})"
    head += f"; real-only baseline {base['mean']:.4f}±{base['std']:.4f}"
    head += f"; synth-only zero-shot {zero_shot['mean']:.4f} (transfer probe)."
    return head


def _print(s: dict) -> None:
    # ASCII only: Windows consoles default to cp1252, which cannot encode -/+- glyphs
    print("\n" + "=" * 66)
    print(f"AUGMENTATION - {s['dataset']}  (+{s['split_sizes']['synth_added_to_train']:,} synth rows; "
          f"test frauds {s['test_frauds']}; seeds {s['seeds']})")
    print("=" * 66)
    for arm in ("real_only", "real_plus_synth", "synth_only"):
        a = s["pr_auc"][arm]
        p = s["precision_at_100"][arm]
        print(f"    {arm:<18} PR-AUC {a['mean']:.4f} +-{a['std']:.4f}   p@100 {p['mean']:.3f}")
    d = s["augmentation_delta_pr_auc"]
    print("-" * 66)
    print(f"  paired delta (real+synth - real_only): {d['mean']:+.4f} +-{d['std']:.4f}  {d['per_seed']}")
    print("VERDICT:", s["verdict"])
    print("=" * 66 + "\n")


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset", nargs="?", default="banksim")
    ap.add_argument("--seeds", nargs="*", type=int, default=[42, 43, 44])
    args = ap.parse_args()
    _print(run_augmentation(args.dataset, seeds=tuple(args.seeds)))
