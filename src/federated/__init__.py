"""Federated Fraud Detection — privacy-preserving multi-bank collaborative learning.

This module provides the federated architecture for evaluating fraud detection
across distributed institutions without sharing raw transaction data:

    * partition: Non-IID account-clustering and IID partitioners
    * client: FederatedClient wrapping honest local training & validation
    * server: FederationServer aggregating predictions via uniform,
              FedProx (val-PR-AUC-weighted), and size-weighted schemes
"""
from __future__ import annotations

from federated.partition import (
    partition_by_account_cluster,
    partition_by_random,
    partition_cross_dataset,
    PartitionResult,
)
from federated.client import FederatedClient
from federated.server import (
    FederationServer,
    aggregate_scores_uniform,
    aggregate_scores_fedprox,
    aggregate_scores_size_weighted,
)

__all__ = [
    "partition_by_account_cluster",
    "partition_by_random",
    "partition_cross_dataset",
    "PartitionResult",
    "FederatedClient",
    "FederationServer",
    "aggregate_scores_uniform",
    "aggregate_scores_fedprox",
    "aggregate_scores_size_weighted",
]
