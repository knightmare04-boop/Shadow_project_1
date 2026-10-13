"""The Federated Fraud Detection Experiment (CLAUDE.md rules 1-6).

Evaluates collaborative fraud detection across K simulated banking institutions
without sharing raw transactions:

    Arms (per dataset, per seed):
      centralized          All data pooled into one central database (privacy-violating upper bound)
      local_only           Each bank trains only on its isolated data (zero collaboration)
      federated_uniform    Collaborative ensemble with uniform score averaging
      federated_fedprox    Collaborative ensemble with validation-PR-AUC reliability weighting
      federated_size       Collaborative ensemble with training-size proportional weighting

Honesty invariants:
  * Chronological 60/20/20 split: Train is strictly earlier than Val, Val strictly
    earlier than Test (Rule 3).
  * One imbalance mechanism: scale_pos_weight derived per local training set (Rule 1).
  * Multi-seed (default 3): Reports mean ± std across random seeds.
  * Thresholds: Tuned on validation, frozen for test (Rule 5).
  * Non-IID account clustering: Accounts partitioned into institutions via KMeans on
    transaction volumes, producing authentic feature and label skew.

Run:
    python -m experiments.federated banksim --k 4 --seeds 42 43 44
    python -m experiments.federated synth_erp --k 4 --seeds 42 43 44
    python -m experiments.federated cross_dataset --seeds 42 43 44
    python -m experiments.federated sensitivity banksim --k_range 2 3 4 5
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys

import numpy as np
import pandas as pd

from common.config import get_dataset
from features.load import load_model_table, split_partition
from federated.client import FederatedClient
from federated.partition import (
    partition_by_account_cluster,
    partition_by_random,
    partition_cross_dataset,
    PartitionResult,
)
from federated.server import FederationServer
from modeling.harness import _fit_xgb, time_split
from modeling.metrics import evaluate, tune_threshold

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]

# Shared feature space and time scale for cross-dataset federation (from augmentation.py)
TIME_SCALE = {
    "ibm_aml": 1.0,
    "banksim": 1.0,
    "paysim": 1.0 / 24.0,
    "sap_wurzburg": 1.0 / 86400.0,
    "synth_erp": 1.0 / 86400.0,
}
TIME_COLS = ("time_since_prev_src", "cycle_time_span")


def _stats(values: list[float]) -> dict[str, float]:
    arr = np.asarray(values, dtype=float)
    return {
        "mean": round(float(arr.mean()), 5),
        "std": round(float(arr.std(ddof=1)), 5) if len(arr) > 1 else 0.0,
    }


def run_federated_single_seed(
    df: pd.DataFrame,
    feature_cols: list[str],
    partition_res: PartitionResult,
    *,
    seed: int = 42,
    partition: pd.Series | None = None,
    label_col: str = "label",
    ts_col: str = "timestamp",
) -> dict:
    """Run all 5 arms for a single seed and return evaluation metrics."""
    k = partition_res.k
    train_mask, val_mask, test_mask = time_split(df[ts_col], partition=partition)
    
    X = df[feature_cols]
    y = df[label_col].astype(int).to_numpy()

    X_train_pool, y_train_pool = X[train_mask], y[train_mask]
    X_val_pool, y_val_pool = X[val_mask], y[val_mask]
    X_test_pool, y_test_pool = X[test_mask], y[test_mask]

    # Arm 1: Centralized Upper Bound (All data pooled)
    log.info("[Seed %d] Training Centralized pooled model...", seed)
    model_cent, spw_cent = _fit_xgb(
        X_train_pool, y_train_pool, X_val_pool, y_val_pool, seed=seed
    )
    p_val_cent = model_cent.predict_proba(X_val_pool)[:, 1]
    thr_cent = tune_threshold(y_val_pool, p_val_cent)
    p_test_cent = model_cent.predict_proba(X_test_pool)[:, 1]
    res_cent = evaluate(y_test_pool, p_test_cent, thr_cent)
    res_cent["threshold"] = thr_cent
    res_cent["scale_pos_weight"] = round(spw_cent, 2)
    res_cent["train_rows"] = int(len(X_train_pool))

    # Train K Federated Clients
    clients: list[FederatedClient] = []
    client_test_evals: list[dict] = []
    client_global_test_evals: list[dict] = []

    log.info("[Seed %d] Training %d federated clients...", seed, k)
    for c_id in range(k):
        c_mask = partition_res.get_client_mask(c_id)
        tr_c = train_mask & c_mask
        val_c = val_mask & c_mask
        te_c = test_mask & c_mask

        client = FederatedClient(
            client_id=c_id,
            name=f"Bank_{c_id}",
            feature_cols=feature_cols,
            seed=seed + c_id,
        )

        # Handle edge case where a client might have no train/val data
        if tr_c.sum() == 0 or val_c.sum() == 0:
            log.warning("Client %d has empty split; skipping fit", c_id)
            continue

        client.fit(
            X_tr=X[tr_c],
            y_tr=y[tr_c],
            X_val=X[val_c],
            y_val=y[val_c],
        )
        clients.append(client)

        # Arm 2: Local-only evaluation
        # (a) on local client test slice
        if te_c.sum() > 0 and y[te_c].sum() > 0:
            local_eval = client.evaluate_test(X[te_c], y[te_c])
        else:
            local_eval = {"pr_auc": 0.0, "roc_auc": 0.5, "f1": 0.0}
        client_test_evals.append(local_eval)

        # (b) on global pooled test set (zero-collaboration cross-bank generalization)
        global_eval = client.evaluate_test(X_test_pool, y_test_pool)
        client_global_test_evals.append(global_eval)

    # Instantiate Federation Server
    server = FederationServer(clients)

    # Calibrate aggregation thresholds on pooled validation period
    for method in ["uniform", "fedprox", "size_weighted"]:
        server.calibrate_threshold(
            pooled_X_val=X_val_pool,
            y_val=y_val_pool,
            method=method,
        )

    # Arm 3, 4, 5: Server Evaluation on Global Test Period
    res_uniform = server.evaluate(X_test_pool, y_test_pool, method="uniform")
    res_fedprox = server.evaluate(X_test_pool, y_test_pool, method="fedprox")
    res_size = server.evaluate(X_test_pool, y_test_pool, method="size_weighted")

    # Aggregate local-only metrics
    avg_local_test_pr_auc = float(np.mean([e.get("pr_auc", 0.0) for e in client_test_evals]))
    avg_global_test_pr_auc = float(np.mean([e.get("pr_auc", 0.0) for e in client_global_test_evals]))

    return {
        "seed": seed,
        "centralized": res_cent,
        "local_only": {
            "avg_local_slice_pr_auc": round(avg_local_test_pr_auc, 5),
            "avg_global_test_pr_auc": round(avg_global_test_pr_auc, 5),
            "client_local_evals": client_test_evals,
            "client_global_evals": client_global_test_evals,
        },
        "federated_uniform": res_uniform,
        "federated_fedprox": res_fedprox,
        "federated_size_weighted": res_size,
    }


def run_federated_experiment(
    dataset_name: str,
    k: int = 4,
    seeds: tuple[int, ...] = (42, 43, 44),
    partition_type: str = "account_cluster",
) -> dict:
    """Run intra-dataset federated learning experiment across multiple seeds."""
    log.info("Starting Federated Experiment on [%s] (k=%d, partition=%s, seeds=%s)",
             dataset_name, k, partition_type, seeds)
    
    df, manifest, tgn_cols = load_model_table(dataset_name, with_tgn=True)
    ordinary = manifest["ordinary_cols"]
    topology = manifest["topology_cols"]
    all_features = ordinary + topology + tgn_cols
    log.info("[%s] Total features: %d (%d ord, %d topo, %d tgn)",
             dataset_name, len(all_features), len(ordinary), len(topology), len(tgn_cols))

    partition = split_partition(df)
    edges_path = Path(get_dataset(dataset_name)["processed_dir"]) / "edges_transactions.csv"

    # Generate Partition
    if partition_type == "account_cluster":
        part_res = partition_by_account_cluster(
            df,
            k=k,
            seed=42,
            edges_path=edges_path,
        )
    elif partition_type == "random_iid":
        part_res = partition_by_random(df, k=k, seed=42)
    else:
        raise ValueError(f"Unknown partition_type: {partition_type}")

    per_seed_runs = []
    for s in seeds:
        run_res = run_federated_single_seed(
            df,
            all_features,
            part_res,
            seed=s,
            partition=partition,
        )
        per_seed_runs.append(run_res)

    # Compute aggregate mean and std across seeds
    arms = ["centralized", "federated_uniform", "federated_fedprox", "federated_size_weighted"]
    summary_pr_auc: dict[str, dict] = {}
    summary_f1: dict[str, dict] = {}

    for arm in arms:
        pr_vals = [r[arm]["pr_auc"] for r in per_seed_runs]
        f1_vals = [r[arm]["f1"] for r in per_seed_runs]
        summary_pr_auc[arm] = _stats(pr_vals)
        summary_f1[arm] = _stats(f1_vals)

    local_global_prs = [r["local_only"]["avg_global_test_pr_auc"] for r in per_seed_runs]
    local_slice_prs = [r["local_only"]["avg_local_slice_pr_auc"] for r in per_seed_runs]
    summary_pr_auc["local_only_global_test"] = _stats(local_global_prs)
    summary_pr_auc["local_only_local_slice"] = _stats(local_slice_prs)

    # Lift metrics:
    fedprox_pr = summary_pr_auc["federated_fedprox"]["mean"]
    cent_pr = summary_pr_auc["centralized"]["mean"]
    local_pr = summary_pr_auc["local_only_global_test"]["mean"]
    uniform_pr = summary_pr_auc["federated_uniform"]["mean"]

    collaboration_lift = round(fedprox_pr - local_pr, 5)
    centralized_parity_pct = round((fedprox_pr / cent_pr) * 100.0, 2) if cent_pr > 0 else 0.0
    fedprox_over_uniform_lift = round(fedprox_pr - uniform_pr, 5)

    full_result = {
        "dataset": dataset_name,
        "k_clients": k,
        "partition_type": partition_type,
        "client_summaries": part_res.client_summaries,
        "seeds": list(seeds),
        "summary_pr_auc": summary_pr_auc,
        "summary_f1": summary_f1,
        "collaboration_lift_pr_auc": collaboration_lift,
        "centralized_parity_pct": centralized_parity_pct,
        "fedprox_over_uniform_lift": fedprox_over_uniform_lift,
        "per_seed_runs": per_seed_runs,
    }

    # Save to results/<dataset>/federated.json
    out_dir = REPO_ROOT / "results" / dataset_name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"federated_{partition_type}_k{k}.json"
    out_file.write_text(json.dumps(full_result, indent=2), encoding="utf-8")
    
    # Also save to main federated.json if primary partition
    if partition_type == "account_cluster" and k == 4:
        (out_dir / "federated.json").write_text(json.dumps(full_result, indent=2), encoding="utf-8")

    log.info("[%s] RESULTS: Centralized PR-AUC=%.4f, Local-Only=%.4f, FedProx=%.4f (Parity=%.1f%%, Collab Lift=+%.4f)",
             dataset_name, cent_pr, local_pr, fedprox_pr, centralized_parity_pct, collaboration_lift)

    return full_result


def run_cross_dataset_experiment(
    seeds: tuple[int, ...] = (42, 43, 44),
    target_names: Sequence[str] = ("banksim", "synth_erp"),
) -> dict:
    """Stress-test: Cross-dataset federation where different datasets act as distinct banks."""
    log.info("Running Cross-Dataset Federation Stress Test across %s", target_names)
    
    # Load and align shared features with time conversion
    dfs: dict[str, pd.DataFrame] = {}
    manifests: dict[str, dict] = {}
    
    for name in target_names:
        proc = Path(get_dataset(name)["processed_dir"])
        with open(proc / "features_manifest.json", encoding="utf-8") as f:
            manifests[name] = json.load(f)
        path = proc / manifests[name]["output"]
        df_i = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
        
        # Scale time features to days
        scale = TIME_SCALE[name]
        for c in TIME_COLS:
            if c in df_i.columns:
                df_i[c] = df_i[c] * scale
        dfs[name] = df_i

    # Shared feature intersection
    common_ord = set.intersection(*[set(m["ordinary_cols"]) for m in manifests.values()])
    common_topo = set.intersection(*[set(m["topology_cols"]) for m in manifests.values()])
    shared_features = sorted(list(common_ord | common_topo))
    log.info("Cross-dataset shared feature space: %d features (%s)", len(shared_features), shared_features)

    # Keep only shared features + essential keys
    keep_cols = ["transaction_id", "timestamp", "label"] + shared_features
    aligned_dfs = {name: dfs[name][keep_cols].copy() for name in target_names}

    unified_df, part_res = partition_cross_dataset(aligned_dfs)
    log.info("Cross-dataset unified table: %d rows across %d clients", len(unified_df), part_res.k)

    per_seed_runs = []
    for s in seeds:
        run_res = run_federated_single_seed(
            unified_df,
            shared_features,
            part_res,
            seed=s,
            partition=part_res.client_ids,
        )
        per_seed_runs.append(run_res)

    arms = ["centralized", "federated_uniform", "federated_fedprox", "federated_size_weighted"]
    summary_pr_auc = {}
    for arm in arms:
        pr_vals = [r[arm]["pr_auc"] for r in per_seed_runs]
        summary_pr_auc[arm] = _stats(pr_vals)

    local_global_prs = [r["local_only"]["avg_global_test_pr_auc"] for r in per_seed_runs]
    summary_pr_auc["local_only_global_test"] = _stats(local_global_prs)

    cross_res = {
        "datasets": list(target_names),
        "shared_features": shared_features,
        "client_summaries": part_res.client_summaries,
        "seeds": list(seeds),
        "summary_pr_auc": summary_pr_auc,
        "per_seed_runs": per_seed_runs,
    }

    out_dir = REPO_ROOT / "results" / "cross_dataset"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "federated_stress_test.json"
    out_file.write_text(json.dumps(cross_res, indent=2), encoding="utf-8")
    log.info("Cross-dataset results written to %s", out_file)
    return cross_res


def run_sensitivity_experiment(
    dataset_name: str,
    k_range: Sequence[int] = (2, 3, 4, 5),
    seeds: tuple[int, ...] = (42, 43, 44),
) -> dict:
    """Evaluate federation sensitivity across varying number of client institutions K."""
    log.info("Running K-Sensitivity Experiment on [%s] for K in %s", dataset_name, k_range)
    sensitivity_results = {}
    for k in k_range:
        res = run_federated_experiment(dataset_name, k=k, seeds=seeds, partition_type="account_cluster")
        sensitivity_results[f"k_{k}"] = {
            "k": k,
            "centralized_pr_auc": res["summary_pr_auc"]["centralized"]["mean"],
            "local_only_pr_auc": res["summary_pr_auc"]["local_only_global_test"]["mean"],
            "fedprox_pr_auc": res["summary_pr_auc"]["federated_fedprox"]["mean"],
            "uniform_pr_auc": res["summary_pr_auc"]["federated_uniform"]["mean"],
            "collaboration_lift": res["collaboration_lift_pr_auc"],
            "centralized_parity_pct": res["centralized_parity_pct"],
        }

    out_dir = REPO_ROOT / "results" / dataset_name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "federated_sensitivity_k.json"
    out_file.write_text(json.dumps(sensitivity_results, indent=2), encoding="utf-8")
    log.info("[%s] Sensitivity results written to %s", dataset_name, out_file)
    return sensitivity_results


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="subcommand")

    # Command: run dataset
    run_parser = subparsers.add_parser("run", help="Run intra-dataset federated experiment")
    run_parser.add_argument("dataset", choices=["banksim", "synth_erp", "sap_wurzburg", "ibm_aml_kaggle"])
    run_parser.add_argument("--k", type=int, default=4, help="Number of client banks")
    run_parser.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44], help="Random seeds")
    run_parser.add_argument("--partition", choices=["account_cluster", "random_iid"], default="account_cluster")

    # Command: cross_dataset
    cross_parser = subparsers.add_parser("cross_dataset", help="Run cross-dataset federation stress test")
    cross_parser.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44])

    # Command: sensitivity
    sens_parser = subparsers.add_parser("sensitivity", help="Run K-sensitivity analysis")
    sens_parser.add_argument("dataset", choices=["banksim", "synth_erp"])
    sens_parser.add_argument("--k_range", type=int, nargs="+", default=[2, 3, 4, 5])
    sens_parser.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44])

    args = parser.parse_args()

    if args.subcommand == "run":
        run_federated_experiment(args.dataset, k=args.k, seeds=tuple(args.seeds), partition_type=args.partition)
    elif args.subcommand == "cross_dataset":
        run_cross_dataset_experiment(seeds=tuple(args.seeds))
    elif args.subcommand == "sensitivity":
        run_sensitivity_experiment(args.dataset, k_range=args.k_range, seeds=tuple(args.seeds))
    else:
        # Default shorthand: python -m experiments.federated banksim
        if len(sys.argv) > 1 and sys.argv[1] in ["banksim", "synth_erp", "sap_wurzburg"]:
            run_federated_experiment(sys.argv[1], k=4, seeds=(42, 43, 44), partition_type="account_cluster")
        else:
            parser.print_help()


if __name__ == "__main__":
    main()
