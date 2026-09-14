"""TreeSHAP attributions via XGBoost's native ``pred_contribs`` — no extra deps.

``pred_contribs=True`` runs the exact TreeSHAP algorithm (identical to the shap
package's TreeExplainer for XGBoost models) in margin space: per row, one signed
contribution per feature plus a bias column. It is a pure tree traversal, so it
works unchanged for models trained with the focal custom objective.

The optional plotting helper is the only place the ``shap`` package is touched
(install with:  pip install -e .[explain]).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import xgboost as xgb


def tree_shap(sb, X: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Exact TreeSHAP contributions for a ScoringBundle over rows X.

    Returns (contribs[n_rows, n_features], base[n_rows]) in margin (log-odds)
    space; contribs columns follow the bundle's feature order.
    """
    dmat = xgb.DMatrix(X[sb.features], feature_names=sb.features)
    raw = sb.booster.predict(dmat, pred_contribs=True,
                             iteration_range=sb.iteration_range)
    return raw[:, :-1], raw[:, -1]          # last column is the bias term


def global_importance(sb, X: pd.DataFrame, top: int | None = None) -> dict[str, float]:
    """Mean |SHAP| per feature over X, descending — the honest global importance
    (replaces gain-based feature_importances_ in final reporting)."""
    contribs, _ = tree_shap(sb, X)
    mean_abs = np.abs(contribs).mean(axis=0)
    ranked = sorted(zip(sb.features, mean_abs), key=lambda kv: kv[1], reverse=True)
    if top:
        ranked = ranked[:top]
    return {k: round(float(v), 5) for k, v in ranked}


def feature_family(feature: str, families: dict[str, list[str]]) -> str:
    for fam, cols in families.items():
        if feature in cols:
            return fam
    return "other"


def top_drivers(contrib_row: np.ndarray, x_row: pd.Series, features: list[str],
                families: dict[str, list[str]], n: int = 5) -> list[dict]:
    """The n features that pushed this row's score hardest (by |SHAP|)."""
    order = np.argsort(-np.abs(contrib_row))[:n]
    return [{
        "feature": features[i],
        "value": None if pd.isna(x_row[features[i]]) else round(float(x_row[features[i]]), 4),
        "shap": round(float(contrib_row[i]), 4),
        "family": feature_family(features[i], families),
    } for i in order]


def plot_summary(sb, X: pd.DataFrame, out_path: str) -> None:
    """Optional beeswarm summary plot; needs the shap package (pip install -e .[explain])."""
    try:
        import shap  # noqa: F401 — optional extra
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as e:
        raise ImportError(
            "SHAP plotting needs the optional extra: pip install -e .[explain]") from e
    contribs, base = tree_shap(sb, X)
    ex = shap.Explanation(values=contribs, base_values=base,
                          data=X[sb.features].to_numpy(),
                          feature_names=sb.features)
    shap.plots.beeswarm(ex, show=False, max_display=20)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
