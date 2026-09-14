"""Load the Shadow Graph (or just an alert subgraph) into Neo4j for the demo.

Default mode loads only the subgraph relevant to results/<ds>/alerts/alerts.json:
every account on an alert path (plus its direct counterparties) and the edges
among them inside the alerts' time range. That keeps the load at seconds, per the
locked rule that Neo4j never carries the full compute burden. ``--full`` loads
the entire canonical edge list instead (IBM AML: 1.32M edges, several minutes).

Every :TRANSACTION edge carries ``seq`` — its position in the canonical stream
order (timestamp, then row order). The path queries use ``seq`` so "past only"
in Cypher means exactly what it meant in the streaming engine, including
same-timestamp tie-breaks.

Run:  python -m graph.load ibm_aml [--alerts results/ibm_aml/alerts/alerts.json]
                                   [--full] [--keep] [--batch 5000]
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import pandas as pd

from common.config import get_dataset
from graph.db import get_driver, ping

log = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[2]

CONSTRAINTS = (
    "CREATE CONSTRAINT account_id_unique IF NOT EXISTS "
    "FOR (a:Account) REQUIRE a.id IS UNIQUE",
    "CREATE INDEX transaction_ts_idx IF NOT EXISTS "
    "FOR ()-[r:TRANSACTION]-() ON (r.timestamp)",
    "CREATE INDEX transaction_id_idx IF NOT EXISTS "
    "FOR ()-[r:TRANSACTION]-() ON (r.id)",
)

WIPE = ("MATCH (n) CALL { WITH n DETACH DELETE n } "
        "IN TRANSACTIONS OF 10000 ROWS")

EDGE_LOAD = """
UNWIND $batch AS row
MERGE (src:Account {id: row.source})
MERGE (dst:Account {id: row.destination})
CREATE (src)-[r:TRANSACTION {
    id: row.transaction_id,
    amount: toFloat(row.amount),
    timestamp: toFloat(row.timestamp),
    seq: toInteger(row.seq),
    is_fraud: toInteger(row.is_fraud)
}]->(dst)
SET r.alert_rank = row.alert_rank
"""


def _alert_filter(edges: pd.DataFrame, alerts: dict) -> pd.DataFrame:
    """Subgraph slice: accounts on any alert path (or fan-in list) plus their
    direct counterparties, edges within the alerts' evidence time range."""
    accounts: set[str] = set()
    lo, hi = float("inf"), float("-inf")
    for a in alerts["alerts"]:
        ev = a.get("graph_evidence", {})
        if a.get("source_account"):
            accounts.add(str(a["source_account"]))
        if a.get("dest_account"):
            accounts.add(str(a["dest_account"]))
        for n in ev.get("path_nodes") or []:
            accounts.add(str(n))
        for s in ev.get("senders") or []:
            accounts.add(str(s["account"]))
        ts = a.get("timestamp")
        if ts is not None:
            w = ev.get("window") or 0
            lo = min(lo, float(ts) - float(w))
            hi = max(hi, float(ts))
    src = edges["source_account"].astype(str)
    dst = edges["dest_account"].astype(str)
    touches = src.isin(accounts) | dst.isin(accounts)
    in_time = (edges["timestamp"] >= lo) & (edges["timestamp"] <= hi)
    sub = edges[touches & in_time]
    log.info("alert subgraph: %d core accounts -> %d edges (of %d) in time "
             "range [%s, %s]", len(accounts), len(sub), len(edges), lo, hi)
    return sub


def load_graph(name: str, alerts_path: str | Path | None = None, *,
               full: bool = False, wipe: bool = True, batch: int = 5000) -> int:
    """Load nodes+edges into Neo4j; returns the number of edges loaded."""
    ds = get_dataset(name)
    edges = pd.read_csv(Path(ds["processed_dir"]) / "edges_transactions.csv",
                        low_memory=False)
    edges = edges.reset_index(drop=True)
    edges["seq"] = edges.index          # canonical stream order (ETL-sorted)

    rank_by_id: dict[str, int] = {}
    alerts = None
    if alerts_path:
        with open(alerts_path, encoding="utf-8") as f:
            alerts = json.load(f)
        rank_by_id = {str(a["transaction_id"]): a["rank"] for a in alerts["alerts"]}

    if not full:
        if alerts is None:
            raise ValueError("subgraph mode needs --alerts (or pass --full)")
        edges = _alert_filter(edges, alerts)

    ids = edges["transaction_id"].astype(str)
    records = pd.DataFrame({
        "source": edges["source_account"].astype(str),
        "destination": edges["dest_account"].astype(str),
        "transaction_id": ids,
        "amount": edges["amount"],
        "timestamp": edges["timestamp"],
        "seq": edges["seq"],
        "is_fraud": edges["label"].astype(int),
        "alert_rank": [rank_by_id.get(i) for i in ids],
    }).to_dict(orient="records")

    driver = get_driver()
    try:
        with driver.session() as session:
            if wipe:
                log.info("wiping existing graph...")
                session.run(WIPE)
            for stmt in CONSTRAINTS:
                session.run(stmt)
            for i in range(0, len(records), batch):
                session.run(EDGE_LOAD, batch=records[i:i + batch])
                if (i // batch) % 20 == 0:
                    log.info("loaded %d / %d edges", min(i + batch, len(records)),
                             len(records))
        log.info("done: %d edges, %d flagged as alerts", len(records),
                 sum(1 for r in records if r["alert_rank"] is not None))
    finally:
        driver.close()
    return len(records)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--alerts", default=None,
                    help="path to alerts.json (default results/<ds>/alerts/alerts.json)")
    ap.add_argument("--full", action="store_true", help="load the whole edge list")
    ap.add_argument("--keep", action="store_true", help="do not wipe the DB first")
    ap.add_argument("--batch", type=int, default=5000)
    a = ap.parse_args()
    if not ping():
        raise SystemExit(0)
    alerts = a.alerts or (REPO_ROOT / "results" / a.dataset / "alerts" / "alerts.json")
    n = load_graph(a.dataset, alerts_path=alerts, full=a.full,
                   wipe=not a.keep, batch=a.batch)
    print(f"loaded {n} edges into Neo4j")
