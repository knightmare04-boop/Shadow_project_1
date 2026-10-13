# MASTER PROJECT CONTEXT: THE SELF-AUDITING LEDGER
> **Target Audience**: AI Coding & Research Agents (Pair programmers, subagents, and automated evaluators)  
> **Purpose**: The complete, authoritative, and exhaustive ground-truth context of the entire project repository, architecture, tech stack, code implementations, empirical findings, and operational invariants.

---

## 1. Executive Summary & Project Identity

* **Project Title**: *The Self-Auditing Ledger: Leakage-Free Temporal Graph Topology for ERP Fraud Detection, with a Production Audit Console*
* **Core Scientific Claim**: Standard graph-based fraud detection suffers from pervasive temporal look-ahead leakage and weak tabular baselines. This project proves that streaming, leakage-free graph topology provides conditional predictive lift (+11.7% to +246.8% PR-AUC), while revealing critical negative results (cycle features carry near-zero importance; topology degrades relational accounting hubs). It combines this with exact tree-native explainability (TreeSHAP in margin space), cross-institutional privacy-preserving federated consensus (FedProx), and an enterprise continuous auditing Procure-to-Pay console backed by database-enforced financial invariants.
* **Repositories**:
  - `Shadow_project_1` (`https://github.com/knightmare04-boop/Shadow_project_1.git`): Primary active repository housing the full application, web console, research paper, presentations, and datasets.
  - `shadowGraphs` / `NodeWatch` (`https://github.com/Aarin062/NodeWatch.git`): Companion repository housing baseline algorithms and experimental scripts.
* **Authors**: Aarin Bhatta, Himanshu Ray, and Mohammed Akif  
* **Affiliation**: School of Computer Science and Engineering, Vellore Institute of Technology, Vellore, India  
* **Academic Venue**: Manuscript prepared for IEEE Transactions on Dependable and Secure Computing (TDSC) / Project Review 2 (Academic Year 2026).

---

## 2. Complete Technology Stack & Tooling

Every layer of the project uses production-grade, pinned technologies:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PRESENTATION & CLIENT                             │
│   React 19.2  •  TypeScript 6.0  •  Vite 8.3  •  TanStack Query 5.102       │
│   Recharts 3.10  •  Tailwind/Tokens CSS  •  Axios 1.20  •  Oxlint 1.81      │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Async REST / SSE (JSON)
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                           BACKEND & APPLICATION API                         │
│   FastAPI 0.115  •  Uvicorn 0.30  •  Pydantic v2.8  •  Structlog 24.4       │
│   Python-Jose (JWT)  •  Bcrypt 4.1  •  Tenacity 9.0  •  Prometheus 0.20     │
└───────┬──────────────────────────────┬──────────────────────────────┬───────┘
        │                              │                              │
┌───────▼──────────────┐   ┌───────────▼──────────────┐   ┌───────────▼───────┐
│  PERSISTENCE & RDBMS │   │  IN-MEMORY CACHE & LOCK  │   │ GRAPH VISUAL AUDIT│
│  PostgreSQL 15       │   │  Redis 7.2               │   │ Neo4j 5.15        │
│  SQLAlchemy 2.0 async│   │  redis-py 5.0            │   │ neo4j driver 5.0  │
│  AsyncPG 0.29 (app)  │   │  Idempotency Locks       │   │ Cypher Subgraph   │
│  Psycopg 3.2 (alembic│   │  Rate Limiting           │   │ Historical Paths  │
│  Alembic 1.13        │   │                          │   │                   │
└──────────────────────┘   └──────────────────────────┘   └───────────────────┘
                                       ▲
                                       │ Sub-2.5ms Feature Extraction & Scoring
┌──────────────────────────────────────┴──────────────────────────────────────┐
│                    ML RESEARCH & STREAMING TOPOLOGY ENGINE                  │
│   Python 3.11  •  NumPy 1.24  •  Pandas 2.0  •  PyArrow 14.0 (Parquet)      │
│   XGBoost 2.0.3 (Hist Head)  •  PyTorch 2.2 (CUDA/CPU)                      │
│   PyTorch Geometric (TGN)    •  SHAP 0.45 (TreeSHAP in Margin Space)        │
│   Scikit-Learn 1.3 (KMeans)  •  Optuna 3.5 (Hyperparameter Optimization)   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                         INFRASTRUCTURE & TEST HARNESS                       │
│   Pytest 8.0  •  Pytest-Asyncio 0.24  •  HTTPX 0.27  •  Testcontainers 4.8  │
│   tools.large_files (90MB SHA-256 chunker for GitHub 100MB limit bypass)    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Technology Matrix by Component

| Domain / Layer | Library / Tool | Version | Specific Purpose / Role in Architecture |
|---|---|---|---|
| **Language Runtime** | Python | 3.11 / 3.12 | Core compute engine for both research and production backend |
| **Tabular Modeling** | XGBoost | 2.0.3 | Histogram gradient-boosted tree classifier with custom objective |
| **Deep Graph Models** | PyTorch / PyG | 2.2 / 2.4 | Continuous-time Temporal Graph Network (TGN) memory vectors |
| **Explainability** | TreeSHAP | 0.45 / Native | Exact polynomial-time margin-space feature attributions via `pred_contribs` |
| **Clustering & Preproc** | Scikit-Learn | 1.3 | KMeans account volume clustering for non-IID federated splits |
| **Graph Compute Path** | Pure Python / deque | Custom | Streaming FIFO `WindowGraph` (leakage-free compute path) |
| **Graph Visual Audit** | Neo4j Community | 5.15 | Forensic subgraph rendering & deterministic Cypher extraction |
| **Web API Framework** | FastAPI | 0.115 | Asynchronous REST endpoints, real-time alert dispatch |
| **ASGI Web Server** | Uvicorn | 0.30 | High-performance asynchronous HTTP/1.1 server |
| **ORM & Database** | SQLAlchemy | 2.0.30 | Async declarative models for P2P ERP schema |
| **Async DB Driver** | AsyncPG | 0.29 | Native PostgreSQL asynchronous connection driver |
| **Sync DB Driver** | Psycopg 3 | 3.2 | Synchronous binary driver dedicated for Alembic migrations |
| **Schema Migrations** | Alembic | 1.13 | Versioned DDL migrations & database trigger enforcement |
| **Distributed Cache** | Redis | 7.2 | Distributed locks, idempotency keys, sliding-window rate limits |
| **Structured Logging** | Structlog | 24.4 | JSON contextual logging with transaction tracing IDs |
| **Telemetry & Metrics** | Prometheus Client | 0.20 | Latency histograms (`SCORING_LATENCY`) and error counters |
| **Frontend Framework** | React | 19.2 | Component-based audit console UI |
| **Frontend Tooling** | Vite / TypeScript | 8.3 / 6.0 | Modern bundler and strict type safety |
| **Data Fetching** | TanStack Query | 5.102 | Declarative server state caching, background polling |
| **Chart Visualizations**| Recharts | 3.10 | Precision-Recall curves, federated metric dashboards |
| **Testing Framework** | Pytest / HTTPX | 8.0 / 0.27 | Parity tests, unit tests, async API integration tests |
| **Artifact Packaging** | tools.large_files | Custom | 90MB file splitter/restorer bypassing GitHub 100MB limit |

---

## 3. The Core Invariant: Read-Then-Insert

The temporal engine enforces an unbending structural rule across all dynamic features:

$$\text{Visible Graph State for Transaction } e_i(u, v, t, a) \equiv G_{<t} = \{e_j \mid t_j < t\} \setminus \text{AgedOutEdges}(t - W)$$

### 3.1 Mathematical Inductive Proof of Leakage-Freedom
1. **Ordering**: The transaction stream is sorted by the composite key $(t_i, \text{tx\_id})$ in strict non-decreasing order.
2. **Read Step**: When edge $e_i = (u_i, v_i, t_i, a_i)$ is evaluated at iteration $i$:
   - All topological queries (degrees, fan-in/fan-out, cycle membership, lapping recurrence) query the graph state $G^{(i)}$.
   - Since $e_i$ has *not yet been added*, $G^{(i)}$ contains only edges from iterations $\{1, 2, \dots, i-1\}$ that have not aged past $t_i - W$.
3. **Insert Step**: Only *after* all features for transaction $i$ are extracted does the engine execute:
   `WindowGraph.add(t_i, u_i, v_i, a_i)` and `LapMemory.record(t_i, u_i, v_i, a_i)`.
4. **Induction**: At iteration 1, $G^{(1)} = \emptyset$. At iteration $k$, $G^{(k)} = \{e_j \mid j < k, t_j \ge t_k - W\}$. A transaction cannot observe itself, nor any transaction that occurs after it in the sequence.
5. **No Whole-Dataset Normalization**: All scaling factors (running means, running standard deviations) use **Welford's algorithm** over past observations only:
   $$\mu_k = \mu_{k-1} + \frac{x_k - \mu_{k-1}}{k}, \quad M_{2,k} = M_{2,k-1} + (x_k - \mu_{k-1})(x_k - \mu_k), \quad s_k^2 = \frac{M_{2,k}}{k-1}$$
   Future statistics never contaminate historical feature rows.

---

## 4. Benchmark Datasets & Characteristics

The project evaluates all models across four heterogeneous financial ecosystems:

| Dataset | Total Rows | Entities $|\mathcal{V}|$ | Test Frauds | Fraud Rate | Graph Topology | Domain Characteristics |
|---|---|---|---|---|---|---|
| **BankSim** | 594,643 | 4,166 | 1,320 | 1.21% | Bipartite Consumer-Merchant | Agent-based consumer purchasing; payments flow strictly from customers to merchants. |
| **IBM AML** | 5,076,142 | 412,416 | 377 | 0.012% (test: 0.12%) | Directed Multi-Hop Network | Complex laundering topologies (smurfing, layering chains, fan-out/fan-in). |
| **SAP Würzburg** | 200,687 | 1,422 | 25 | 0.012% | Relational General Ledger | Real SAP double-entry journal postings; dense clearing hubs (payroll, taxes). |
| **Synth ERP** | 1,141,842 | 8,240 | 1,093 | 0.096% | Agent-Based Calibrated Economy | Injected behavioral fraud: vendor kickbacks, ghost payroll, lapping schemes. |

### Evaluation Splits:
* **Chronological Split**: 60% Train ($t < T_1$), 20% Validation ($T_1 \le t < T_2$), 20% Held-Out Test ($t \ge T_2$).
* **Strict Rule**: No row shuffling, no random k-fold cross-validation, and no bidirectional temporal imputation.

---

## 5. Detailed Component Implementations

### 5.1 Streaming Topology Engine (`src/topology/window_graph.py` & `engine.py`)

#### `WindowGraph` Data Structure:
```python
class WindowGraph:
    __slots__ = ("window", "_edges", "out", "in_", "indeg", "outdeg", "last")

    def __init__(self, window: int | float | None):
        self.window = window
        self._edges: deque[tuple[int, int, int]] = deque()      # (ts, u, v) in FIFO time order
        self.out: dict[int, dict[int, int]] = defaultdict(dict)  # out[u][v] = multiplicity
        self.in_: dict[int, dict[int, int]] = defaultdict(dict)  # in_[v][u] = multiplicity
        self.indeg: dict[int, int] = defaultdict(int)            # total in-edges (multiplicity)
        self.outdeg: dict[int, int] = defaultdict(int)           # total out-edges (multiplicity)
        self.last: dict[int, dict[int, tuple[float, int | float]]] = defaultdict(dict) # (amount, ts)
```
- **Eviction (`_evict_before(now)`)**: Pops expired edges from the front of the `deque` in $O(1)$ amortized time, decrementing `indeg`, `outdeg`, and removing dictionary keys when multiplicity reaches zero.
- **Cycle Search (`find_cycle(u, v, max_len=4, budget=4000)`)**: Performs a bounded forward Breadth-First / Depth-First search starting at destination $v$ searching for paths back to source $u$. If a path $v \rightsquigarrow u$ exists of length $\le \text{max\_len}-1$, adding edge $u \to v$ completes a directed cycle of length $\le \text{max\_len}$.
- **Tightness & Amount Conservation**: Traverses `self.last` along the detected cycle path to compute:
  $$\text{cycle\_amount\_ratio} = \frac{\min_{e \in \mathcal{C}} a_e}{\max_{e \in \mathcal{C}} a_e}, \quad \text{cycle\_span} = \max_{e \in \mathcal{C}} t_e - \min_{e \in \mathcal{C}} t_e$$

#### `LapMemory`:
Maintains a rolling ring-buffer of previous transactions per counterparty to identify **accounts-receivable lapping**:
```python
class LapMemory:
    def __init__(self, capacity: int = 25):
        self.capacity = capacity
        self.history: dict[int, deque[float]] = defaultdict(lambda: deque(maxlen=capacity))

    def check_and_record(self, account_id: int, amount: float) -> tuple[int, float]:
        hist = self.history[account_id]
        recurrence_count = sum(1 for prev_amt in hist if math.isclose(prev_amt, amount, rel_tol=0.01))
        hist.append(amount)
        return recurrence_count, len(hist)
```

---

### 5.2 Continuous Temporal Graph Network (`src/modeling/tgn.py`)

Implements a lightweight, CPU-friendly continuous-time graph network (Rossi et al. 2020) operating strictly under Rule 4:
- **Time2Vec Periodic Time Encoding**:
  $$\Phi(\Delta t) = \cos(\mathbf{w} \cdot \log(1 + \Delta t) + \mathbf{b})$$
  Implemented via PyTorch parameters `self.time_w = nn.Parameter(torch.randn(time_dim))` and `self.time_b = nn.Parameter(torch.zeros(time_dim))`.
- **Memory Module**: Maintains a state vector $\mathbf{s}_u \in \mathbb{R}^{32}$ for every active node $u$.
- **Message Function & Update**: When interaction $(u, v, t)$ occurs:
  $$\mathbf{m}_u(t) = \text{MLP}([\mathbf{s}_u(t^-),\, \mathbf{s}_v(t^-),\, \Phi(\Delta t)]), \quad \mathbf{s}_u(t) = \text{GRUCell}(\mathbf{m}_u(t),\, \mathbf{s}_u(t^-))$$
- **Label-Free Link Prediction Head**: Self-supervised objective trained strictly on the train period to predict real next edges versus random negative destinations:
  $$\mathcal{L}_{\text{TGN}} = -\sum_{(u, v) \in \mathcal{E}} \log \sigma(\mathbf{z}_u^\top \mathbf{z}_v) - \sum_{(u, v_{\text{neg}}) \notin \mathcal{E}} \log \sigma(-\mathbf{z}_u^\top \mathbf{z}_{v_{\text{neg}}})$$
- **Extracted Embeddings**: Once trained, weights are frozen. Processing the transaction stream produces a 16-dimensional continuous latent vector $\mathbf{z}_{\text{tgn}} = [\mathbf{s}_u, \mathbf{s}_v, \text{expectedness}]$ without using fraud labels or transaction amounts.

---

### 5.3 Custom Imbalance Objective: $\alpha$-Free Focal Loss (`src/modeling/objectives.py`)

To satisfy **Rule 1** (*One imbalance mechanism, not two*), the model avoids mixing SMOTE with class weights. Instead, it uses an unweighted, symmetric focal loss:

$$\mathcal{L}_{\text{focal}}(p_t) = -(1 - p_t)^\gamma \log(p_t), \quad p_t = \begin{cases} p & \text{if } y = 1 \\ 1 - p & \text{if } y = 0 \end{cases}$$

#### Closed-Form Gradient & Numerical Hessian:
With margin $m \in \mathbb{R}$ and $p = \sigma(m)$:
```python
def _focal_grad(margin: np.ndarray, y: np.ndarray, gamma: float) -> np.ndarray:
    p = np.clip(sigmoid(margin), 1e-12, 1.0 - 1e-12)
    def g1(q):
        return gamma * q * (1.0 - q) ** gamma * np.log(q) - (1.0 - q) ** (gamma + 1.0)
    return np.where(y == 1, g1(p), -g1(1.0 - p))

def focal_objective(gamma: float = 2.0):
    def obj(y_true: np.ndarray, margin: np.ndarray):
        y = np.asarray(y_true, dtype=np.float64)
        m = np.asarray(margin, dtype=np.float64)
        grad = _focal_grad(m, y, gamma)
        hess = (_focal_grad(m + 1e-4, y, gamma) - _focal_grad(m - 1e-4, y, gamma)) / (2.0 * 1e-4)
        hess = np.maximum(hess, 1e-16)  # XGBoost requires strictly positive hessians
        return grad, hess
    return obj
```
Because the objective is callable, XGBoost predicts raw log-odds margins $m$. Inference applies $\sigma(m)$ to obtain calibrated probabilities.

---

### 5.4 Exact TreeSHAP Explainability (`src/modeling/explain.py`)

- **Native TreeSHAP**: Invokes XGBoost's C++ native tree traversal:
  ```python
  dmat = xgb.DMatrix(X[features], feature_names=features)
  raw = booster.predict(dmat, pred_contribs=True)
  contribs, bias = raw[:, :-1], raw[:, -1]
  ```
- **Mathematical Invariant**:
  $$\sum_{j=1}^M \phi_j(x_i) + \phi_0 = f_{\text{margin}}(x_i) \equiv \log\left(\frac{p_i}{1 - p_i}\right)$$
  Signed attributions are additive in log-odds space. A positive $\phi_j$ indicates that feature $j$ pushed the risk probability upward.
- **Two-Layer Forensic Alert Synthesis**:
  - **Layer 1 (Model Attribution)**: Returns top-3 driving features signed by risk direction (e.g., `+0.43 log_amount`, `+0.29 dest_in_degree`).
  - **Layer 2 (Reconstructed Neo4j Subgraph)**: Executes a deterministic Cypher query fetching historical nodes and edges within trailing 30 days:
    ```cypher
    MATCH (u:Account {id: $src_id})-[e:TRANSFERRED*1..2]-(v:Account)
    WHERE e.timestamp <= $tx_timestamp AND e.timestamp >= $tx_timestamp - 2592000
    RETURN u, e, v LIMIT 50;
    ```

---

### 5.5 Privacy-Preserving Federated Consensus (`src/federated/`)

Designed to satisfy bank secrecy mandates (GDPR, GLBA):
1. **Partitioning (`src/federated/partition.py`)**:
   - `KMeans(n_clusters=4)` clusters accounts by log volume, creating realistic institutional skew:
     - **Client 0 (Retail Core)**: 87.5% volume, 0.38% fraud rate.
     - **Client 1 (High-Risk Gateway)**: 0.6% volume, 18.67% fraud rate.
     - **Client 2 (Commercial B2B)**: 4.2% volume, 14.0% fraud rate.
     - **Client 3 (Regional Branch)**: 7.7% volume, 2.3% fraud rate.
2. **Client Autonomous Training (`src/federated/client.py`)**:
   - Each `FederatedClient` trains strictly on its local partition using local focal loss and derives its local validation PR-AUC. No transaction rows or raw features leave the client node.
3. **FedProx Validation Reliability Weighting (`src/federated/server.py`)**:
   - Aggregates scores via normalized power weighting of validation PR-AUC:
     $$w_k = \frac{(\text{PR-AUC}_{\text{val}, k})^\beta}{\sum_{j=1}^K (\text{PR-AUC}_{\text{val}, j})^\beta}, \quad \hat{p}_{\text{consensus}}(e_i) = \sum_{k=1}^K w_k \cdot f_k(e_i)$$
   - Prevents fraud-starved institutions (Client 0) from corrupting global consensus.

---

### 5.6 Database-Enforced Financial Invariants (`alembic/versions/6192dae4f4a4_gl_invariants_triggers.py`)

Financial integrity is enforced at the PostgreSQL database engine level:

1. **Double-Entry Balance Trigger**:
   ```sql
   CREATE OR REPLACE FUNCTION check_journal_entry_balance() RETURNS TRIGGER AS $$
   DECLARE total_debit NUMERIC(18,2); total_credit NUMERIC(18,2);
   BEGIN
       SELECT COALESCE(SUM(debit_amount), 0), COALESCE(SUM(credit_amount), 0)
         INTO total_debit, total_credit
         FROM journal_lines WHERE journal_entry_id = NEW.journal_entry_id;
       IF total_debit <> total_credit THEN
           RAISE EXCEPTION 'journal entry % is not balanced: debit=% credit=%',
               NEW.journal_entry_id, total_debit, total_credit USING ERRCODE = 'check_violation';
       END IF;
       RETURN NULL;
   END; $$ LANGUAGE plpgsql;

   CREATE CONSTRAINT TRIGGER trg_journal_lines_balance
   AFTER INSERT OR UPDATE OR DELETE ON journal_lines
   DEFERRABLE INITIALLY DEFERRED
   FOR EACH ROW EXECUTE FUNCTION check_journal_entry_balance();
   ```
   *Rationale*: Must be `DEFERRABLE INITIALLY DEFERRED` so it evaluates at transaction commit, allowing multi-line journal postings to be inserted sequentially.

2. **Period Close Guard**:
   ```sql
   CREATE TRIGGER trg_journal_entries_period_open
   BEFORE INSERT OR UPDATE ON journal_entries
   FOR EACH ROW EXECUTE FUNCTION check_fiscal_period_open();
   ```
   Rejects postings where `fiscal_periods.status != 'open'`.

3. **Immutable Audit Log**:
   ```sql
   CREATE TRIGGER trg_audit_log_immutable
   BEFORE UPDATE OR DELETE ON audit_log
   FOR EACH ROW EXECUTE FUNCTION reject_audit_log_mutation();
   ```
   Unconditionally rejects `UPDATE` and `DELETE` queries on `audit_log`, providing tamper-proof write-once compliance (SOX).

4. **Duplicate-Payment & Concurrency Defense (`app/services/payment_service.py`)**:
   Uses `SELECT ... FOR UPDATE` on invoice rows combined with Redis atomic idempotency locks (`SET key val NX EX 300`) to guarantee zero duplicate disbursements under high-concurrency race conditions.

---

### 5.7 Online Serving Architecture & Parity Testing

- **Backend Scoring Service (`app/services/scoring_service.py`)**:
  Instantiates `FraudScoringService` holding `OnlineTopologyState` and `OnlineOrdinaryState`.
  - Computes features incrementally against in-memory sliding window.
  - Predicts risk score via loaded `ScoringBundle`.
  - Latency executes in **$< 2.5\text{ ms}$** per transaction (well within the $< 200\text{ ms}$ SLA).
- **Parity Assertion (`tests/test_online_topology_parity.py`)**:
  Replays 20,000 real transactions through both offline batch `extract_features` and online `OnlineTopologyState`, verifying exact float equality (`math.isclose(a, b, rel_tol=1e-9)`) across all 13 topology features with **zero mismatches**.

---

### 5.8 React 19 Frontend Web Audit Console (`web/`)

- Built with React 19, TypeScript, and Vite.
- **Pages**:
  - `Alerts.tsx`: Interactive real-time risk alert triage, confidence badges, TreeSHAP waterfall graphs, and Cypher graph path inspection.
  - `Federated.tsx`: Multi-bank consensus metrics, client drift monitoring, blind spot lift visualizations.
  - `Invoices.tsx`: 3-way matching interface (PO vs Goods Receipt vs Invoice).
  - `Payments.tsx`: Payment batch execution with live scoring integration.
  - `Vendors.tsx`: Vendor directory and bank detail audit history.
- **Styling**: Tailored design tokens (`web/src/styles/tokens.css` and `global.css`) providing a sleek dark/light corporate aesthetic with zero generic styling.

---

### 5.9 Large File Chunker (`tools/large_files.py`)

Bypasses GitHub's 100MB per-file hard limit without requiring paid Git LFS quotas:
- Files exceeding 95MB are split into ordered $\le 90\text{ MiB}$ chunks under `large_file_parts/<path>/part-NNNN`.
- `large_file_parts/MANIFEST.json` records original file size and SHA-256 hash.
- CLI commands:
  ```bash
  python -m tools.large_files split    # Split oversize files into chunks
  python -m tools.large_files restore  # Rebuild original datasets from chunks
  python -m tools.large_files verify   # Assert SHA-256 integrity
  ```

---

## 6. Empirical Findings & Methodological Traps

1. **The Cycle Null Result**:
   - Directed cycle features carry near-zero gain importance ($< 0.005$) in real data (BankSim, IBM AML, SAP Würzburg). Real-world fraudsters layer funds into exit sinks (cash mules, crypto gateways) rather than routing money back to the origin account.
2. **The Relational ERP Negative Lift**:
   - Introducing pure graph topology on SAP Würzburg degrades PR-AUC from 0.1581 to 0.0717 ($-54.6\%$). In double-entry accounting ledgers, high fan-in accounts are legitimate clearing hubs (payroll, tax liabilities). Pure graph models generate false alerts on legitimate hubs.
3. **The ROC-AUC Fallacy**:
   - Under extreme class imbalance ($< 0.1\%$ fraud), ROC-AUC is artificially inflated $> 0.99$ by true negatives. PR-AUC and operational Precision@100 are the only honest metrics.
4. **Synthetic Data Augmentation Penalty**:
   - Naively mixing synthetic data into real datasets harms test performance unless calibrated against empirical degree distributions.

---

## 7. Complete Codebase Directory Map

```text
Shadow_project_1/
├── app/                               # Enterprise FastAPI Application
│   ├── api/                           # REST endpoints (alerts, ledger, federated)
│   ├── core/                          # Config, security, DB connections, middleware
│   │   ├── idempotency_middleware.py  # Redis SETNX idempotency protection
│   │   └── security.py                # JWT & bcrypt authentication
│   ├── db/                            # PostgreSQL session & SQLAlchemy models
│   │   ├── session.py                 # Async engine & sessionmaker
│   │   └── redis_client.py            # Async Redis connection pool
│   ├── models/                        # Declarative DB models (audit, gl, invoice, payment)
│   ├── schemas/                       # Pydantic v2 validation schemas
│   ├── services/                      # Application business logic
│   │   ├── scoring_service.py         # Sub-2.5ms live FraudScoringService
│   │   ├── online_topology.py         # Real-time streaming topology state
│   │   ├── payment_service.py         # Concurrent payment execution with row locks
│   │   └── federated_service.py       # Federated score aggregation
│   └── main.py                        # FastAPI application entrypoint
├── data/                              # Data directories (raw, processed)
│   ├── processed/                     # Leakage-free feature tables (parquet, csv)
│   └── raw/                           # Raw benchmark datasets
├── docs/                              # Project documentation & architectural designs
│   ├── FINAL_REPORT.md                # Comprehensive final project report
│   ├── MODELS_AND_TECHNIQUES.md       # Detailed guide to all ML models and ETL stages
│   └── DESIGN.md                      # Foundational design & ablation rules
├── experiments/                       # Core ML research and evaluation scripts
│   ├── ablation.py                    # 7-arm within-dataset ablation engine
│   ├── federated.py                   # FedProx federated simulation benchmark
│   ├── modern.py                      # TGN & Tabular Transformer modernization probe
│   └── run_dataset.py                 # End-to-end dataset feature extraction & scoring
├── large_file_parts/                  # Ordered <=90MB chunks for GitHub compliance
│   └── MANIFEST.json                  # SHA-256 and size verification manifest
├── paper/                             # IEEE Research Paper Source & Deliverables
│   ├── figures/                       # High-resolution empirical evaluation figures
│   ├── full_paper.tex                 # Complete IEEEtran LaTeX source code
│   ├── references.bib                 # 15 BibTeX citations
│   ├── REVIEW_2_PAPER.md              # Markdown draft of the research paper
│   ├── Self_Auditing_Ledger_Overleaf_Package.zip # 1-click Overleaf bundle
│   └── The_Self_Auditing_Ledger_Paper.docx       # Fully styled Word manuscript
├── results/                           # JSON experiment outputs & markdown tables
├── src/                               # Core Python Modules
│   ├── features/                      # Deterministic ingestion & preprocessing
│   ├── federated/                     # Client, Server, and Partition implementations
│   │   ├── client.py                  # FederatedClient autonomous learner
│   │   ├── partition.py               # KMeans non-IID account volume clustering
│   │   └── server.py                  # FedProx validation reliability weighting
│   ├── graph/                         # Neo4j connector & Cypher query builder
│   ├── modeling/                      # ML models & evaluation
│   │   ├── objectives.py              # Custom focal loss & gradient/hessian calculations
│   │   ├── explain.py                 # Margin-space TreeSHAP & alert drivers
│   │   ├── tgn.py                     # Continuous Temporal Graph Network (PyG)
│   │   └── harness.py                 # Chronological validation & training harness
│   └── topology/                      # Streaming leakage-free WindowGraph engine
│       ├── window_graph.py            # FIFO WindowGraph data structure & cycle search
│       └── engine.py                  # Read-then-insert feature extraction coordinator
├── tests/                             # Comprehensive automated test suite
│   ├── test_online_topology_parity.py # 20,000 transaction parity assertion test
│   ├── test_federated.py              # Federated consensus tests
│   └── test_cycle_path.py             # Bounded cycle search test
├── tools/                             # Repository tooling
│   └── large_files.py                 # Split/restore/verify engine for large files
├── web/                               # React 19 / TypeScript Audit Console
│   ├── src/pages/Alerts.tsx           # Real-time forensic alert review
│   ├── src/pages/Federated.tsx        # Multi-bank federated consensus monitoring
│   ├── src/pages/Invoices.tsx         # P2P invoice approval workflow
│   └── src/App.tsx                    # Frontend router & navigation
├── CLAUDE.md                          # Source of truth rules & invariants
├── pyproject.toml                     # Dependencies & build configuration
└── HOW_TO_RUN.md                      # Operational CLI runbook
```

---

## 8. CLI Runbook & Operational Commands

### 8.1 Setup & Large Files:
```bash
# Setup environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[explain,test,app]"

# Restore datasets from chunks
python -m tools.large_files restore
python -m tools.large_files verify
```

### 8.2 Research Experiments:
```bash
# Feature extraction (Leakage-free streaming topology)
python experiments/run_dataset.py --dataset banksim

# 7-Arm within-dataset ablation
python experiments/ablation.py --dataset banksim

# Federated simulation (FedProx reliability weighting, K=4)
python experiments/federated.py --dataset banksim --clients 4 --strategy fedprox

# Modern TGN embedding extraction
python -m modeling.tgn banksim
```

### 8.3 Quality Assurance & Parity Testing:
```bash
# Run online-to-batch feature parity test (20,000 real transactions)
pytest tests/test_online_topology_parity.py -v

# Run federated simulation test suite
pytest tests/test_federated.py -v
```

### 8.4 Running the Production System:
```bash
# Run database migrations
alembic upgrade head

# Start FastAPI backend (Port 8000)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Start React audit console (Port 5173)
cd web && npm install && npm run dev
```

---

## 9. Non-Negotiable Invariants for AI Agents

1. **Rule 1 (Single Imbalance Mechanism)**: Never mix SMOTE oversampling with class weights. Use custom $\alpha$-free focal loss or `scale_pos_weight`.
2. **Rule 2 (Threshold Freezing)**: Always tune decision thresholds $\bar{\tau}$ on validation data and freeze them for test evaluation. Never report at arbitrary default 0.5.
3. **Rule 3 (Strict Chronological Splits)**: Train on past ($t < T_1$), validate on intermediate ($T_1 \le t < T_2$), test on future ($t \ge T_2$). No random shuffling.
4. **Rule 4 (Read-Then-Insert)**: A transaction's features must depend *only* on graph state $G_{<t}$. Never insert an edge before reading its features. No whole-dataset statistics.
5. **Rule 5 (Honest Evaluation Metrics)**: Evaluate with PR-AUC / Average Precision and Precision@K. Never rely on ROC-AUC on imbalanced datasets.
6. **Rule 6 (GitHub 100MB Rule)**: Never commit raw data files $> 90\text{ MB}$. Always run `python -m tools.large_files split` and ensure raw data is in `.gitignore`.
