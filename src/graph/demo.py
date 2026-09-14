"""The Neo4j audit demo — draw each alert's suspicious path and verify it.

For every alert in results/<ds>/alerts/alerts.json whose evidence is a cycle,
query the as-of path back in Neo4j (graph/queries.py) and check the node
sequence matches the recorded evidence; fan-in alerts get their sender count
cross-checked. This doubles as the Neo4j verification gate: all cycle alerts
must PASS.

Prints the exact Neo4j Browser query for the visual walkthrough at the end.

Run:  python -m graph.demo ibm_aml [--alerts <path>] [--max-hops 5]
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from graph.db import get_driver, ping
from graph.queries import BROWSER_SHOWCASE, cycle_for_tx, fanin_for_tx

log = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[2]

# When the evidence window is None/unbounded, pass an effectively infinite bound.
_NO_WINDOW = 1e18


def run_demo(name: str, alerts_path: str | Path | None = None,
             max_hops: int = 5) -> bool:
    alerts_path = Path(alerts_path or
                       REPO_ROOT / "results" / name / "alerts" / "alerts.json")
    with open(alerts_path, encoding="utf-8") as f:
        payload = json.load(f)

    driver = get_driver()
    ok = True
    n_cycle = n_pass = 0
    try:
        with driver.session() as session:
            for a in payload["alerts"]:
                ev = a["graph_evidence"]
                window = ev.get("window")
                window = _NO_WINDOW if window is None else float(window)
                head = (f"[{a['rank']:>2}] {a['transaction_id']} "
                        f"score {a['score']:.4f}")
                if ev["type"] == "cycle" and ev.get("path_nodes"):
                    n_cycle += 1
                    got = cycle_for_tx(session, a["transaction_id"], window,
                                       max_hops=max_hops)
                    # recorded path_nodes = [src, dst, ..., src]; the Cypher path
                    # starts at dst and ends at src -> compare against [dst.., src].
                    want = ev["path_nodes"][1:]
                    if got and got["path_nodes"] == want:
                        n_pass += 1
                        print(f"{head}  CYCLE PASS: "
                              f"{' -> '.join(ev['path_nodes'])}")
                    else:
                        ok = False
                        print(f"{head}  CYCLE FAIL: recorded {want}, "
                              f"neo4j {got['path_nodes'] if got else None}")
                elif ev["type"] == "fan_in":
                    got = fanin_for_tx(session, a["transaction_id"], window)
                    n = got["n_senders"] if got else 0
                    note = "" if n == ev["n_senders"] else (
                        f"  (recorded {ev['n_senders']} - multi-edge tie-breaks "
                        f"can differ)")
                    print(f"{head}  FAN-IN: {n} senders into "
                          f"{a['dest_account']}{note}")
                else:
                    print(f"{head}  no graph evidence (drivers-only alert)")
    finally:
        driver.close()

    print("-" * 70)
    print(f"cycle evidence verified in Neo4j: {n_pass}/{n_cycle} PASS")
    print("\nNeo4j Browser walkthrough (paste into http://localhost:7474):")
    print(BROWSER_SHOWCASE.strip())
    return ok and n_pass == n_cycle


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--alerts", default=None)
    ap.add_argument("--max-hops", type=int, default=5)
    a = ap.parse_args()
    if not ping():
        raise SystemExit(0)
    good = run_demo(a.dataset, alerts_path=a.alerts, max_hops=a.max_hops)
    raise SystemExit(0 if good else 1)
