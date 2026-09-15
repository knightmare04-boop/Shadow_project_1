---
name: neo4j-graph-auditor
description: >-
  Guide for Neo4j Cypher query optimization, graph schema design, visual audit alert generation,
  and combining SHAP feature attributions with graph path reconstruction for fraud investigations.
  Use when writing Cypher queries, connecting to Neo4j, or designing explainable graph alerts.
---

# Neo4j Graph Auditor & Explainable Alert Architecture

This skill provides design patterns, Cypher query templates, and integration workflows for building **visual, explainable fraud-detection audit alerts** using Neo4j and SHAP.

---

## 1. Architectural Guardrails

### Compute vs. Visualization Separation
* **Python (Pandas / NetworkX / igraph)**: Handles all high-throughput feature extraction, streaming sliding-window calculations, and model training.
* **Neo4j**: Dedicated strictly to **visualization, interactive exploration, and suspicious path explanation** for human auditors.
* **Why**: Heavy in-database graph computations across millions of temporal edges risk Out-Of-Memory (OOM) failures. Neo4j excels at targeted subgraph retrieval.

---

## 2. Graph Schema & Indexing

### Canonical Schema Design
* **Nodes**: `:Account {id: STRING, account_type: STRING, country: STRING}`
* **Edges**: `[:TRANSACTION {id: STRING, timestamp: INTEGER/FLOAT, amount: FLOAT, is_fraud: INTEGER, alert_id: STRING}]`

```cypher
// Ensure unique account constraint & fast lookups
CREATE CONSTRAINT account_id_unique IF NOT EXISTS
FOR (a:Account) REQUIRE a.id IS UNIQUE;

// Index transactions by timestamp and id for rapid temporal path lookups
CREATE INDEX transaction_ts_idx IF NOT EXISTS
FOR ()-[r:TRANSACTION]-() ON (r.timestamp);

CREATE INDEX transaction_id_idx IF NOT EXISTS
FOR ()-[r:TRANSACTION]-() ON (r.id);
```

### High-Throughput Batch Ingestion Pattern (Python)
```python
from neo4j import GraphDatabase
import pandas as pd

def ingest_transactions_batch(driver, df_edges: pd.DataFrame, batch_size: int = 5000):
    query = """
    UNWIND $batch AS row
    MERGE (src:Account {id: row.source})
    MERGE (dst:Account {id: row.destination})
    CREATE (src)-[r:TRANSACTION {
        id: row.transaction_id,
        amount: toFloat(row.amount),
        timestamp: toInteger(row.timestamp),
        is_fraud: toInteger(row.is_fraud)
    }]->(dst)
    """
    with driver.session() as session:
        records = df_edges.to_dict(orient="records")
        for i in range(0, len(records), batch_size):
            session.run(query, batch=records[i:i + batch_size])
```

---

## 3. Suspicious Pattern Queries (Cypher)

### Circular Money Loops ($A \to B \to C \to A$)
```cypher
MATCH path = (a:Account)-[r1:TRANSACTION]->(b:Account)-[r2:TRANSACTION]->(c:Account)-[r3:TRANSACTION]->(a)
WHERE r1.timestamp <= r2.timestamp 
  AND r2.timestamp <= r3.timestamp
  AND r3.timestamp - r1.timestamp <= 86400  // 24 hour window
RETURN path, [r in relationships(path) | r.amount] AS amounts, (r3.timestamp - r1.timestamp) AS duration_seconds
LIMIT 25;
```

### Money Mule Aggregation (Fan-In Hub)
```cypher
MATCH (mule:Account)
MATCH (source:Account)-[r:TRANSACTION]->(mule)
WHERE r.timestamp >= $start_time AND r.timestamp <= $end_time
WITH mule, count(DISTINCT source) AS num_senders, sum(r.amount) AS total_collected, collect(r) AS txns
WHERE num_senders >= 10 AND total_collected >= 50000
RETURN mule.id AS mule_account, num_senders, total_collected, txns
ORDER BY num_senders DESC;
```

### Rapid Layering Chain ($A \to B \to C \to D$)
```cypher
MATCH path = (a:Account)-[r1:TRANSACTION]->(b:Account)-[r2:TRANSACTION]->(c:Account)-[r3:TRANSACTION]->(d:Account)
WHERE r1.timestamp <= r2.timestamp 
  AND r2.timestamp <= r3.timestamp
  AND (r3.timestamp - r1.timestamp) <= 300 // Completed within 5 minutes
  AND abs(r1.amount - r2.amount) / r1.amount <= 0.05 // Amount conserved
RETURN path, (r3.timestamp - r1.timestamp) AS latency_seconds
LIMIT 20;
```

---

## 4. SHAP + Path Explainability Alert Generator

```python
import shap
import pandas as pd

def generate_audit_alert(
    model,
    feature_row: pd.Series,
    shap_explainer: shap.TreeExplainer,
    transaction_id: str,
    driver,
    top_n_features: int = 4
) -> dict:
    # 1. SHAP Feature Contribution Calculation
    shap_values = shap_explainer(pd.DataFrame([feature_row]))
    values = shap_values.values[0]
    feature_names = feature_row.index
    
    # Sort by absolute SHAP attribution
    sorted_idx = sorted(range(len(values)), key=lambda k: abs(values[k]), reverse=True)
    drivers = [
        {"feature": feature_names[i], "value": float(feature_row.iloc[i]), "shap_impact": float(values[i])}
        for i in sorted_idx[:top_n_features]
    ]
    
    # 2. Query Concrete Subgraph Evidence in Neo4j
    subgraph_query = """
    MATCH (s:Account)-[t:TRANSACTION {id: $tx_id}]->(d:Account)
    OPTIONAL MATCH path = (d)-[r:TRANSACTION*1..4]->(s)
    WHERE ALL(i in range(0, size(r)-2) WHERE (r[i]).timestamp <= (r[i+1]).timestamp)
      AND LAST(r).timestamp <= t.timestamp
    RETURN s.id AS src, d.id AS dst, t.amount AS amount, t.timestamp AS ts,
           [n in nodes(path) | n.id] AS cycle_path_nodes
    LIMIT 1
    """
    with driver.session() as session:
        result = session.run(subgraph_query, tx_id=transaction_id).single()
    
    return {
        "alert_id": f"ALERT-{transaction_id}",
        "transaction_id": transaction_id,
        "source_account": result["src"] if result else feature_row.get("source"),
        "destination_account": result["dst"] if result else feature_row.get("destination"),
        "risk_drivers": drivers,
        "graph_evidence": {
            "is_cycle": bool(result and result["cycle_path_nodes"]),
            "path_nodes": result["cycle_path_nodes"] if result else []
        }
    }
```
