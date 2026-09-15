"""Live fraud scoring — the point where Module 3's ERP postings meet the
research pipeline. One `FraudScoringService` instance per dataset/tenant,
holding the live `OnlineTopologyState` + `OnlineOrdinaryState` (the window
that makes topology/ordinary features leakage-safe) plus the loaded scoring
bundle (Module 5, Stage B's "online" artifact — ordinary+topology only, no
TGN, because TGN cannot be served online today — see
app/services/online_topology.py and tools/train_online_bundles.py).

Latency budget (BCSE497J NFR): topology + ordinary + XGBoost + SHAP should
land well under the <200ms p95 target — everything here is O(1)-per-feature
graph/dict lookups plus one small DMatrix predict, no whole-stream replay.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import xgboost as xgb

from app.core.logging import get_logger
from app.core.metrics import SCORING_LATENCY
from app.services.online_ordinary import OnlineOrdinaryState
from app.services.online_topology import OnlineTopologyState

log = get_logger(__name__)


@dataclass
class ScoreResult:
    transaction_id: str
    score: float
    threshold: float
    alert: bool
    latency_ms: float
    risk_drivers: list[dict] = field(default_factory=list)


class FraudScoringService:
    def __init__(self, *, dataset: str, bundle, topology_params: dict,
                categorical_prefixes: dict | None = None):
        self.dataset = dataset
        self.bundle = bundle  # modeling.score.ScoringBundle
        self.topology = OnlineTopologyState(
            window=topology_params.get("window"),
            max_cycle_len=topology_params.get("max_cycle_len", 6),
            search_budget=topology_params.get("search_budget", 4000),
            lap_memory=topology_params.get("lap_memory", 25),
            lap_tol=topology_params.get("lap_tol", 0.01),
        )
        self.ordinary = OnlineOrdinaryState(
            ordinary_cols=[c for c in bundle.features if c not in
                          {"in_cycle", "cycle_length", "in_cycle_ge3", "cycle_amount_ratio",
                           "cycle_time_span", "fan_in", "fan_out", "dest_in_degree",
                           "src_out_degree", "lap_in_recur", "lap_in_payers",
                           "lap_out_recur", "lap_out_payees"}],
            categorical_prefixes=categorical_prefixes or {},
        )

    def score(self, *, transaction_id: str, ts: float, source_account: str,
             dest_account: str, amount: float, categoricals: dict | None = None,
             top_n_drivers: int = 5) -> ScoreResult:
        t0 = time.perf_counter()

        topo_feats = self.topology.score_transaction(
            ts=ts, source_account=source_account, dest_account=dest_account, amount=amount,
        )
        ord_feats = self.ordinary.score_transaction(
            ts=ts, source_account=source_account, dest_account=dest_account,
            amount=amount, categoricals=categoricals,
        )
        row = {**topo_feats, **ord_feats}
        X = pd.DataFrame([row])[self.bundle.features]

        from modeling.objectives import sigmoid
        dmat = xgb.DMatrix(X, feature_names=self.bundle.features)
        margin = self.bundle.booster.predict(dmat, output_margin=True,
                                             iteration_range=self.bundle.iteration_range)
        score = float(sigmoid(np.asarray(margin, dtype=np.float64))[0])
        is_alert = score >= self.bundle.threshold

        drivers: list[dict] = []
        if is_alert:
            from modeling.explain import top_drivers, tree_shap
            contribs, _ = tree_shap(self.bundle, X)
            families = self.bundle.feature_families or {}
            drivers = top_drivers(contribs[0], X.iloc[0], self.bundle.features, families, n=top_n_drivers)

        latency_s = time.perf_counter() - t0
        SCORING_LATENCY.labels(dataset=self.dataset).observe(latency_s)
        latency_ms = latency_s * 1000
        return ScoreResult(
            transaction_id=transaction_id, score=round(score, 6),
            threshold=self.bundle.threshold, alert=is_alert,
            latency_ms=round(latency_ms, 2), risk_drivers=drivers,
        )
