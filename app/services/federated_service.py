"""Live Federated Fraud Scoring Service.

Enables collaborative multi-bank inference:
Given an incoming transaction, scores it against an ensemble of distributed
banking models using FedProx (val-PR-AUC-weighted) or uniform aggregation,
preserving local bank privacy while maximizing cross-institutional fraud capture.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Sequence

import numpy as np
import pandas as pd

from app.core.logging import get_logger
from app.services.scoring_service import ScoreResult
from federated.server import aggregate_scores_fedprox, aggregate_scores_uniform
from modeling.score import ScoringBundle

log = get_logger(__name__)


@dataclass
class FederatedScoreResult:
    transaction_id: str
    federated_score: float
    client_scores: dict[str, float]
    threshold: float
    alert: bool
    aggregation_method: str
    latency_ms: float
    institution_weights: dict[str, float] = field(default_factory=dict)


class FederatedScoringService:
    """Manages multi-institution federated model scoring in real time."""

    def __init__(
        self,
        *,
        client_bundles: dict[str, ScoringBundle],
        client_weights: dict[str, float] | None = None,
        aggregation_method: str = "fedprox",
        threshold: float | None = None,
    ):
        self.bundles = client_bundles
        self.client_names = list(client_bundles.keys())
        self.method = aggregation_method
        
        # Empirical reliability weights (validation PR-AUC per client)
        if client_weights:
            self.weights = client_weights
        else:
            self.weights = {
                name: float(bundle.metrics.get("val", {}).get("pr_auc", 0.5))
                for name, bundle in client_bundles.items()
            }
            
        # Decision threshold: average or calibrated
        if threshold is not None:
            self.threshold = threshold
        else:
            thrs = [b.threshold for b in client_bundles.values()]
            self.threshold = float(np.mean(thrs)) if thrs else 0.5

    def score_transaction(
        self,
        feature_row: pd.DataFrame | dict,
        transaction_id: str,
    ) -> FederatedScoreResult:
        """Score a single incoming transaction across all client models."""
        t0 = time.perf_counter()
        
        if isinstance(feature_row, dict):
            df = pd.DataFrame([feature_row])
        else:
            df = feature_row

        scores_by_client: dict[str, float] = {}
        for name, bundle in self.bundles.items():
            # Align features
            missing = [c for c in bundle.features if c not in df.columns]
            if missing:
                for c in missing:
                    df[c] = 0.0
            x_mat = df[bundle.features]
            
            # Predict
            if bundle.score_fn == "sigmoid_margin":
                from modeling.objectives import sigmoid
                raw = bundle.model.predict(xgb.DMatrix(x_mat), output_margin=True)
                s = float(sigmoid(raw)[0])
            else:
                p = bundle.model.predict_proba(x_mat)[:, 1]
                s = float(p[0])
            scores_by_client[name] = round(s, 5)

        score_list = [np.array([scores_by_client[n]]) for n in self.client_names]
        weights_list = [self.weights[n] for n in self.client_names]

        if self.method == "fedprox":
            agg = float(aggregate_scores_fedprox(score_list, weights_list)[0])
        else:
            agg = float(aggregate_scores_uniform(score_list)[0])

        latency_ms = (time.perf_counter() - t0) * 1000.0
        alert = bool(agg >= self.threshold)

        return FederatedScoreResult(
            transaction_id=transaction_id,
            federated_score=round(agg, 5),
            client_scores=scores_by_client,
            threshold=round(self.threshold, 4),
            alert=alert,
            aggregation_method=self.method,
            latency_ms=round(latency_ms, 2),
            institution_weights={n: round(w, 4) for n, w in self.weights.items()},
        )
