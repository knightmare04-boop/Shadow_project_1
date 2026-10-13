"""Non-IID and IID dataset partitioning for federated learning simulation.

Simulates distributed banking institutions:
  * Non-IID (primary): Clusters accounts by transaction volume and activity
    patterns via KMeans. Each client represents a distinct financial institution
    profile (e.g. retail bank, commercial institution, high-volume merchant bank).
    Produces realistic feature skew and label skew across clients.
  * IID (baseline): Uniform stratified random split across K clients.
  * Cross-dataset (stress test): Treats distinct simulation environments
    (BankSim, synth_erp, etc.) as independent institutional clients.
"""
from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.model_selection import StratifiedKFold

log = logging.getLogger(__name__)


@dataclass
class PartitionResult:
    """Container for client partition assignments and statistical audit."""
    k: int
    partition_type: str
    client_ids: np.ndarray          # integer client id per row (0 .. k-1)
    client_masks: dict[int, np.ndarray]  # bool mask per client
    client_summaries: list[dict]    # summary dict per client

    def get_client_mask(self, client_id: int) -> np.ndarray:
        return self.client_masks[client_id]


def _build_summary(client_ids: np.ndarray, y: np.ndarray, k: int) -> list[dict]:
    total_n = len(client_ids)
    summaries = []
    for c in range(k):
        mask = client_ids == c
        n_rows = int(mask.sum())
        n_fraud = int(y[mask].sum()) if n_rows > 0 else 0
        rate = (n_fraud / n_rows) if n_rows > 0 else 0.0
        pct = (n_rows / total_n) if total_n > 0 else 0.0
        summaries.append({
            "client_id": c,
            "n_rows": n_rows,
            "pct_rows": round(pct, 4),
            "n_fraud": n_fraud,
            "fraud_rate": round(rate, 6),
        })
    return summaries


def partition_by_account_cluster(
    df: pd.DataFrame,
    *,
    k: int = 4,
    seed: int = 42,
    edges_path: str | Path | None = None,
    source_col: str = "source_account",
    label_col: str = "label",
    min_frauds_per_client: int = 5,
) -> PartitionResult:
    """Partition transactions by clustering source accounts into K client banks.

    Accounts are clustered by log-transformed transaction volume and degree:
      - tx_count: number of transactions by this account
      - total_amount: aggregate volume
      - mean_amount: average transaction size

    If `source_col` is not in `df`, `edges_path` is read to map `transaction_id`
    to `source_account`.
    """
    n_rows = len(df)
    y = df[label_col].astype(int).to_numpy()

    # Resolve source account mapping
    if source_col in df.columns:
        sources = df[source_col].astype(str).to_numpy()
        amounts = df["amount"].to_numpy() if "amount" in df.columns else np.exp(df["log_amount"].to_numpy()) - 1.0
    elif edges_path is not None:
        p = Path(edges_path)
        if not p.exists():
            raise FileNotFoundError(f"edges_path not found: {edges_path}")
        edges = pd.read_csv(p, usecols=["transaction_id", source_col, "amount"])
        edges["transaction_id"] = edges["transaction_id"].astype(str)
        mapping = dict(zip(edges["transaction_id"], edges[source_col].astype(str)))
        amt_mapping = dict(zip(edges["transaction_id"], edges["amount"].astype(float)))
        
        tx_ids = df["transaction_id"].astype(str).tolist()
        sources = np.array([mapping.get(tid, f"unk_{i}") for i, tid in enumerate(tx_ids)])
        amounts = np.array([amt_mapping.get(tid, 10.0) for tid in tx_ids])
    else:
        raise ValueError(f"'{source_col}' not in df and no edges_path provided")

    # Compute account-level feature aggregates
    account_df = pd.DataFrame({
        "account": sources,
        "amount": amounts,
        "is_fraud": y,
    })
    stats = account_df.groupby("account").agg(
        tx_count=("amount", "count"),
        total_amount=("amount", "sum"),
        mean_amount=("amount", "mean"),
        fraud_count=("is_fraud", "sum"),
    ).reset_index()

    features = np.log1p(stats[["tx_count", "total_amount", "mean_amount"]].to_numpy())
    
    # Run KMeans clustering
    kmeans = KMeans(n_clusters=k, random_state=seed, n_init=10)
    cluster_labels = kmeans.fit_predict(features)
    stats["cluster"] = cluster_labels

    # Verify each cluster has minimum fraud representation for valid training
    cluster_frauds = stats.groupby("cluster")["fraud_count"].sum()
    if (cluster_frauds < min_frauds_per_client).any():
        log.warning(
            "KMeans produced cluster with <%d frauds (%s). Falling back to quantile-stratified clustering.",
            min_frauds_per_client, dict(cluster_frauds)
        )
        # Fallback: quantile volume sorting stratified to ensure fraud in all clients
        stats = stats.sort_values(["fraud_count", "tx_count"], ascending=[False, False]).reset_index(drop=True)
        stats["cluster"] = np.arange(len(stats)) % k

    acct_to_cluster = dict(zip(stats["account"], stats["cluster"]))
    client_ids = np.array([acct_to_cluster.get(s, hash(s) % k) for s in sources], dtype=int)

    masks = {c: (client_ids == c) for c in range(k)}
    summaries = _build_summary(client_ids, y, k)

    log.info(
        "Account-cluster partition (k=%d): sizes=%s, frauds=%s",
        k,
        [s["n_rows"] for s in summaries],
        [s["n_fraud"] for s in summaries],
    )

    return PartitionResult(
        k=k,
        partition_type="account_cluster",
        client_ids=client_ids,
        client_masks=masks,
        client_summaries=summaries,
    )


def partition_by_random(
    df: pd.DataFrame,
    *,
    k: int = 4,
    seed: int = 42,
    label_col: str = "label",
) -> PartitionResult:
    """IID baseline: Stratified random split of transactions into K clients."""
    y = df[label_col].astype(int).to_numpy()
    skf = StratifiedKFold(n_splits=k, shuffle=True, random_state=seed)

    client_ids = np.zeros(len(df), dtype=int)
    for client_idx, (_, test_idx) in enumerate(skf.split(df, y)):
        client_ids[test_idx] = client_idx

    masks = {c: (client_ids == c) for c in range(k)}
    summaries = _build_summary(client_ids, y, k)

    return PartitionResult(
        k=k,
        partition_type="random_iid",
        client_ids=client_ids,
        client_masks=masks,
        client_summaries=summaries,
    )


def partition_cross_dataset(
    dfs: dict[str, pd.DataFrame],
    label_col: str = "label",
) -> tuple[pd.DataFrame, PartitionResult]:
    """Cross-dataset partition where each dataset represents one client bank.

    Returns the concatenated unified DataFrame and the corresponding PartitionResult.
    """
    dataset_names = list(dfs.keys())
    k = len(dataset_names)

    tagged_frames = []
    for c_idx, name in enumerate(dataset_names):
        d = dfs[name].copy()
        d["__client_id"] = c_idx
        tagged_frames.append(d)

    unified = pd.concat(tagged_frames, ignore_index=True)
    client_ids = unified["__client_id"].to_numpy(dtype=int)
    unified = unified.drop(columns=["__client_id"])

    y = unified[label_col].astype(int).to_numpy()
    masks = {c: (client_ids == c) for c in range(k)}
    summaries = _build_summary(client_ids, y, k)
    for s, name in zip(summaries, dataset_names):
        s["dataset_name"] = name

    return unified, PartitionResult(
        k=k,
        partition_type="cross_dataset",
        client_ids=client_ids,
        client_masks=masks,
        client_summaries=summaries,
    )
