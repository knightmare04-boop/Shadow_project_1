"""HPO invariants: determinism, config-0 = locked defaults, low-fraud guard."""
import numpy as np
import pandas as pd

from modeling.harness import DEFAULT_XGB_PARAMS
from modeling.hpo import FOCAL_GAMMA_SPACE, SEARCH_SPACE, random_search, sample_configs


def test_config0_is_locked_defaults():
    for mech in ("class_weight", "focal"):
        cfgs = sample_configs(5, seed=42, imbalance=mech)
        assert cfgs[0]["xgb_params"] == DEFAULT_XGB_PARAMS
        assert cfgs[0]["focal_gamma"] == 2.0


def test_sampling_is_deterministic_and_in_space():
    a = sample_configs(10, seed=42, imbalance="focal")
    b = sample_configs(10, seed=42, imbalance="focal")
    assert a == b
    for cfg in a[1:]:
        p = cfg["xgb_params"]
        for key, space in SEARCH_SPACE.items():
            if isinstance(space, list):
                assert p[key] in space
            else:
                _, lo, hi = space
                assert lo <= p[key] <= hi
        assert cfg["focal_gamma"] in FOCAL_GAMMA_SPACE


def test_low_fraud_guard_skips_search():
    rng = np.random.default_rng(1)
    n = 2000
    df = pd.DataFrame({
        "timestamp": np.arange(n) // 10,
        "x1": rng.normal(size=n),
        "label": np.zeros(n, dtype=int),
    })
    df.loc[df.index[:30], "label"] = 1     # all frauds in the earliest rows ->
    out = random_search(df, ["x1"], imbalance="class_weight", n_configs=3)
    assert out["hpo_skipped"] is True      # val split holds ~0 frauds
    assert out["best_params"] == DEFAULT_XGB_PARAMS
    assert out["trials"] == []
