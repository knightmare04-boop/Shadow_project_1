"""Modeling harness — the honest training/evaluation loop (CLAUDE.md rules 1-6).

One function does the whole rigorous pipeline for a given feature set:

    time_split (train=earlier, test=later; never shuffle)
        -> XGBoost with ONE imbalance mechanism (rule 1): class weight
           (scale_pos_weight, the default) OR a focal-loss objective — never both,
           never SMOTE. The mechanism used is recorded in every result/bundle.
        -> early-stop on validation PR-AUC (model selection by PR-AUC, not F1@0.5)
        -> freeze the decision threshold tuned on validation
        -> evaluate on the future test period
        -> persist model + threshold + feature list

The ablation calls this twice (baseline cols, then baseline+topology cols) with an
identical split and config, so the only thing that differs is the feature set.
``train_and_evaluate_seeds`` repeats the pipeline across seeds and reports
mean ± std — required before interpreting small margins (single-seed differences
of ~0.01 PR-AUC are within XGBoost's subsample noise).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from xgboost import XGBClassifier

from modeling.metrics import evaluate, tune_threshold
from modeling.objectives import focal_objective, sigmoid

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]

# The locked default configuration. HPO (modeling/hpo.py) overlays overrides on
# top of this dict — config #0 of every search IS this dict, so a tuned model can
# never lose to the locked baseline on the selection split.
DEFAULT_XGB_PARAMS = dict(
    n_estimators=500,
    max_depth=6,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    min_child_weight=5,
    reg_lambda=1.0,
    reg_alpha=0.0,
)


def time_split(ts: pd.Series, train_frac: float = 0.6, val_frac: float = 0.2,
               partition=None):
    """Chronological split into boolean masks (train, val, test). NO shuffling (rule 3).

    Default: a global day-aligned quantile split (earlier trains, later tests).

    ``partition`` (e.g. SAP's ``run_id``): split *within* each partition by time
    position — each run contributes its early rows to train and its late rows to
    test. Required when the global time axis is synthetic and not a real cross-run
    chronology (SAP's runs are ordered fraud-first/clean-middle, which would put a
    zero-fraud run in validation under a global split)."""
    ts = np.asarray(ts)
    n = len(ts)
    if partition is None:
        t1 = int(np.floor(np.quantile(ts, train_frac)))
        t2 = int(np.floor(np.quantile(ts, train_frac + val_frac)))
        if t2 <= t1:  # degenerate (coarse time axis) -> nudge the val boundary up
            t2 = t1 + 1
        return ts < t1, (ts >= t1) & (ts < t2), ts >= t2

    partition = np.asarray(partition)
    train = np.zeros(n, bool); val = np.zeros(n, bool); test = np.zeros(n, bool)
    for p in pd.unique(partition):
        idx = np.where(partition == p)[0]          # rows are globally time-sorted -> contiguous & ordered
        m = len(idx)
        c1, c2 = int(m * train_frac), int(m * (train_frac + val_frac))
        train[idx[:c1]] = True
        val[idx[c1:c2]] = True
        test[idx[c2:]] = True
    return train, val, test


def _fit_xgb(Xtr, ytr, Xval, yval, seed: int, imbalance: str = "class_weight",
             focal_gamma: float = 2.0, xgb_params: dict | None = None):
    """XGBoost with exactly ONE imbalance mechanism (rule 1); early-stop on val PR-AUC.

    imbalance="class_weight": scale_pos_weight = neg/pos (the locked default).
    imbalance="focal":        alpha-free focal-loss objective, scale_pos_weight=1
                              (the mechanisms are never combined).
    xgb_params overlays overrides on DEFAULT_XGB_PARAMS (HPO path); early stopping
    and the eval metric are fixed, not searchable.
    """
    pos = int(ytr.sum())
    neg = int(len(ytr) - pos)
    spw = (neg / pos) if pos else 1.0
    common = dict(
        **{**DEFAULT_XGB_PARAMS, **(xgb_params or {})},
        eval_metric="aucpr",          # PR-AUC drives early stopping (rule 5); rank-based,
        early_stopping_rounds=40,     # so it is valid on raw margins too (focal path)
        tree_method="hist",
        random_state=seed,
        n_jobs=-1,
    )
    if imbalance == "class_weight":
        model = XGBClassifier(scale_pos_weight=spw, **common)
    elif imbalance == "focal":
        model = XGBClassifier(objective=focal_objective(focal_gamma),
                              scale_pos_weight=1.0, **common)
        spw = 1.0
    else:
        raise ValueError(f"unknown imbalance mechanism: {imbalance!r}")
    model.fit(Xtr, ytr, eval_set=[(Xval, yval)], verbose=False)
    return model, spw


def _predict_scores(model, X, imbalance: str) -> np.ndarray:
    """Fraud scores in [0,1]. With a custom objective XGBoost outputs a raw margin,
    so the focal path applies the sigmoid itself."""
    if imbalance == "focal":
        return sigmoid(model.predict(X, output_margin=True))
    return model.predict_proba(X)[:, 1]


def train_and_evaluate(
    df: pd.DataFrame,
    feature_cols: list[str],
    *,
    label: str = "label",
    ts_col: str = "timestamp",
    seed: int = 42,
    persist_as: str | None = None,
    partition=None,
    imbalance: str = "class_weight",
    focal_gamma: float = 2.0,
    xgb_params: dict | None = None,
    bundle_extra: dict | None = None,
) -> dict:
    """Run the full honest pipeline for one feature set and return a result dict.

    ``xgb_params`` overlays hyperparameter overrides on DEFAULT_XGB_PARAMS (the
    HPO path). ``bundle_extra`` lets the caller add self-describing fields
    (dataset, feature families, TGN provenance, split spec) to the persisted
    bundle without the harness knowing about them.
    """
    train, val, test = time_split(df[ts_col], partition=partition)
    X = df[feature_cols]
    y = df[label].astype(int).to_numpy()

    model, spw = _fit_xgb(X[train], y[train], X[val], y[val], seed,
                          imbalance=imbalance, focal_gamma=focal_gamma,
                          xgb_params=xgb_params)
    p_val = _predict_scores(model, X[val], imbalance)
    p_test = _predict_scores(model, X[test], imbalance)

    threshold = tune_threshold(y[val], p_val)            # tuned on val, then frozen
    test_metrics = evaluate(y[test], p_test, threshold)
    val_metrics = evaluate(y[val], p_val, threshold)

    importances = dict(sorted(
        zip(feature_cols, (float(v) for v in model.feature_importances_)),
        key=lambda kv: kv[1], reverse=True,
    ))
    result = {
        "n_features": len(feature_cols),
        "features": feature_cols,
        "split_sizes": {"train": int(train.sum()), "val": int(val.sum()), "test": int(test.sum())},
        "split_frauds": {"train": int(y[train].sum()), "val": int(y[val].sum()), "test": int(y[test].sum())},
        "imbalance": imbalance if imbalance == "class_weight" else f"focal(gamma={focal_gamma})",
        "scale_pos_weight": round(spw, 2),
        "best_iteration": int(getattr(model, "best_iteration", -1) or -1),
        "xgb_params": {**DEFAULT_XGB_PARAMS, **(xgb_params or {})},
        "val": val_metrics,
        "test": test_metrics,
        "feature_importance": importances,
    }

    if persist_as:
        art_dir = REPO_ROOT / "artifacts" / persist_as
        art_dir.mkdir(parents=True, exist_ok=True)
        model.save_model(art_dir / "model.json")
        _write_bundle(art_dir, threshold=threshold, feature_cols=feature_cols,
                      result=result, seed=seed, imbalance=imbalance,
                      focal_gamma=focal_gamma, spw=spw, bundle_extra=bundle_extra)
        result["artifact_dir"] = str(art_dir)
    return result


def _write_bundle(art_dir: Path, *, threshold, feature_cols, result, seed,
                  imbalance, focal_gamma, spw, bundle_extra: dict | None) -> None:
    """Persist bundle schema v2 next to model.json.

    ``score_fn`` matters: a focal model reloaded from model.json has lost its
    Python objective, so predict_proba on it is WRONG — scoring must apply
    sigmoid to the raw margin. modeling/score.py honors this field.
    """
    bundle = {
        "schema_version": 2,
        "model_type": "xgboost",
        "threshold": threshold,
        "features": feature_cols,
        "imbalance": result["imbalance"],
        "focal_gamma": focal_gamma if imbalance == "focal" else None,
        "score_fn": "sigmoid_margin" if imbalance == "focal" else "proba",
        "scale_pos_weight": spw,
        "seed": seed,
        "xgb_params": result["xgb_params"],
        "best_iteration": result["best_iteration"],
        "metrics": {"val": result["val"], "test": result["test"]},
        "note": "trees need no scaler",
        **(bundle_extra or {}),
    }
    payload = json.dumps(bundle, indent=2)
    out = art_dir / "bundle.json"
    try:
        out.write_text(payload, encoding="utf-8")
    except PermissionError:  # transient OneDrive sync lock — retry once
        import time
        time.sleep(2.0)
        out.write_text(payload, encoding="utf-8")


def train_and_evaluate_seeds(
    df: pd.DataFrame,
    feature_cols: list[str],
    *,
    seeds=(42, 43, 44),
    persist_as: str | None = None,
    **kw,
) -> dict:
    """Repeat the pipeline across seeds; report mean ± std of the headline metrics.

    Single-seed margins of ~0.01 PR-AUC are within subsample noise, so any
    model-class or mechanism comparison must be read off these aggregates, never
    off one seed. Only the first seed's model is persisted (they share split,
    features and mechanism; the artifact is for the demo, not the comparison).
    """
    runs = [
        train_and_evaluate(df, feature_cols, seed=s,
                           persist_as=(persist_as if s == seeds[0] else None), **kw)
        for s in seeds
    ]

    def _agg(pick):
        vals = np.array([pick(r) for r in runs], dtype=float)
        return round(float(vals.mean()), 5), round(float(vals.std(ddof=0)), 5)

    summary = {
        "seeds": list(seeds),
        "imbalance": runs[0]["imbalance"],
        "n_features": runs[0]["n_features"],
        "xgb_params": runs[0]["xgb_params"],
        "split_sizes": runs[0]["split_sizes"],
        "split_frauds": runs[0]["split_frauds"],
    }
    for split in ("val", "test"):
        for metric in ("pr_auc", "roc_auc", "precision@100", "recall@100", "f1"):
            mean, std = _agg(lambda r, s=split, m=metric: r[s][m])
            summary[f"{split}_{metric}_mean"] = mean
            summary[f"{split}_{metric}_std"] = std
    summary["per_seed"] = runs
    return summary
