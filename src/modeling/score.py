"""Inference entry point — load a persisted bundle and score rows.

The bundle (schema v2, written by the harness) is self-describing: feature list
and order, decision threshold, imbalance mechanism, and ``score_fn``. Scoring is
uniform: XGBoost's raw margin + sigmoid. For a class-weight model
(binary:logistic) sigmoid(margin) IS predict_proba; for a focal model the saved
model.json has lost its Python objective, so the margin+sigmoid path is the only
correct one — never call predict_proba on a reloaded focal model.

Run:  python -m modeling.score banksim --artifact final --split test --verify
"""
from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

from features.load import load_model_table, split_partition
from modeling.harness import REPO_ROOT, time_split
from modeling.objectives import sigmoid

log = logging.getLogger(__name__)


@dataclass
class ScoringBundle:
    booster: xgb.Booster
    bundle: dict
    artifact_dir: Path

    @property
    def features(self) -> list[str]:
        return self.bundle["features"]

    @property
    def threshold(self) -> float:
        return self.bundle["threshold"]

    @property
    def feature_families(self) -> dict:
        return self.bundle.get("feature_families", {})

    @property
    def iteration_range(self) -> tuple[int, int]:
        """Trees to use at prediction time. The model was early-stopped: the
        in-training sklearn wrapper predicted with best_iteration trees, but a
        reloaded Booster uses ALL trees unless told otherwise — which silently
        changes every score. (0, 0) means all trees (no early stop recorded)."""
        best = self.bundle.get("best_iteration", -1)
        return (0, best + 1) if best is not None and best >= 0 else (0, 0)


def load_bundle(artifact_dir: str | Path) -> ScoringBundle:
    art = Path(artifact_dir)
    if not art.is_absolute():
        art = REPO_ROOT / art
    with open(art / "bundle.json", encoding="utf-8") as f:
        bundle = json.load(f)
    booster = xgb.Booster()
    booster.load_model(str(art / "model.json"))
    return ScoringBundle(booster=booster, bundle=bundle, artifact_dir=art)


def _dmatrix(sb: ScoringBundle, df: pd.DataFrame) -> xgb.DMatrix:
    """DMatrix in the EXACT bundle feature order (order sensitivity is real)."""
    missing = [c for c in sb.features if c not in df.columns]
    if missing:
        raise ValueError(f"frame is missing bundle features: {missing[:8]}"
                         f"{'...' if len(missing) > 8 else ''}")
    X = df[sb.features]
    return xgb.DMatrix(X, feature_names=sb.features)


def score_frame(sb: ScoringBundle, df: pd.DataFrame) -> pd.DataFrame:
    """Score rows -> [transaction_id, score, alert]. Uniform margin+sigmoid path."""
    margin = sb.booster.predict(_dmatrix(sb, df), output_margin=True,
                                iteration_range=sb.iteration_range)
    score = sigmoid(np.asarray(margin, dtype=np.float64))
    out = pd.DataFrame({
        "transaction_id": df["transaction_id"].astype(str).to_numpy(),
        "score": score,
        "alert": score >= sb.threshold,
    })
    return out


def score_dataset(name: str, artifact: str = "final", split: str = "test",
                  verify: bool = False) -> pd.DataFrame:
    """Reload a persisted model and score one chronological split of a dataset.

    ``verify=True`` recomputes the split PR-AUC and asserts it matches the value
    recorded in the bundle at persist time — the bundle round-trip test.
    """
    sb = load_bundle(Path("artifacts") / name / artifact)
    df, _, _ = load_model_table(name)
    masks = dict(zip(("train", "val", "test"),
                     time_split(df["timestamp"], partition=split_partition(df))))
    if split not in masks:
        raise ValueError(f"split must be one of {list(masks)}, got {split!r}")
    part = df[masks[split]].reset_index(drop=True)
    scored = score_frame(sb, part)
    scored["label"] = part["label"].astype(int).to_numpy()
    scored["timestamp"] = part["timestamp"].to_numpy()

    if verify:
        from sklearn.metrics import average_precision_score
        got = round(float(average_precision_score(scored["label"], scored["score"])), 5)
        want = sb.bundle.get("metrics", {}).get(split, {}).get("pr_auc")
        if want is None:
            log.warning("bundle has no recorded %s PR-AUC to verify against", split)
        elif abs(got - want) > 1e-4:
            raise AssertionError(
                f"round-trip FAILED: recomputed {split} PR-AUC {got} != bundle {want}")
        else:
            log.info("round-trip OK: %s PR-AUC %.5f matches bundle", split, got)
    return scored


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--artifact", default="final")
    ap.add_argument("--split", default="test", choices=("train", "val", "test"))
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--out", default=None, help="optional CSV path for the scores")
    a = ap.parse_args()
    scored = score_dataset(a.dataset, artifact=a.artifact, split=a.split,
                           verify=a.verify)
    n_alert = int(scored["alert"].sum())
    print(f"{a.dataset}/{a.artifact} [{a.split}]: {len(scored)} rows scored, "
          f"{n_alert} alerts")
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        scored.to_csv(a.out, index=False)
        print(f"wrote {a.out}")
