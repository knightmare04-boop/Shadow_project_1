"""Online (one-transaction-at-a-time) topology feature computation.

This is NOT a reimplementation of the research engine's algorithm — it
reuses `topology.window_graph.WindowGraph` and `topology.lap_memory.LapMemory`
directly, the exact same classes `topology.engine.extract_features` uses for
the batch/offline pipeline. What differs is only the *driver loop*: instead
of iterating a pre-loaded DataFrame and discarding the graph at the end,
`OnlineTopologyState` holds one WindowGraph + two LapMemory instances alive
across calls, one call per live transaction, so the next transaction's
features can be computed without replaying the whole history.

Correctness is the entire point of this class — the read-then-insert order
below is copied line-for-line from `topology.engine.extract_features`
(same source read as fan_in/fan_out, same cycle search, same lap-memory
recurrence, edge inserted only AFTER features are read). A parity test
(tests/test_online_topology_parity.py) replays a real dataset through both
paths and asserts every feature column matches exactly, row for row.

Persistence: `snapshot()` / `restore()` pickle the graph + lap memories +
the incremental account-id factorization map, so an app restart resumes
mid-window rather than starting cold (Module 5 plan, Stage A: "state
snapshotted to Postgres so a restart doesn't lose the window").
"""
from __future__ import annotations

import pickle
from dataclasses import dataclass, field

from topology.engine import FEATURE_COLS
from topology.lap_memory import LapMemory
from topology.window_graph import WindowGraph


@dataclass
class OnlineTopologyState:
    window: int | float | None
    max_cycle_len: int = 6
    search_budget: int = 4000
    lap_memory: int = 25
    lap_tol: float = 0.01

    graph: WindowGraph = field(init=False)
    in_lap: LapMemory = field(init=False)   # dest's recent INCOMING amounts
    out_lap: LapMemory = field(init=False)  # source's recent OUTGOING amounts
    account_ids: dict = field(default_factory=dict)
    _next_id: int = 0

    def __post_init__(self) -> None:
        self.graph = WindowGraph(self.window)
        self.in_lap = LapMemory(self.lap_memory, self.lap_tol)
        self.out_lap = LapMemory(self.lap_memory, self.lap_tol)

    def _factorize(self, account: str) -> int:
        """Incremental string->int account id. Unlike the batch engine's
        `pd.factorize` over the whole edge table, this assigns ids as new
        accounts are first seen — order-dependent but internally consistent,
        which is all WindowGraph/LapMemory need (they only compare ids to
        each other, never to a global ordering)."""
        acc_id = self.account_ids.get(account)
        if acc_id is None:
            acc_id = self._next_id
            self.account_ids[account] = acc_id
            self._next_id += 1
        return acc_id

    def score_transaction(self, *, ts: int | float, source_account: str,
                          dest_account: str, amount: float) -> dict:
        """Returns the 13 topology feature columns for ONE new transaction,
        in the exact same read-then-insert order as
        `topology.engine.extract_features`'s loop body. Mutates state:
        the transaction is added to the graph/lap-memory AFTER its features
        are read, so it can never see itself."""
        u = self._factorize(source_account)
        v = self._factorize(dest_account)
        g = self.graph
        g.evict(ts)

        feats = {c: 0 for c in FEATURE_COLS}
        feats["cycle_amount_ratio"] = float("nan")
        feats["cycle_time_span"] = float("nan")

        feats["fan_in"] = g.fan_in(v)
        feats["fan_out"] = g.fan_out(u)
        feats["dest_in_degree"] = g.in_degree(v)
        feats["src_out_degree"] = g.out_degree(u)

        if u == v:
            feats["in_cycle"] = 1
            feats["cycle_length"] = 1
        else:
            res = g.cycle_features(v, u, self.max_cycle_len, self.search_budget)
            if res is not None:
                length, p_min_amt, p_max_amt, p_min_ts = res
                feats["in_cycle"] = 1
                feats["cycle_length"] = length
                if length >= 3:
                    feats["in_cycle_ge3"] = 1
                lo = amount if amount < p_min_amt else p_min_amt
                hi = amount if amount > p_max_amt else p_max_amt
                if hi > 0:
                    feats["cycle_amount_ratio"] = lo / hi
                feats["cycle_time_span"] = ts - p_min_ts

        feats["lap_in_recur"], feats["lap_in_payers"] = self.in_lap.recurrence(v, amount)
        feats["lap_out_recur"], feats["lap_out_payees"] = self.out_lap.recurrence(u, amount)

        # Insert only now — mirrors the batch engine's leakage-safety invariant.
        g.add(ts, u, v, amount)
        self.in_lap.record(v, amount, u)
        self.out_lap.record(u, amount, v)

        return feats

    # ---- persistence --------------------------------------------------------
    #
    # `topology.lap_memory.LapMemory` builds its dict with
    # `defaultdict(lambda: deque(maxlen=k))` — a closure, which stdlib
    # `pickle` cannot serialize ("Can't get local object ...<locals>.<lambda>").
    # `WindowGraph` uses only `defaultdict(dict)` / `defaultdict(int)` (plain
    # picklable type references), so it pickles directly. Rather than modify
    # the locked research module for our own persistence needs, LapMemory is
    # snapshotted by hand: k, tol, and a plain dict copy of its deques (the
    # deques themselves ARE picklable; only the defaultdict's factory isn't).
    @staticmethod
    def _snapshot_lap(lap: LapMemory) -> dict:
        return {"k": lap.k, "tol": lap.tol, "mem": dict(lap.mem)}

    @staticmethod
    def _restore_lap(data: dict) -> LapMemory:
        lap = LapMemory(data["k"], data["tol"])
        lap.mem.update(data["mem"])  # falls back into the fresh defaultdict's own lambda
        return lap

    def snapshot(self) -> bytes:
        return pickle.dumps({
            "window": self.window, "max_cycle_len": self.max_cycle_len,
            "search_budget": self.search_budget, "lap_memory": self.lap_memory,
            "lap_tol": self.lap_tol, "graph": self.graph,
            "in_lap": self._snapshot_lap(self.in_lap),
            "out_lap": self._snapshot_lap(self.out_lap),
            "account_ids": self.account_ids, "_next_id": self._next_id,
        })

    @classmethod
    def restore(cls, blob: bytes) -> "OnlineTopologyState":
        data = pickle.loads(blob)
        state = cls(
            window=data["window"], max_cycle_len=data["max_cycle_len"],
            search_budget=data["search_budget"], lap_memory=data["lap_memory"],
            lap_tol=data["lap_tol"],
        )
        state.graph = data["graph"]
        state.in_lap = cls._restore_lap(data["in_lap"])
        state.out_lap = cls._restore_lap(data["out_lap"])
        state.account_ids = data["account_ids"]
        state._next_id = data["_next_id"]
        return state
