"""Federated Client — autonomous institutional learner (CLAUDE.md rules 1-5 compliant).

Each FederatedClient models an independent financial institution (e.g. Bank A, B, C):
  * Private Data: Trains strictly on its local slice of data (no row-sharing).
  * Imbalance Discipline: One imbalance mechanism (scale_pos_weight derived locally).
  * Early Stopping: Stops on its local validation PR-AUC.
  * Local Calibration: Tunes its decision threshold on local validation data.
  * Model Selection Metric: PR-AUC (Rule 5).
  * Privacy Guarantee: Only outputs prediction scores on query data or its empirical
    validation PR-AUC (used by the server as confidence weight).
"""
from __future__ import annotations

import logging
from typing import Sequence

import numpy as np
import pandas as pd

from modeling.harness import _fit_xgb, _predict_scores
from modeling.metrics import evaluate, tune_threshold

log = logging.getLogger(__name__)


class FederatedClient:
    """Represents a single bank or financial entity participating in federation."""

    def __init__(
        self,
        client_id: int,
        name: str | None = None,
        *,
        feature_cols: list[str],
        imbalance: str = "class_weight",
        focal_gamma: float = 2.0,
        seed: int = 42,
    ):
        self.client_id = client_id
        self.name = name or f"client_{client_id}"
        self.feature_cols = list(feature_cols)
        self.imbalance = imbalance
        self.focal_gamma = focal_gamma
        self.seed = seed

        self.model = None
        self.threshold: float = 0.5
        self.spw: float = 1.0
        self.val_pr_auc: float = 0.0
        self.val_metrics: dict = {}
        self.train_size: int = 0
        self.train_frauds: int = 0
        self.val_size: int = 0
        self.val_frauds: int = 0

    def fit(
        self,
        X_tr: pd.DataFrame | np.ndarray,
        y_tr: np.ndarray,
        X_val: pd.DataFrame | np.ndarray,
        y_val: np.ndarray,
        xgb_params: dict | None = None,
    ) -> dict:
        """Fit local XGBoost model on the client's own historical data.

        Early stops on local validation PR-AUC, then tunes and freezes the threshold.
        """
        self.train_size = int(len(y_tr))
        self.train_frauds = int(y_tr.sum())
        self.val_size = int(len(y_val))
        self.val_frauds = int(y_val.sum())

        if self.train_frauds == 0:
            log.warning("[%s] 0 frauds in train set; fitting unweighted model", self.name)

        self.model, self.spw = _fit_xgb(
            X_tr,
            y_tr,
            X_val,
            y_val,
            seed=self.seed,
            imbalance=self.imbalance,
            focal_gamma=self.focal_gamma,
            xgb_params=xgb_params,
        )

        p_val = self.predict_scores(X_val)
        self.threshold = tune_threshold(y_val, p_val)
        self.val_metrics = evaluate(y_val, p_val, self.threshold)
        self.val_pr_auc = float(self.val_metrics.get("pr_auc", 0.0))

        log.info(
            "[%s] trained: %d rows (%d fraud, spw=%.2f) -> val PR-AUC: %.4f, thr: %.4f",
            self.name,
            self.train_size,
            self.train_frauds,
            self.spw,
            self.val_pr_auc,
            self.threshold,
        )
        return self.get_summary()

    def predict_scores(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        """Predict fraud probability scores in [0, 1]."""
        if self.model is None:
            raise RuntimeError(f"Client {self.name} has not been fitted.")
        if isinstance(X, pd.DataFrame):
            X_mat = X[self.feature_cols]
        else:
            X_mat = X
        return _predict_scores(self.model, X_mat, self.imbalance)

    def evaluate_test(
        self,
        X_test: pd.DataFrame | np.ndarray,
        y_test: np.ndarray,
        threshold: float | None = None,
    ) -> dict:
        """Evaluate client's model on test data using frozen or provided threshold."""
        thr = self.threshold if threshold is None else threshold
        scores = self.predict_scores(X_test)
        metrics = evaluate(y_test, scores, thr)
        metrics["threshold"] = thr
        metrics["scale_pos_weight"] = self.spw
        metrics["train_rows"] = self.train_size
        metrics["train_frauds"] = self.train_frauds
        return metrics

    def get_summary(self) -> dict:
        """Summary of client characteristics and validation performance."""
        return {
            "client_id": self.client_id,
            "name": self.name,
            "train_size": self.train_size,
            "train_frauds": self.train_frauds,
            "val_size": self.val_size,
            "val_frauds": self.val_frauds,
            "scale_pos_weight": round(self.spw, 2),
            "val_pr_auc": round(self.val_pr_auc, 4),
            "val_threshold": round(self.threshold, 4),
            "val_metrics": self.val_metrics,
        }
