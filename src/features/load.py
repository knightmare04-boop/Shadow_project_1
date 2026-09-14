"""Shared model-table loader — the single place the feature table meets the TGN
embeddings.

Every consumer (experiments/modern.py, experiments/final.py, modeling/score.py,
modeling/alerts.py) must load through here so they all see the identical table:
same string ids, same duplicate-id policy, same strict one-to-one merge, same
stable time ordering. In particular the SAP `run_id` partition series must be
taken from the *post-merge* frame — `split_partition` below is the single source.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

from common.config import get_dataset

log = logging.getLogger(__name__)


def load_model_table(name: str, *, with_tgn: bool = True, tgn_epochs: int = 3
                     ) -> tuple[pd.DataFrame, dict, list[str]]:
    """Load features_model (+ optionally merge the TGN embeddings).

    Returns (df, manifest, tgn_cols); tgn_cols is [] when with_tgn=False.
    The frame is stably sorted by timestamp with a fresh index.
    """
    proc = Path(get_dataset(name)["processed_dir"])
    with open(proc / "features_manifest.json", encoding="utf-8") as f:
        manifest = json.load(f)
    path = proc / manifest["output"]
    df = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
    df["transaction_id"] = df["transaction_id"].astype(str)

    tgn_cols: list[str] = []
    if with_tgn:
        from modeling.tgn import build_embeddings  # deferred: torch import is heavy
        tgn_path = build_embeddings(name, epochs=tgn_epochs)  # reuses cached parquet
        tgn = pd.read_parquet(tgn_path)
        tgn_cols = [c for c in tgn.columns if c != "transaction_id"]
        tgn["transaction_id"] = tgn["transaction_id"].astype(str)
        # transaction_id is not unique on every dataset (SAP repeats a doc:position
        # id across 29 edges, which also cartesian-inflated features_model by 58
        # rows). Rows with an ambiguous id cannot be paired with their embedding,
        # so they are dropped from BOTH sides (<0.03% of SAP; zero elsewhere)
        # before a strict one-to-one merge. All consumers share this identical
        # table, so comparisons are unaffected.
        dup = (set(df["transaction_id"][df["transaction_id"].duplicated(keep=False)])
               | set(tgn["transaction_id"][tgn["transaction_id"].duplicated(keep=False)]))
        if dup:
            n_before = len(df)
            df = df[~df["transaction_id"].isin(dup)]
            tgn = tgn[~tgn["transaction_id"].isin(dup)]
            log.warning("[%s] dropped %d rows with non-unique transaction_id "
                        "(cannot pair with embeddings)", name, n_before - len(df))
        df = df.merge(tgn, on="transaction_id", how="inner", validate="one_to_one")

    df = df.sort_values("timestamp", kind="stable").reset_index(drop=True)
    return df, manifest, tgn_cols


def split_partition(df: pd.DataFrame) -> pd.Series | None:
    """The partition series for time_split, taken from the post-merge frame.

    SAP's synthetic time axis is only ordered *within* a run, so its split must
    be per-`run_id`; every other dataset returns None (global chronological split).
    """
    return df["run_id"] if "run_id" in df.columns else None
