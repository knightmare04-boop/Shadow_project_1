"""Cypher for reconstructing an alert's suspicious path — as-of by construction.

Every edge carries ``seq`` (its canonical stream position, loaded by graph/load).
"Past only" is expressed as ``r.seq < t.seq`` — the exact same rule the streaming
engine used, including same-timestamp tie-breaks — so the paths Neo4j draws are
the paths the features actually saw. The window bound uses timestamps, matching
``WindowGraph.evict``.
"""
from __future__ import annotations

# Shortest already-present path dest ~> src whose edges are all strictly before
# the alert transaction (seq) and inside its trailing window (timestamp), hops in
# non-decreasing seq order. Prepending the alert edge closes the cycle.
CYCLE_FOR_TX = """
MATCH (s:Account)-[t:TRANSACTION {id: $tx_id}]->(d:Account)
MATCH p = (d)-[rs:TRANSACTION*1..%(max_hops)d]->(s)
WHERE ALL(r IN rs WHERE r.seq < t.seq AND r.timestamp >= t.timestamp - $window)
RETURN [n IN nodes(p) | n.id]        AS path_nodes,
       [r IN rs | r.amount]          AS amounts,
       [r IN rs | r.timestamp]       AS timestamps,
       size(rs)                      AS n_hops
ORDER BY n_hops ASC
LIMIT 1
"""

# All distinct senders into the alert's destination, strictly before the alert
# and inside its window — the fan-in evidence.
FANIN_FOR_TX = """
MATCH (s:Account)-[t:TRANSACTION {id: $tx_id}]->(d:Account)
MATCH (o:Account)-[r:TRANSACTION]->(d)
WHERE r.seq < t.seq AND r.timestamp >= t.timestamp - $window
RETURN d.id AS dest,
       count(DISTINCT o.id) AS n_senders,
       collect(DISTINCT o.id)[..25] AS senders
"""

# For the Neo4j Browser: draw every loaded alert edge with its neighbourhood.
BROWSER_SHOWCASE = """
MATCH p = (s:Account)-[t:TRANSACTION]->(d:Account)
WHERE t.alert_rank IS NOT NULL
RETURN p
"""


def cycle_for_tx(session, tx_id: str, window: float, max_hops: int = 5):
    """Run CYCLE_FOR_TX; returns the record dict or None."""
    rec = session.run(CYCLE_FOR_TX % {"max_hops": max_hops},
                      tx_id=tx_id, window=float(window)).single()
    return dict(rec) if rec else None


def fanin_for_tx(session, tx_id: str, window: float):
    rec = session.run(FANIN_FOR_TX, tx_id=tx_id, window=float(window)).single()
    return dict(rec) if rec else None
