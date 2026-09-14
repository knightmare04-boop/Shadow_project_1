"""Light hyperparameter search — seeded random search, validation-selected.

Deliberately hand-rolled (no optuna): 20-30 trials is below the regime where
model-based search beats random, a seeded ``default_rng`` makes the whole search
deterministic, and trials serialize to plain JSON.

Honesty properties:
  * Selection reads ONLY validation PR-AUC (rule 5: PR-AUC is the model-selection
    metric). Each trial's test PR-AUC is recorded for post-hoc audit but is never
    consulted by the search.
  * Config #0 of every search is DEFAULT_XGB_PARAMS — the tuned result can never
    lose to the locked baseline configuration on the selection split.
  * Guard: if the validation split holds fewer than ``min_val_frauds`` frauds
    (SAP: 19), the search is skipped and the defaults returned — a 20-fraud val
    split cannot support hyperparameter selection on top of early stopping and
    threshold tuning.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from modeling.harness import DEFAULT_XGB_PARAMS, time_split, train_and_evaluate

log = logging.getLogger(__name__)

# Discrete choices are lists; continuous ranges are ("uniform"|"loguniform", lo, hi).
SEARCH_SPACE = {
    "max_depth":        [3, 4, 6, 8],
    "learning_rate":    ("loguniform", 0.02, 0.15),
    "min_child_weight": [1, 5, 10, 20],
    "subsample":        ("uniform", 0.6, 1.0),
    "colsample_bytree": ("uniform", 0.5, 1.0),
    "reg_lambda":       [0.5, 1.0, 2.0, 5.0],
    "reg_alpha":        [0.0, 0.1, 0.5],
}
FOCAL_GAMMA_SPACE = [1.0, 2.0, 3.0]  # sampled only when imbalance == "focal"


def sample_configs(n: int, seed: int, imbalance: str) -> list[dict]:
    """n configs; #0 is always the locked defaults (gamma 2.0 on the focal arm)."""
    rng = np.random.default_rng(seed)
    configs: list[dict] = [{"xgb_params": dict(DEFAULT_XGB_PARAMS),
                            "focal_gamma": 2.0}]
    while len(configs) < n:
        params = {}
        for key, space in SEARCH_SPACE.items():
            if isinstance(space, list):
                params[key] = space[int(rng.integers(len(space)))]
            else:
                kind, lo, hi = space
                if kind == "loguniform":
                    params[key] = float(np.exp(rng.uniform(np.log(lo), np.log(hi))))
                else:
                    params[key] = float(rng.uniform(lo, hi))
        gamma = (FOCAL_GAMMA_SPACE[int(rng.integers(len(FOCAL_GAMMA_SPACE)))]
                 if imbalance == "focal" else 2.0)
        configs.append({"xgb_params": params, "focal_gamma": gamma})
    return configs


def random_search(df: pd.DataFrame, feature_cols: list[str], *,
                  imbalance: str, partition=None, n_configs: int = 20,
                  screen_seed: int = 42, min_val_frauds: int = 20) -> dict:
    """Single-seed screen: one honest train/val/test run per config, selected on
    validation PR-AUC. Returns the best params + the full trial log."""
    _, val, _ = time_split(df["timestamp"], partition=partition)
    val_frauds = int(df.loc[val, "label"].astype(int).sum())
    if val_frauds < min_val_frauds:
        log.warning("HPO skipped: only %d validation frauds (< %d) — "
                    "returning locked defaults", val_frauds, min_val_frauds)
        return {"hpo_skipped": True, "val_frauds": val_frauds,
                "best_params": dict(DEFAULT_XGB_PARAMS), "best_focal_gamma": 2.0,
                "best_val_pr_auc": None, "n_configs": 0, "trials": []}

    trials = []
    best = None
    for i, cfg in enumerate(sample_configs(n_configs, screen_seed, imbalance)):
        r = train_and_evaluate(df, feature_cols, seed=screen_seed,
                               partition=partition, imbalance=imbalance,
                               focal_gamma=cfg["focal_gamma"],
                               xgb_params=cfg["xgb_params"])
        trial = {"config": cfg["xgb_params"], "focal_gamma": cfg["focal_gamma"],
                 "val_pr_auc": r["val"]["pr_auc"],
                 "test_pr_auc": r["test"]["pr_auc"],  # audit only — never selection
                 "best_iteration": r["best_iteration"]}
        trials.append(trial)
        if best is None or trial["val_pr_auc"] > best["val_pr_auc"]:
            best = trial
        log.info("HPO trial %d/%d (%s): val PR-AUC %.4f (best %.4f)",
                 i + 1, n_configs, imbalance, trial["val_pr_auc"], best["val_pr_auc"])

    return {"hpo_skipped": False, "val_frauds": val_frauds,
            "best_params": best["config"], "best_focal_gamma": best["focal_gamma"],
            "best_val_pr_auc": best["val_pr_auc"], "n_configs": n_configs,
            "selection_metric": "val_pr_auc", "trials": trials}
