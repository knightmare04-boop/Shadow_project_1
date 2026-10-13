"""Federation Server — privacy-preserving score aggregation & threshold calibration.

Implements model ensemble aggregation (Option B):
  * Uniform: Simple average across all K clients.
  * FedProx (Reliability-weighted): Clients weighted by their validation PR-AUC,
    mitigating non-IID client drift and down-weighting noisy institutions.
  * Size-weighted: Weighted proportionally to client training volume.

Invariants (CLAUDE.md rules 1-6):
  * No raw data or feature matrices leave client nodes.
  * Decision threshold is tuned on aggregated VALIDATION scores and frozen
    for test evaluation (Rule 5).
  * Evaluates PR-AUC (primary), ROC-AUC, F1, and Precision@k.
"""
from __future__ import annotations

import logging
from typing import Literal, Sequence

import numpy as np
import pandas as pd

from federated.client import FederatedClient
from modeling.metrics import evaluate, tune_threshold

log = logging.getLogger(__name__)

AggregationMethod = Literal["uniform", "fedprox", "size_weighted"]


def aggregate_scores_uniform(scores_list: Sequence[np.ndarray]) -> np.ndarray:
    """Arithmetic mean of client probability scores."""
    return np.mean(scores_list, axis=0)


def aggregate_scores_fedprox(
    scores_list: Sequence[np.ndarray],
    weights: Sequence[float],
    power: float = 1.0,
) -> np.ndarray:
    """Validation-PR-AUC weighted score aggregation.

    Down-weights clients with degraded validation performance due to non-IID skew.
    """
    w = np.maximum(np.asarray(weights, dtype=float), 1e-6) ** power
    norm_w = w / w.sum()
    stacked = np.stack(scores_list, axis=0)  # (K, N)
    return np.tensordot(norm_w, stacked, axes=(0, 0))


def aggregate_scores_size_weighted(
    scores_list: Sequence[np.ndarray],
    sizes: Sequence[int],
) -> np.ndarray:
    """Sample-size weighted score aggregation."""
    s = np.asarray(sizes, dtype=float)
    norm_s = s / s.sum() if s.sum() > 0 else np.ones(len(s)) / len(s)
    stacked = np.stack(scores_list, axis=0)
    return np.tensordot(norm_s, stacked, axes=(0, 0))


class FederationServer:
    """Central coordinator for aggregating federated client predictions."""

    def __init__(self, clients: Sequence[FederatedClient]):
        if not clients:
            raise ValueError("FederationServer requires at least one client")
        self.clients = list(clients)
        self.k = len(self.clients)
        self.thresholds: dict[str, float] = {}

    @property
    def client_weights(self) -> list[float]:
        """Validation PR-AUC of each client."""
        return [c.val_pr_auc for c in self.clients]

    @property
    def client_sizes(self) -> list[int]:
        """Training set size of each client."""
        return [c.train_size for c in self.clients]

    def aggregate(
        self,
        scores_list: Sequence[np.ndarray],
        method: AggregationMethod = "fedprox",
    ) -> np.ndarray:
        """Aggregate an ensemble of client score arrays."""
        if method == "uniform":
            return aggregate_scores_uniform(scores_list)
        elif method == "fedprox":
            return aggregate_scores_fedprox(scores_list, self.client_weights)
        elif method == "size_weighted":
            return aggregate_scores_size_weighted(scores_list, self.client_sizes)
        else:
            raise ValueError(f"Unknown aggregation method: {method}")

    def calibrate_threshold(
        self,
        X_val_by_client: Sequence[pd.DataFrame | np.ndarray] | None = None,
        y_val: np.ndarray | None = None,
        method: AggregationMethod = "fedprox",
        pooled_X_val: pd.DataFrame | np.ndarray | None = None,
    ) -> float:
        """Tune aggregation threshold on validation scores and freeze for test.

        If pooled_X_val and y_val are given, every client scores the pooled validation set,
        and threshold is tuned on the aggregated scores.
        Otherwise, falls back to weighted average of clients' local thresholds.
        """
        if pooled_X_val is not None and y_val is not None:
            val_scores = [c.predict_scores(pooled_X_val) for c in self.clients]
            agg_val_scores = self.aggregate(val_scores, method=method)
            thr = tune_threshold(y_val, agg_val_scores)
        else:
            # Fallback to local threshold weighted combination
            weights = np.array(self.client_weights)
            norm_w = weights / weights.sum() if weights.sum() > 0 else np.ones(self.k) / self.k
            thr = float(np.sum([w * c.threshold for w, c in zip(norm_w, self.clients)]))

        self.thresholds[method] = thr
        return thr

    def predict_scores(
        self,
        X: pd.DataFrame | np.ndarray,
        method: AggregationMethod = "fedprox",
    ) -> np.ndarray:
        """Collect score predictions from each client and aggregate."""
        scores_list = [c.predict_scores(X) for c in self.clients]
        return self.aggregate(scores_list, method=method)

    def evaluate(
        self,
        X_test: pd.DataFrame | np.ndarray,
        y_test: np.ndarray,
        method: AggregationMethod = "fedprox",
        threshold: float | None = None,
    ) -> dict:
        """Evaluate the federated ensemble on test data."""
        scores = self.predict_scores(X_test, method=method)
        thr = threshold if threshold is not None else self.thresholds.get(method, 0.5)
        metrics = evaluate(y_test, scores, thr)
        metrics["aggregation_method"] = method
        metrics["threshold"] = thr
        metrics["k_clients"] = self.k
        metrics["client_val_pr_aucs"] = [round(w, 4) for w in self.client_weights]
        metrics["client_sizes"] = self.client_sizes
        return metrics
