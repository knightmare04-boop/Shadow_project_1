"""Bundle round-trip: a persisted model must rescore to its recorded metrics.

The dangerous path is focal: a model reloaded from model.json has lost its
Python objective, so predict_proba on it is wrong — score.py must go raw margin
-> sigmoid (bundle score_fn == "sigmoid_margin"). This test trains tiny models
with BOTH mechanisms on synthetic data, persists them, reloads through
modeling.score, and checks the recomputed test PR-AUC against the bundle.
"""
import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import average_precision_score

import modeling.harness as harness
from modeling.harness import time_split, train_and_evaluate
from modeling.score import load_bundle, score_frame


@pytest.fixture()
def synth_df() -> pd.DataFrame:
    rng = np.random.default_rng(0)
    n = 6000
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    logits = -4.2 + 2.0 * x1 + 1.0 * x2
    y = (rng.uniform(size=n) < 1 / (1 + np.exp(-logits))).astype(int)
    return pd.DataFrame({
        "transaction_id": [str(i) for i in range(n)],
        "timestamp": np.arange(n) // 10,   # 10 rows per "day"
        "x1": x1, "x2": x2,
        "noise": rng.normal(size=n),
        "label": y,
    })


@pytest.mark.parametrize("imbalance", ["class_weight", "focal"])
def test_roundtrip(tmp_path, monkeypatch, synth_df, imbalance):
    monkeypatch.setattr(harness, "REPO_ROOT", tmp_path)  # artifacts go to tmp
    cols = ["x1", "x2", "noise"]
    res = train_and_evaluate(synth_df, cols, imbalance=imbalance,
                             persist_as=f"synth/{imbalance}")
    sb = load_bundle(tmp_path / "artifacts" / "synth" / imbalance)

    assert sb.bundle["schema_version"] == 2
    assert sb.bundle["score_fn"] == ("sigmoid_margin" if imbalance == "focal"
                                     else "proba")
    assert sb.features == cols

    _, _, test = time_split(synth_df["timestamp"])
    part = synth_df[test].reset_index(drop=True)
    scored = score_frame(sb, part)
    got = round(float(average_precision_score(part["label"], scored["score"])), 5)
    assert abs(got - res["test"]["pr_auc"]) <= 1e-4, (
        f"reloaded {imbalance} model rescored {got}, "
        f"recorded {res['test']['pr_auc']}")
    # threshold decisions are reproducible too
    assert (scored["alert"] == (scored["score"] >= sb.threshold)).all()
