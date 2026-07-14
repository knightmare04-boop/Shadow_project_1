"""base — shared machinery for the synthetic generator (buffer, time, amounts).

Design notes:
  * Everything is driven by one ``numpy`` ``Generator`` per module (spawned from
    the master seed), so the dataset is a pure function of (config, seed, code).
  * Timestamps are integer SECONDS from day 0 (day 0 is a Monday). Day/hour
    structure is real: weekday/weekend rhythms, business hours, month-end and
    seasonal effects — richer than any of the real sets (IBM has whole days,
    PaySim hours), which downstream code may but need not exploit.
  * Amounts use a median/sigma lognormal parameterization: heavy-tailed,
    strictly positive, and a mixture of many flows — which is what makes real
    ledgers approximately Benford (Nigrini) without us ever targeting Benford.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "config" / "synthetic.yaml"

DAY = 86400  # seconds


def load_synth_config(path: str | Path | None = None) -> dict:
    with open(Path(path) if path else DEFAULT_CONFIG, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def lognorm(rng: np.random.Generator, median: float, sigma: float, size=None):
    """Lognormal draw(s) parameterized by MEDIAN (not mean) and log-sigma."""
    return rng.lognormal(mean=np.log(median), sigma=sigma, size=size)


def uniform(rng: np.random.Generator, lo_hi, size=None):
    lo, hi = lo_hi
    return rng.uniform(lo, hi, size=size)


def randint(rng: np.random.Generator, lo_hi) -> int:
    lo, hi = lo_hi
    return int(rng.integers(lo, hi + 1))


# ---- calendar ----------------------------------------------------------------

def day_weights(cfg: dict, monthend: bool = False) -> np.ndarray:
    """Relative activity weight of each simulated day (weekday x season x
    optional month-end bump). Day 0 is a Monday; months are 30-day blocks —
    a simplification that still produces a visible month-end cycle."""
    act = cfg["activity"]
    days = int(cfg["days"])
    d = np.arange(days)
    w = np.asarray(act["weekday_weights"], dtype=float)[d % 7].copy()
    sb = act["season_bump"]
    w[(d >= sb["start_day"]) & (d <= sb["end_day"])] *= sb["factor"]
    if monthend:
        dom = d % 30
        is_end = dom >= 27
        is_weekday = (d % 7) < 5
        w[is_end & is_weekday] *= act["monthend_factor"]
    return w


def sample_days(rng: np.random.Generator, weights: np.ndarray, n: int) -> np.ndarray:
    p = weights / weights.sum()
    return rng.choice(len(weights), size=n, p=p)


def business_seconds(rng: np.random.Generator, n: int) -> np.ndarray:
    """Time-of-day for office-driven events: morning + afternoon peaks."""
    pick = rng.random(n) < 0.55
    hrs = np.where(pick, rng.normal(10.8, 1.7, n), rng.normal(15.2, 1.9, n))
    return (np.clip(hrs, 7.0, 19.5) * 3600).astype(np.int64)


def consumer_seconds(rng: np.random.Generator, n: int) -> np.ndarray:
    """Time-of-day for consumer purchases: daytime + an evening bump."""
    pick = rng.random(n) < 0.6
    hrs = np.where(pick, rng.normal(13.0, 3.2, n), rng.normal(19.0, 2.2, n))
    return (np.clip(hrs, 8.0, 23.0) * 3600).astype(np.int64)


def anytime_seconds(rng: np.random.Generator, n: int) -> np.ndarray:
    """Automated / online events: any hour, mild daytime bias."""
    hrs = np.mod(rng.normal(14.0, 6.0, n), 24.0)
    return (hrs * 3600).astype(np.int64)


# ---- the event buffer ----------------------------------------------------------

class EventBuffer:
    """Columnar accumulator for transactions. Appends numpy chunks; concatenates
    once at the end. Fraud rows carry the scenario id + typology (provenance)."""

    def __init__(self):
        self.ts: list[np.ndarray] = []
        self.src: list[np.ndarray] = []
        self.dst: list[np.ndarray] = []
        self.amt: list[np.ndarray] = []
        self.typ: list[np.ndarray] = []
        self.alert_id: list[np.ndarray] = []
        self.alert_type: list[np.ndarray] = []

    def add(self, ts, src, dst, amt, tx_type,
            alert_id: str | None = None, alert_type: str | None = None) -> int:
        """Append a chunk. ``src``/``dst`` may be scalars or arrays; ``tx_type``
        is one string per chunk. Returns the number of events appended."""
        ts = np.asarray(ts, dtype=np.int64)
        n = ts.size
        if n == 0:
            return 0
        self.ts.append(ts)
        self.src.append(np.broadcast_to(np.asarray(src, dtype=object), (n,)).copy()
                        if np.asarray(src).ndim == 0 else np.asarray(src, dtype=object))
        self.dst.append(np.broadcast_to(np.asarray(dst, dtype=object), (n,)).copy()
                        if np.asarray(dst).ndim == 0 else np.asarray(dst, dtype=object))
        self.amt.append(np.round(np.maximum(np.asarray(amt, dtype=float), 0.01), 2))
        self.typ.append(np.full(n, tx_type, dtype=object))
        self.alert_id.append(np.full(n, alert_id if alert_id else "", dtype=object))
        self.alert_type.append(np.full(n, alert_type if alert_type else "", dtype=object))
        return n

    def arrays(self) -> dict[str, np.ndarray]:
        return {
            "TIMESTAMP": np.concatenate(self.ts),
            "SOURCE_ACCOUNT": np.concatenate(self.src),
            "DEST_ACCOUNT": np.concatenate(self.dst),
            "AMOUNT": np.concatenate(self.amt),
            "TX_TYPE": np.concatenate(self.typ),
            "ALERT_ID": np.concatenate(self.alert_id),
            "ALERT_TYPE": np.concatenate(self.alert_type),
        }
