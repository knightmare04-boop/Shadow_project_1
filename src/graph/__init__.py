"""graph — the Neo4j demo/explanation layer (visualization ONLY, never compute).

Module map:
    db       driver from NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD env vars; graceful
             ping() with setup instructions when no instance is reachable.
    load     schema constraints + batched UNWIND load of the alert subgraph
             (or, with --full, the whole canonical edge list).
    queries  Cypher for reconstructing an alert's suspicious path (temporal,
             as-of ordering via the stream sequence number).
    demo     end-to-end check: for each alert in alerts.json, query the path in
             Neo4j and verify it matches the recorded evidence (PASS/FAIL).

The locked architecture (PROJECT_OVERVIEW section 4): Python computes, Neo4j
shows. All alert content is produced without Neo4j (modeling/alerts.py); this
package only draws it.
"""
