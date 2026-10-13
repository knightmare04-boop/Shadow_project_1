# MASTER PROJECT CONTEXT: THE SELF-AUDITING LEDGER
> **Target Audience**: AI Coding & Research Agents (Pair programmers, subagents, and automated evaluators)  
> **Purpose**: Serves as the complete, authoritative, and unambiguous ground-truth context of the entire project repository, architecture, methodology, empirical findings, and operational invariants.

---

## 1. Executive Summary & Project Identity

* **Project Title**: *The Self-Auditing Ledger: Leakage-Free Temporal Graph Topology for ERP Fraud Detection, with a Production Audit Console*
* **Core Thesis**: Graph-based fraud detection methods frequently suffer from pervasive temporal look-ahead leakage and lack controlled same-architecture ablation against strong tabular baselines. This project provides a mathematically provable, leakage-free streaming temporal topology engine, subjects it to multi-dataset ablation, integrates continuous-time Temporal Graph Networks (TGN), implements privacy-preserving federated consensus (FedProx), and deploys an enterprise continuous auditing console backed by database-enforced double-entry ledger invariants.
* **Primary Repositories**:
  - `Shadow_project_1` (`https://github.com/knightmare04-boop/Shadow_project_1.git`): Primary active codebase, research papers, presentations, datasets, and web console.
  - `shadowGraphs` / `NodeWatch` (`https://github.com/Aarin062/NodeWatch.git`): Companion repository housing baseline algorithms and experimental scripts.
* **Authors**: Aarin Bhatta, Himanshu Ray, and Mohammed Akif  
* **Affiliation**: School of Computer Science and Engineering, Vellore Institute of Technology, Vellore, India  
* **Target Publication**: IEEE Transactions on Dependable and Secure Computing (TDSC) / Project Review 2 (Academic Year 2026).

---

## 2. The Three Methodological Crises in Published Literature

Systematic review of prior literature (GCN, GAT, EvolveGCN, GraphSAGE, tabular baselines) identified three critical methodological flaws that this project resolves:

1. **Pervasive Temporal Leakage**:
   - *The Flaw*: Academic graph benchmarks routinely construct static graph representations over an entire dataset span prior to feature extraction. Consequently, topological features (degrees, PageRank, k-hop embeddings) for historical transactions incorporate edges from their own future.
   - *The Consequence*: Laboratory performance collapses catastrophically upon deployment to streaming production pipelines.
   - *Our Solution*: A strictly causal **Read-Then-Insert** streaming engine where a transaction at timestamp $t$ only ever sees the graph state $G_{<t}$.

2. **Absent Ablation Discipline**:
   - *The Flaw*: Novel graph neural net architectures are routinely compared against naive tabular models lacking domain-standard feature engineering (e.g., comparing against raw amount and categorical IDs without Welford z-scores, arrival deltas, or diurnal encodings).
   - *The Consequence*: It is impossible to isolate whether observed performance gains stem from genuine topological structure or simply auxiliary tabular signals.
   - *Our Solution*: Controlled, same-architecture 7-arm ablation isolating:
     - Baseline Ordinary Tabular
     - + Structure Only (Pure Graph, amounts zeroed out)
     - + Handcrafted Topology (13 streaming features)
     - + Learned Continuous TGN Embeddings
     - Final Champion Hybrid Ensemble (Tabular + Handcrafted Topology + TGN).

3. **Uninterpretable Black-Box Deployments**:
   - *The Flaw*: Deep graph architectures lack exact, polynomial-time attribution methods. Under statutory regulations (Sarbanes-Oxley Act, Basel III, GDPR Article 22), auditors cannot legally act upon black-box risk scores without verifiable, reconstructable evidence trails.
   - *Our Solution*: Exact, tree-native **TreeSHAP** computed in log-odds margin space, coupled with deterministic **Cypher subgraph extraction** to produce verifiable 2-layer forensic alert packets.

---

## 3. The Core Invariant: Read-Then-Insert

The temporal engine enforces an unbending structural rule across all dynamic features:

$$\text{Visible Graph State for Transaction } e_i(u, v, t, a) \equiv G_{<t} = \{e_j \mid t_j < t\} \setminus \text{AgedOutEdges}(t - W)$$

### Execution Sequence:
1. **Sort**: All transactions are sorted by the composite key `(timestamp, tx_id)` in strict non-decreasing order.
2. **Read**:
   - Query `WindowGraph` for source fan-out, destination fan-in, out-degree, and in-degree over trailing windows $W \in \{1\text{d}, 7\text{d}, 30\text{d}\}$.
   - If $\text{src} \neq \text{dst}$, execute bounded DFS/cycle search for length-3 and length-4 directed loops.
   - Query `LapMemory` for rolling recurrence of monetary amount $a$ against each counterparty's historical payment record.
   - Compute Welford running mean and variance z-scores using past events only (never whole-dataset statistics).
   - Compute inter-event arrival delta $\Delta t = t - t_{\text{prev}}(u)$.
3. **Insert**:
   - Only *after* all features for transaction $i$ have been evaluated does the engine invoke:
     `WindowGraph.add(t, u, v, amount)` and `LapMemory.record(t, u, v, amount)`.
4. **Inductive Guarantee**:
   Edge $j$ is added only during iteration $j$. Therefore, the graph state visible to iteration $i$ is identically $\{j : j < i\}$ minus aged-out edges—never a superset, and never containing information from its own future.

---

## 4. Benchmark Datasets

The project evaluates all models across four heterogeneous financial ecosystems:

| Dataset | Total Rows | Entities $|\mathcal{V}|$ | Test Frauds | Fraud Rate | Graph Topology | Domain Characteristics |
|---|---|---|---|---|---|---|
| **BankSim** | 594,643 | 4,166 | 1,320 | 1.21% | Bipartite Consumer-Merchant | Agent-based consumer purchasing; payments flow strictly from customers to merchants. |
| **IBM AML** | 5,076,142 | 412,416 | 377 | 0.012% (test: 0.12%) | Directed Multi-Hop Network | Complex laundering topologies (smurfing, layering chains, fan-out/fan-in). |
| **SAP Würzburg** | 200,687 | 1,422 | 25 | 0.012% | Relational General Ledger | Real SAP double-entry journal postings; dense clearing hubs (payroll, taxes). |
| **Synth ERP** | 1,141,842 | 8,240 | 1,093 | 0.096% | Agent-Based Calibrated Economy | Injected behavioral fraud: vendor kickbacks, ghost payroll, lapping schemes. |

### Evaluation Splits:
* **Chronological Split**: 60% Train ($t < T_1$), 20% Validation ($T_1 \le t < T_2$), 20% Held-Out Test ($t \ge T_2$).
* **Strict Rule**: No row shuffling, no random k-fold cross-validation, and no bidirectional interpolation.

---

## 5. Feature Space Taxonomy

Each transaction $e_i$ is mapped to a combined feature vector:
$$\mathbf{x}_i = [\mathbf{x}_{\text{ord}},\, \mathbf{x}_{\text{topo}},\, \mathbf{z}_{\text{tgn}}] \in \mathbb{R}^{D}$$

### 5.1 Ordinary Tabular Features ($\mathbf{x}_{\text{ord}}$)
- $\log_{10}(a_i + 1)$: Log-scaled transaction monetary amount.
- `amount_z_score`: Running Welford z-score updated sequentially:
  $$\mu_k = \mu_{k-1} + \frac{a_k - \mu_{k-1}}{k}, \quad M_{2,k} = M_{2,k-1} + (a_k - \mu_{k-1})(a_k - \mu_k), \quad z_k = \frac{a_k - \mu_k}{\sqrt{M_{2,k}/(k-1)}}$$
- Diurnal Periodic Encodings: $\sin\left(\frac{2\pi h_i}{24}\right), \cos\left(\frac{2\pi h_i}{24}\right)$ where $h_i$ is the hour of the day.
- Inter-event arrival delta: $\Delta t = t_i - t_{\text{prev}}(u_i)$.

### 5.2 Handcrafted Streaming Topology ($\mathbf{x}_{\text{topo}}$) — 13 Features
1. `src_out_degree_1d`: Out-degree of source over past 24 hours.
2. `src_out_degree_7d`: Out-degree of source over past 7 days.
3. `src_out_degree_30d`: Out-degree of source over past 30 days.
4. `dst_in_degree_1d`: In-degree of destination over past 24 hours.
5. `dst_in_degree_7d`: In-degree of destination over past 7 days.
6. `dst_in_degree_30d`: In-degree of destination over past 30 days.
7. `fan_in_ratio`: Destination in-degree relative to total active neighborhood.
8. `fan_out_ratio`: Source out-degree relative to total active neighborhood.
9. `counterparty_reciprocity`: Proportion of directed edges between $u$ and $v$ that are reciprocated ($v \to u$).
10. `burstiness_velocity`: Ratio of short-term degree (1d) to medium-term degree (7d).
11. `lap_recurrence`: Frequency of exact or near-identical amount recurrence from same counterparty (accounts-receivable lapping).
12. `in_cycle_len3`: Boolean indicator / count of directed length-3 cycles completed by this edge ($u \to v \to w \to u$).
13. `in_cycle_len4`: Boolean indicator / count of directed length-4 cycles completed by this edge.

### 5.3 Continuous Dynamic Graph Embeddings ($\mathbf{z}_{\text{tgn}} \in \mathbb{R}^{16}$)
- Extracted using a continuous-time **Temporal Graph Network (TGN)** implemented in PyTorch Geometric.
- Maintains decaying memory states $\mathbf{s}_u(t)$ updated upon each interaction via an event-driven GRU cell:
  $$\mathbf{m}_i = \text{MessageFunction}(\mathbf{s}_u(t^-), \mathbf{s}_v(t^-), \Delta t, \mathbf{e}_{uv}), \quad \mathbf{s}_u(t) = \text{MemoryUpdate}(\mathbf{s}_u(t^-), \mathbf{m}_i)$$
- Enforces strict event-driven memory updates so no future message affects historical node states.

---

## 6. Champion Model & Objective Formulation

The finalized production model is the **Hybrid Streaming Topology + TGN Embeddings + Focal-Loss XGBoost Ensemble**:

$$f^*(e_i) = \text{XGBoost}\Big([\mathbf{x}_{\text{ord}},\, \mathbf{x}_{\text{topo}},\, \mathbf{z}_{\text{tgn}}];\, \mathcal{L}_{\text{obj}}(\gamma^*),\, \Theta^*\Big)$$

### Loss Formulation:
- **$\alpha$-Free Focal Loss** (for BankSim, SAP Würzburg, Synth ERP):
  $$\mathcal{L}_{\text{focal}}(p_t) = -(1 - p_t)^\gamma \log(p_t)$$
  where $p_t = p$ if $y=1$ else $1-p$. The parameter $\gamma$ dynamically down-weights easy negatives without requiring arbitrary alpha balancing ($\gamma = 1.0$ for BankSim/Synth ERP, $\gamma = 2.0$ for SAP Würzburg).
- **Scale Position Weighting** (for IBM AML):
  $$\text{scale\_pos\_weight} = \frac{N_{\text{neg}}}{N_{\text{pos}}}$$

### Validation Threshold Freezing (Rule 2):
The operational classification threshold $\bar{\tau}$ is strictly tuned on the **validation split** to maximize $F_1$ or bounded $P@K$, and then frozen:
$$\bar{\tau} = \arg\max_{\tau} F_1(\mathcal{D}_{\text{val}}, \tau)$$
All reported test metrics use $\bar{\tau}$. Metrics are **never** reported at an arbitrary default $0.5$ threshold.

---

## 7. Empirical Results & Within-Dataset Ablation

### 7.1 Test-Split PR-AUC Across Model Progression Arms (3-Seed Mean $\pm$ Std)

| Model Arm | BankSim PR-AUC | IBM AML PR-AUC | SAP Würzburg PR-AUC | Synth ERP PR-AUC |
|---|---|---|---|---|
| **Baseline (Ordinary Tabular)** | 0.7870 $\pm$ 0.0700 | 0.9920 $\pm$ 0.0026 | **0.1581 $\pm$ 0.0129** | 0.2483 $\pm$ 0.0602 |
| **+ Structure Only (Pure Graph)** | 0.8924 $\pm$ 0.0035 | 0.9922 $\pm$ 0.0025 | 0.0734 $\pm$ 0.0081 | 0.4120 $\pm$ 0.1205 |
| **+ All Topology (Handcrafted)** | 0.9319 $\pm$ 0.0017 | 1.0000 $\pm$ 0.0000 | 0.0717 $\pm$ 0.0095 | 0.4569 $\pm$ 0.1547 |
| **+ TGN Embeddings (Learned)** | 0.9196 $\pm$ 0.0012 | 0.9872 $\pm$ 0.0101 | 0.0594 $\pm$ 0.0241 | 0.6972 $\pm$ 0.0004 |
| **Final Champion (Topo+TGN+HPO)** | **0.9364 $\pm$ 0.0015** | **1.0000 $\pm$ 0.0000** | 0.1557 $\pm$ 0.0717 | **0.7784 $\pm$ 0.0053** |

### 7.2 State-of-the-Art (SOTA) Comparison

| Dataset | Method / Reference | Model Family | Test PR-AUC | Precision@100 |
|---|---|---|---|---|
| **BankSim** | Random Forest (Lopez-Rojas et al. 2016) | Tabular Ensemble | 0.7420 | 0.9100 |
| | GraphSAGE (Weber et al. 2019) | Static Graph Neural Net | 0.8120 | 0.9400 |
| | Standard XGBoost (No Topology) | Tabular Gradient Boosted | 0.7870 | 0.9633 |
| | **FedProx Consensus (Ours, Privacy-Preserving)** | Federated Score Ensemble | **0.9140** | **1.0000** |
| | **Proposed Champion (Ours)** | Hybrid Topology + TGN | **0.9364** | **1.0000** |
| **IBM AML** | Random Forest Baseline | Tabular Ensemble | 0.8840 | 0.9600 |
| | EvolveGCN (Pareja et al. 2020) | Dynamic Recurrent Graph | 0.9120 | 0.9800 |
| | Standalone TGN (Rossi et al. 2020) | Continuous Graph Network | 0.9872 | 1.0000 |
| | **Proposed Champion (Ours)** | Hybrid Topology + TGN | **1.0000** | **1.0000** |
| **SAP Würzburg** | Autoencoder Anomaly (Schreyer et al. 2020) | Deep Unsupervised | 0.1240 | 0.0500 |
| | Baseline XGBoost (Ordinary GL) | Tabular Gradient Boosted | **0.1581** | 0.0733 |
| | **Proposed Champion (Ours)** | Hybrid Topology + TGN | 0.1557 | **0.1033** |

---

## 8. Critical Scientific Discoveries & Null Results

Agents working on this project must be aware of four empirical truths that contradict naive academic assumptions:

1. **The Cycle Null Result**:
   - *Discovery*: Directed cycle features (`in_cycle_len3`, `in_cycle_len4`, `cycle_amount_ratio`) carry near-zero gain importance ($< 0.005$) on BankSim, IBM AML, and SAP Würzburg.
   - *Reason*: In real financial systems, fraudsters rarely route funds in complete closed loops back to the originator. Instead, they structure transactions as fan-out layering chains into exit sinks (crypto gateways, cash mules). Degree bursts and monetary velocity dominate tree splits.

2. **The Relational ERP Negative Lift**:
   - *Discovery*: On SAP Würzburg, introducing pure graph topology drops PR-AUC from 0.1581 to 0.0717 ($-54.6\%$).
   - *Reason*: In double-entry accounting ledgers, high fan-in accounts represent legitimate clearing hubs (payroll clearing accounts, value-added tax liabilities, cash settlement). Pure topology flags these legitimate clearing hubs as anomalous sinks, generating false positives.

3. **The ROC-AUC Fallacy**:
   - *Discovery*: On datasets with $<0.1\%$ fraud, ROC-AUC is artificially inflated by millions of true negatives. For example, on SAP Würzburg, a naive classifier achieves **0.991 ROC-AUC** while yielding a dismal **0.155 PR-AUC**.
   - *Standard*: PR-AUC (Average Precision) and operational Precision@K ($K \in \{50, 100, 500, 1000\}$) are the only acceptable honesty metrics.

4. **Synthetic Data Augmentation Penalty**:
   - *Discovery*: Naively training on mixed real + synthetic data degraded real-world test PR-AUC. Hand-crafted topology on real data consistently beat synthetic augmentation unless models were strictly calibrated against the target economy's empirical degree distributions.

---

## 9. Privacy-Preserving Federated Consensus (FedProx)

To address bank secrecy and cross-border data privacy regulations (GDPR, GLBA), the project establishes a **Score-Level Ensemble Consensus** architecture across $K=4$ heterogeneous non-IID banking institutions.

### Institutional Clients Partitioning (BankSim):
- **Client 0 (Retail Core)**: 87.5% transaction volume, 0.38% fraud rate.
- **Client 1 (High-Risk Gateway)**: 0.6% volume, 18.67% fraud rate (specialized target).
- **Client 2 (Commercial B2B)**: 4.2% volume, 14.0% fraud rate.
- **Client 3 (Regional Branch)**: 7.7% volume, 2.3% fraud rate.

### Empirical Validation Reliability Weighting:
Rather than uniform score averaging (which allows fraud-starved institutions to dilute consensus), the global consensus weights each client $k$ by its empirical validation PR-AUC:

$$w_k = \frac{\text{PR-AUC}_{\text{val}, k}^\beta}{\sum_{j=1}^K \text{PR-AUC}_{\text{val}, j}^\beta}, \quad \hat{p}_{\text{consensus}}(e_i) = \sum_{k=1}^K w_k \cdot f_k(e_i)$$

### Performance Results:
- **Centralized Upper Bound**: 0.9241 PR-AUC (100% parity, violates privacy).
- **Isolated Local-Only**: 0.8547 PR-AUC (92.49% parity).
- **Federated FedProx Consensus**: **0.9140 PR-AUC** (recovers **98.91%** of centralized bound with zero raw data sharing).
- **Client 1 Blind Spot**: Client 1 achieves 0.8338 PR-AUC locally but drops to **0.7479 PR-AUC** (-8.6% penalty) when exposed to global streams. FedProx resolves this blind spot completely, achieving 0.9140.

---

## 10. Explainability & Two-Layer Forensic Alert Packets

Forensic auditors under SOX and Basel III require mathematical proof of why an alert was triggered.

### Layer 1: Exact TreeSHAP in Log-Odds Margin Space
Attributions are calculated via XGBoost's native `pred_contribs` algorithm:
$$\sum_{j=1}^M \phi_j(x_i) + \phi_0 = f_{\text{margin}}(x_i)$$
This runs the exact TreeSHAP recursion as a pure tree traversal. It is exact (not sampled) and additive in log-odds space.

### Layer 2: Reconstructed Neo4j Cypher Subgraph Evidence
When an anomaly exceeds $\bar{\tau}$, the console executes a deterministic Cypher query to pull the surrounding 2-hop transaction subgraph from Neo4j:
```cypher
MATCH (u:Account {id: $src_id})-[e1:TRANSFERRED*1..2]-(v:Account)
WHERE e1.timestamp <= $tx_timestamp AND e1.timestamp >= $tx_timestamp - 2592000
RETURN u, e1, v LIMIT 50;
```
The resulting alert packet bundles:
- `transaction_id`, `amount`, `timestamp`
- Top 3 driving features with signed contributions (e.g., `+0.43 log_amount`, `+0.29 dest_in_degree`)
- Reconstructed graph nodes and edges for visual rendering in the audit console.

---

## 11. Production Architecture & Enterprise Invariants

The production platform comprises an asynchronous FastAPI scoring backend, a PostgreSQL financial ledger, a Redis cache/distributed lock, Neo4j graph storage, and a React 18 TypeScript console.

### Database-Enforced Financial Invariants (PostgreSQL Triggers):
Ledger integrity is guaranteed at the database engine level, not in application code:
1. **Double-Entry Balance Trigger**:
   A deferred constraint trigger on `journal_lines` asserts $\sum \text{Debits} = \sum \text{Credits}$ across each transaction at commit time. Postings with unbalanced debits/credits raise an immediate SQL exception.
2. **Period Close Guard**:
   A `BEFORE INSERT` trigger rejects ledger entries posted to closed fiscal accounting periods.
3. **Immutable Audit Trail**:
   Triggers unconditionally reject `UPDATE` and `DELETE` commands on the `audit_log` table.
4. **Duplicate-Payment Defense**:
   Idempotency middleware paired with `SELECT ... FOR UPDATE` locks on invoice records prevents duplicate disbursements under concurrent asynchronous race conditions.

### Serving Parity & Latency:
- `tests/test_online_topology_parity.py` replays 20,000 real transactions through both batch and streaming engines, asserting **zero column mismatches** across all 13 topology features.
- Online scoring latency executes in **$< 2.5\text{ ms}$** per transaction.

---

## 12. Complete Codebase Directory Map

```text
Shadow_project_1/
├── app/                               # Enterprise FastAPI Application
│   ├── api/                           # REST endpoints (alerts, ledger, federated)
│   ├── core/                          # Config, security, DB connections
│   ├── db/                            # PostgreSQL session & SQLAlchemy models
│   ├── services/                      # Scoring service & federated consensus service
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
│   ├── banksim/                       # BankSim evaluation logs & metrics
│   ├── ibm_aml/                       # IBM AML evaluation logs & metrics
│   └── federated_table.md             # Consolidated cross-institutional metrics
├── src/                               # Core Python Modules
│   ├── features/                      # Deterministic ingestion & preprocessing
│   ├── federated/                     # Client, Server, and Partition implementations
│   ├── graph/                         # Neo4j connector & Cypher query builder
│   ├── modeling/                      # XGBoost, focal loss, TreeSHAP, TGN wrappers
│   └── topology/                      # Streaming leakage-free WindowGraph engine
├── tests/                             # Comprehensive automated test suite
│   ├── test_online_topology_parity.py # Streaming vs batch parity assertion
│   ├── test_federated.py              # Federated aggregation & reliability tests
│   └── test_cycle_path.py             # Bounded cycle search test
├── tools/                             # Repository tooling
│   └── large_files.py                 # Split/restore/verify engine for large files
├── web/                               # React 18 / TypeScript Audit Console
│   ├── src/pages/Alerts.tsx           # Real-time forensic alert review
│   ├── src/pages/Federated.tsx        # Multi-bank federated consensus monitoring
│   └── src/App.tsx                    # Frontend router & navigation
├── CLAUDE.md                          # Source of truth rules & invariants
├── MODELS_AND_TECHNIQUES.md           # Master technical guide (root copy)
├── pyproject.toml                     # Dependencies & build configuration
└── HOW_TO_RUN.md                      # Operational CLI runbook
```

---

## 13. Operational CLI Runbook

### Environment Setup:
```bash
# Initialize Python virtual environment
python -m venv .venv
source .venv/bin/activate  # Or on Windows: .venv\Scripts\activate

# Install package in editable mode with dependencies
pip install -e .
```

### Large File Management (Overcoming GitHub 100MB Limit):
```bash
# Rebuild large datasets after git clone
python -m tools.large_files restore

# Verify integrity against MANIFEST.json
python -m tools.large_files verify

# Split updated datasets into 90MB chunks before git commit
python -m tools.large_files split
```

### Running Key Experiments & Benchmarks:
```bash
# 1. Run Leakage-Free Feature Extraction on BankSim
python experiments/run_dataset.py --dataset banksim

# 2. Run the 7-Arm Within-Dataset Ablation
python experiments/ablation.py --dataset banksim

# 3. Run Federated Learning Simulation (K=4, FedProx)
python experiments/federated.py --dataset banksim --clients 4 --strategy fedprox

# 4. Run Modern TGN Embedding Probe
python experiments/modern.py --dataset banksim
```

### Running Test Suite:
```bash
# Run streaming-to-batch parity assertion (20,000 transactions)
pytest tests/test_online_topology_parity.py -v

# Run federated consensus test
pytest tests/test_federated.py -v
```

### Launching the Production Audit Console:
```bash
# 1. Start FastAPI backend (Port 8000)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 2. Start React Web Console (Port 5173)
cd web
npm install
npm run dev
```

---

## 14. Invariants & Strict Rules for AI Agents

Any AI agent interacting with or extending this codebase **must** adhere to these principles:

1. **Never Violate Read-Then-Insert**: Under no circumstances should feature extraction code compute global statistics over future timestamps or look ahead in the transaction stream.
2. **Never Use Whole-Dataset Normalization**: All scaling, z-scores, and mean aggregations must be computed via running/expanding estimators (e.g., Welford algorithm) over past observations only.
3. **Never Randomly Shuffle Folds**: Cross-validation must strictly partition data chronologically (e.g., $t < T_1$ train, $T_1 \le t < T_2$ val, $t \ge T_2$ test).
4. **Never Commit Unchunked Files $> 90\text{ MB}$**: Always run `python -m tools.large_files split` and ensure large raw data files are ignored by git.
5. **Preserve One Imbalance Mechanism**: Do not mix SMOTE oversampling with class weighting. Prefer $\alpha$-free focal loss or scale-position weights.
6. **Freeze Thresholds on Validation**: Do not report test metrics at an uncalibrated default threshold of 0.5.
7. **Report PR-AUC and Precision@K**: Never declare success using ROC-AUC on imbalanced fraud datasets.
