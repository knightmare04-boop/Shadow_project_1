"""Unit tests for the federated fraud detection pipeline."""
import sys
import unittest
import numpy as np
import pandas as pd

from federated.client import FederatedClient
from federated.partition import (
    partition_by_account_cluster,
    partition_by_random,
)
from federated.server import (
    FederationServer,
    aggregate_scores_fedprox,
    aggregate_scores_size_weighted,
    aggregate_scores_uniform,
)
from modeling.harness import time_split


def make_mock_data():
    """Synthetic dataset with account structures for testing federated partitioning & training."""
    rng = np.random.default_rng(42)
    n = 2000
    n_accounts = 40
    accounts = [f"acct_{i:03d}" for i in range(n_accounts)]
    
    # Assign accounts to different activity tiers (non-IID)
    weights = np.linspace(0.1, 1.0, n_accounts)
    weights = weights / weights.sum()
    src_accounts = rng.choice(accounts, size=n, p=weights)
    dest_accounts = rng.choice(accounts, size=n)
    
    amounts = rng.exponential(scale=100.0, size=n) + 1.0
    high_risk = set(accounts[:10])
    p_fraud = np.array([0.15 if s in high_risk else 0.01 for s in src_accounts])
    labels = (rng.uniform(size=n) < p_fraud).astype(int)
    
    f1 = np.log1p(amounts) + rng.normal(scale=0.2, size=n)
    f2 = rng.normal(scale=1.0, size=n)
    
    df = pd.DataFrame({
        "transaction_id": [f"tx_{i:05d}" for i in range(n)],
        "timestamp": np.sort(rng.integers(0, 100, size=n)),
        "source_account": src_accounts,
        "dest_account": dest_accounts,
        "amount": amounts,
        "log_amount": np.log1p(amounts),
        "f1": f1,
        "f2": f2,
        "label": labels,
    })
    return df


class TestFederatedPipeline(unittest.TestCase):
    def setUp(self):
        self.df = make_mock_data()

    def test_partition_by_random(self):
        k = 4
        res = partition_by_random(self.df, k=k, seed=42)
        self.assertEqual(res.k, k)
        self.assertEqual(res.partition_type, "random_iid")
        self.assertEqual(len(res.client_summaries), k)
        total_rows = sum(s["n_rows"] for s in res.client_summaries)
        self.assertEqual(total_rows, len(self.df))
        for s in res.client_summaries:
            self.assertGreater(s["n_rows"], 0)
            self.assertGreater(s["n_fraud"], 0)

    def test_partition_by_account_cluster(self):
        k = 3
        res = partition_by_account_cluster(
            self.df,
            k=k,
            seed=42,
            source_col="source_account",
        )
        self.assertEqual(res.k, k)
        self.assertEqual(res.partition_type, "account_cluster")
        self.assertEqual(len(res.client_summaries), k)
        total_rows = sum(s["n_rows"] for s in res.client_summaries)
        self.assertEqual(total_rows, len(self.df))
        self.assertTrue(set(res.client_ids).issubset({0, 1, 2}))

    def test_federated_client_fit_and_predict(self):
        df = self.df
        feature_cols = ["f1", "f2"]
        train, val, test = time_split(df["timestamp"])
        
        client = FederatedClient(
            client_id=0,
            name="Bank_Alpha",
            feature_cols=feature_cols,
            seed=42,
        )
        
        summary = client.fit(
            X_tr=df.loc[train, feature_cols],
            y_tr=df.loc[train, "label"].to_numpy(),
            X_val=df.loc[val, feature_cols],
            y_val=df.loc[val, "label"].to_numpy(),
        )
        
        self.assertEqual(summary["train_size"], int(train.sum()))
        self.assertGreaterEqual(summary["val_pr_auc"], 0.0)
        
        scores = client.predict_scores(df.loc[test, feature_cols])
        self.assertEqual(len(scores), int(test.sum()))
        self.assertTrue((scores >= 0.0).all() and (scores <= 1.0).all())
        
        test_metrics = client.evaluate_test(
            df.loc[test, feature_cols],
            df.loc[test, "label"].to_numpy(),
        )
        self.assertIn("pr_auc", test_metrics)
        self.assertIn("roc_auc", test_metrics)

    def test_federation_server_aggregation(self):
        df = self.df
        feature_cols = ["f1", "f2"]
        k = 3
        partition = partition_by_random(df, k=k, seed=42)
        train, val, test = time_split(df["timestamp"])
        
        clients = []
        for c_id in range(k):
            c_mask = partition.get_client_mask(c_id)
            tr_c = train & c_mask
            val_c = val & c_mask
            
            client = FederatedClient(client_id=c_id, feature_cols=feature_cols, seed=42 + c_id)
            client.fit(
                X_tr=df.loc[tr_c, feature_cols],
                y_tr=df.loc[tr_c, "label"].to_numpy(),
                X_val=df.loc[val_c, feature_cols],
                y_val=df.loc[val_c, "label"].to_numpy(),
            )
            clients.append(client)
            
        server = FederationServer(clients)
        self.assertEqual(server.k, k)
        
        server.calibrate_threshold(
            pooled_X_val=df.loc[val, feature_cols],
            y_val=df.loc[val, "label"].to_numpy(),
            method="fedprox",
        )
        
        X_test = df.loc[test, feature_cols]
        y_test = df.loc[test, "label"].to_numpy()
        
        for method in ["uniform", "fedprox", "size_weighted"]:
            results = server.evaluate(X_test, y_test, method=method)
            self.assertIn("pr_auc", results)
            self.assertIn("precision@100", results)
            self.assertEqual(results["aggregation_method"], method)


if __name__ == "__main__":
    unittest.main()
