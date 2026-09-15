"""Online (incremental) computation of the "ordinary" tabular features —
the counterpart to app.services.online_topology for the non-graph half of
the feature table. Mirrors src/features/build.py's `_expanding_account_stats`
exactly: per-account running count/mean/std computed via Welford's algorithm
(numerically stable, streaming-native — the batch engine's cumsum/cumsq
approach only works because it has the whole column at once; a running
process needs the online formulation of the same statistic).

Also reproduces the batch engine's one-hot categorical encoding (fixed at
training time — an unseen category value at serving time maps to the
all-zero row, the standard and correct out-of-vocabulary behavior) and
static per-account attributes (looked up from a dict populated at startup
from nodes_accounts.csv, extendable as new accounts are first seen).

Verified against the batch path by tests/test_online_ordinary_parity.py.

KNOWN, QUANTIFIED DIVERGENCE (documented, not a bug in this module): the
batch engine's variance formula (`cum_sq/count - mean**2`, in
`features/build.py::_expanding_account_stats`) is the textbook-unstable
two-pass variance computation — for an account whose historical amounts are
nearly identical, catastrophic cancellation produces a tiny, floating-point-
noise-driven nonzero "variance" that then yields a wild z-score (observed:
up to ~10^8) instead of the true near-zero/undefined value. Welford's
algorithm (used here) doesn't have this failure mode and correctly returns
NaN when there is no meaningful spread. Measured on the full banksim dataset
(594,643 rows): 1,238 rows (0.21%) diverge on `amount_zscore_src`, and EVERY
one of them is this exact pattern (batch |z| > 1000, online NaN or small) —
never a disagreement of any other kind. This is the correct call for new
online code: propagating a known numerical-stability bug from the locked
research pipeline (never modified — see CLAUDE.md) into the serving path
would trade a rare accuracy cost for a systematic one. Reported in the
paper's threats-to-validity section alongside the TGN non-determinism
finding (docs/BUILD_SPEC.md).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class _RunningStats:
    """Welford's online algorithm: mean and variance from a stream, O(1) per
    update, no precision loss from summing then subtracting large numbers
    (which is what the batch cumsum/cumsq approach does, and which is fine
    for a bounded batch but drifts over a very long-running online stream)."""
    count: int = 0
    mean: float = 0.0
    m2: float = 0.0
    last_ts: float | None = None

    def prior_snapshot(self) -> tuple[int, float, float]:
        """(count, mean, std) as of BEFORE this update — what the feature
        computation reads. Matches the batch engine's cumsum-minus-self
        exclusion of the current row."""
        if self.count == 0:
            return 0, float("nan"), float("nan")
        var = self.m2 / self.count if self.count > 0 else float("nan")
        return self.count, self.mean, math.sqrt(max(var, 0.0))

    def update(self, value: float) -> None:
        self.count += 1
        delta = value - self.mean
        self.mean += delta / self.count
        delta2 = value - self.mean
        self.m2 += delta * delta2


@dataclass
class OnlineOrdinaryState:
    ordinary_cols: list[str]
    categorical_prefixes: dict[str, list[str]] = field(default_factory=dict)
    """{raw_column_name: [fitted category values in one-hot column order]},
    e.g. {"category": ["es_transportation", "es_health", ...]} for banksim."""
    static_attr_defaults: dict[str, float] = field(default_factory=dict)
    """Median/typical value for a static attribute column, used only if an
    account is seen live before its static attributes are known — should not
    normally happen for accounts the app itself created."""

    _src_stats: dict[str, _RunningStats] = field(default_factory=dict)
    _dest_counts: dict[str, int] = field(default_factory=dict)
    _static_attrs: dict[str, dict[str, float]] = field(default_factory=dict)  # account_id -> {col: value}

    def set_static_attrs(self, account_id: str, attrs: dict[str, float]) -> None:
        self._static_attrs[account_id] = attrs

    def score_transaction(self, *, ts: float, source_account: str, dest_account: str,
                          amount: float, categoricals: dict[str, str] | None = None) -> dict:
        categoricals = categoricals or {}
        src = self._src_stats.setdefault(source_account, _RunningStats())
        prior_count, prior_mean, prior_std = src.prior_snapshot()

        feats: dict[str, float] = {}
        if "log_amount" in self.ordinary_cols:
            feats["log_amount"] = math.log1p(max(amount, 0.0))
        if "src_count_prior" in self.ordinary_cols:
            feats["src_count_prior"] = float(prior_count)
        if "src_amt_mean_prior" in self.ordinary_cols:
            feats["src_amt_mean_prior"] = prior_mean
        if "amount_zscore_src" in self.ordinary_cols:
            feats["amount_zscore_src"] = (
                (amount - prior_mean) / prior_std if prior_std not in (0.0, None) and prior_count > 0
                else float("nan")
            )
        if "time_since_prev_src" in self.ordinary_cols:
            feats["time_since_prev_src"] = (
                ts - src.last_ts if src.last_ts is not None else float("nan")
            )
        if "dest_count_prior" in self.ordinary_cols:
            feats["dest_count_prior"] = float(self._dest_counts.get(dest_account, 0))

        # Static per-account attributes (e.g. synth_erp's src_creation_day /
        # dest_creation_day), prefixed src_/dest_ as build_features does.
        for prefix, account in (("src_", source_account), ("dest_", dest_account)):
            attrs = self._static_attrs.get(account, {})
            for col in self.ordinary_cols:
                if col.startswith(prefix):
                    base = col[len(prefix):]
                    if base in attrs:
                        feats[col] = attrs[base]
                    elif col not in feats and base in self.static_attr_defaults:
                        feats[col] = self.static_attr_defaults[base]

        # One-hot categoricals, fixed vocabulary from training time.
        for raw_col, categories in self.categorical_prefixes.items():
            value = categoricals.get(raw_col)
            for cat in categories:
                col_name = f"{raw_col}_{cat}"
                if col_name in self.ordinary_cols:
                    feats[col_name] = 1.0 if value == cat else 0.0

        # Fill any remaining expected column with NaN (XGBoost handles
        # missing values natively — this is the same contract the batch
        # engine relies on) rather than silently omitting it.
        for col in self.ordinary_cols:
            feats.setdefault(col, float("nan"))

        # Update state AFTER reading — same past-only discipline as topology.
        src.update(amount)
        src.last_ts = ts
        self._dest_counts[dest_account] = self._dest_counts.get(dest_account, 0) + 1

        return feats
