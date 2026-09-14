"""Graph-evidence reconstruction for audit alerts — replay, don't re-engineer.

The streaming engine (topology/engine.py) stores per-transaction *features*
(``in_cycle``, ``cycle_length``, ``fan_in``...), not the underlying paths — the
paths of a handful of flagged transactions are not worth persisting for millions
of rows. This module replays the same as-of stream (same ordering, same window,
same partition resets, same factorization) and, for the requested transactions
only, captures the actual evidence from the past-only graph state *before* the
transaction is inserted:

  * the shortest cycle the transaction closes (``WindowGraph.cycle_path`` — the
    same BFS that produced the stored features), and
  * the distinct senders behind its destination's fan-in.

Leakage note: this layer only *explains* already-computed features; it reads the
graph at exactly the same point in the stream the engine did, so the evidence is
as-of by construction.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from common.config import get_dataset
from topology.engine import resolve_params
from topology.window_graph import WindowGraph

log = logging.getLogger(__name__)

MAX_FAN_IN_SENDERS = 25  # cap the fan-in evidence list (most recent first)


def reconstruct_evidence(name: str, tx_ids: set[str],
                         config_path: str | None = None) -> dict[str, dict]:
    """One replay pass; returns {transaction_id: evidence} for the requested ids.

    Evidence dict: {"src", "dst", "amount", "ts", "window",
                    "cycle_path": [{"src","dst","amount","ts"}, ...] | None
                       (forward order, closing edge FIRST — the full cycle
                        u -> v -> ... -> u),
                    "fan_in_senders": [{"account","amount","ts"}, ...]}
    """
    ds = get_dataset(name, config_path)
    params = resolve_params(ds)
    edges = pd.read_csv(Path(ds["processed_dir"]) / "edges_transactions.csv",
                        low_memory=False)

    n = len(edges)
    # EXACTLY the engine's factorization (same concat order) so node ids and BFS
    # iteration order match the feature pass.
    codes, uniques = pd.factorize(
        pd.concat([edges["source_account"], edges["dest_account"]],
                  ignore_index=True))
    acct = uniques.astype(str)
    src = codes[:n].tolist()
    dst = codes[n:].tolist()
    ts = edges["timestamp"].to_numpy().tolist()
    amt = edges["amount"].to_numpy(dtype=float).tolist()
    ids = edges["transaction_id"].astype(str).to_numpy()
    pcol = params["partition_col"]
    part = edges[pcol].to_numpy() if pcol and pcol in edges.columns else None

    wanted = set(tx_ids)
    window = params["window"]
    max_len = params["max_cycle_len"]
    budget = params["search_budget"]

    out: dict[str, dict] = {}
    g = WindowGraph(window)
    cur_part = None
    for i in range(n):
        if part is not None and part[i] != cur_part:
            g = WindowGraph(window)
            cur_part = part[i]
        t = ts[i]
        u = src[i]
        v = dst[i]
        a = amt[i]
        g.evict(t)

        if ids[i] in wanted and ids[i] not in out:  # read BEFORE insert (as-of)
            senders = []
            for s in g.in_.get(v, {}):
                s_amt, s_ts = g.last[s][v]   # most recent edge s -> v in window
                senders.append({"account": acct[s], "amount": s_amt, "ts": s_ts})
            senders.sort(key=lambda d: d["ts"], reverse=True)

            cycle = None
            if u == v:
                cycle = [{"src": acct[u], "dst": acct[v], "amount": a, "ts": t}]
            else:
                hops = g.cycle_path(v, u, max_len, budget)
                if hops is not None:
                    cycle = ([{"src": acct[u], "dst": acct[v], "amount": a, "ts": t}]
                             + [{"src": acct[x], "dst": acct[y], "amount": ha,
                                 "ts": hts} for x, y, ha, hts in hops])
            out[ids[i]] = {
                "src": acct[u], "dst": acct[v], "amount": a, "ts": t,
                "window": window,
                "cycle_path": cycle,
                "fan_in_senders": senders[:MAX_FAN_IN_SENDERS],
                "fan_in_total": len(senders),
            }
            if len(out) == len(wanted):
                break

        g.add(t, u, v, a)

    missing = wanted - set(out)
    if missing:
        log.warning("[%s] %d requested transaction ids not found in the edge "
                    "stream", name, len(missing))
    return out
