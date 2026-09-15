# Neo4j Audit Demo — setup & walkthrough

The Neo4j layer is **visualization only** (locked architecture, PROJECT_OVERVIEW §4).
Everything it draws already exists in `results/<dataset>/alerts/alerts.json`,
which is produced entirely in Python (`python -m modeling.alerts <dataset>`).
If Neo4j is unavailable, the alerts remain fully usable.

## 1. Setup (one-time)

**Option A — Neo4j Desktop** (recommended on this machine):
1. Install Neo4j Desktop, create a local DBMS (version 5.x), set a password, start it.

**Option B — Docker:**
```
docker run -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/<password> neo4j:5
```

Then, in the shell you run the demo from (PowerShell):
```powershell
$env:NEO4J_PASSWORD = "<password>"
# optional overrides (defaults shown):
# $env:NEO4J_URI  = "bolt://localhost:7687"
# $env:NEO4J_USER = "neo4j"
```

## 2. Generate the alerts (no Neo4j needed)

```powershell
python -m modeling.alerts ibm_aml --k 20     # needs artifacts/ibm_aml/final (run experiments.final first)
```
Writes `results/ibm_aml/alerts/alerts.{json,txt}` — SHAP risk drivers + the
actual cycle/fan-in evidence per alert.

## 3. Load the alert subgraph

```powershell
python -m graph.load ibm_aml                 # wipes the DB, loads the alert subgraph (seconds)
# python -m graph.load ibm_aml --full        # entire 1.32M-edge graph instead (minutes)
```
Every `:TRANSACTION` edge carries `seq` (canonical stream position) so Cypher's
"past only" matches the streaming engine exactly, including same-day tie-breaks.

## 4. Run the verified demo

```powershell
python -m graph.demo ibm_aml
```
For each alert it re-derives the suspicious path *in Neo4j* and checks it matches
the recorded evidence — every cycle alert must print `CYCLE PASS`.

## 5. Visual walkthrough (Neo4j Browser, http://localhost:7474)

Show all flagged transactions with their neighbourhood:
```cypher
MATCH p = (s:Account)-[t:TRANSACTION]->(d:Account)
WHERE t.alert_rank IS NOT NULL
RETURN p
```
Drill into one alert's loop (replace `$tx_id` / `$window`):
```cypher
MATCH (s:Account)-[t:TRANSACTION {id: $tx_id}]->(d:Account)
MATCH p = (d)-[rs:TRANSACTION*1..5]->(s)
WHERE ALL(r IN rs WHERE r.seq < t.seq AND r.timestamp >= t.timestamp - $window)
RETURN p ORDER BY size(rs) ASC LIMIT 1
```
Narrate from the matching entry in `alerts.txt`, e.g. *"closes a 4-hop cycle
A -> B -> C -> A conserving 95% of the amount within 2 days"* — layer 1 (why the
model scored it) is the SHAP drivers, layer 2 (the evidence) is the drawn path.
