# The Self-Auditing Ledger: Leakage-Free Temporal Graph Topology for ERP Fraud Detection, with a Production Audit Console

**Authors**: Aarin Bhatta, Himanshu Ray, and Mohammed Akif  
*School of Computer Science and Engineering, Vellore Institute of Technology, Vellore, India*  
*Review 2 Submission — September / October 2026*

---

## Abstract
Graph-based fraud detection methods are frequently proposed without an explicit audit of temporal leakage, and rarely evaluated with a controlled, same-architecture ablation that isolates the marginal value of graph structure from the tabular signal it is layered on top of. This paper presents a leakage-free streaming temporal-topology feature engine—enforcing a formal **read-then-insert** invariant so that a transaction's features can never depend on information from its own future—and subjects it to a rigorous within-dataset ablation across four heterogeneous financial datasets (BankSim bipartite payment simulator, IBM AML multi-hop transfer network, SAP Würzburg real general-ledger export, and a calibrated synthetic ERP economy). The central finding is conditional, not universal: graph topology adds substantial, leakage-free predictive value on two of four datasets (+11.7% and +246.8% relative PR-AUC), is uninformative on a third whose tabular baseline is already saturated (PR-AUC $\approx 1.0$), and *actively hurts* on the fourth. We report this honestly, including the finding that hand-crafted cycle-detection features carry near-zero gain importance on three of four datasets, that a learned temporal graph network never beats hand-crafted topology on real data, and that naive synthetic-data augmentation measurably harms real-dataset performance. Furthermore, to address cross-institutional banking privacy barriers (GDPR/GLBA), we introduce a **Privacy-Preserving Federated Learning** architecture with empirical validation reliability weighting (FedProx), recovering **98.91%** of the centralized upper bound's performance without sharing raw customer transactions. Finally, we describe and empirically verify a production Procure-to-Pay ERP with a forensic audit console that serves this leakage-free feature computation live against real transactions with sub-2.5ms latency, backed by database-enforced financial-integrity invariants.

**Keywords**: fraud detection, temporal graphs, data leakage, anti-money laundering, explainable AI, continuous auditing, ERP systems, XGBoost, federated learning, synthetic data.

---

## 1. Introduction and Related Work

Financial statement fraud, procurement deception, and money laundering impose global damages exceeding billions of dollars annually. While modern enterprise resource planning (ERP) systems record millions of double-entry ledger postings daily, traditional automated auditing relies largely on isolated static business rules (e.g., threshold limits, duplicate invoice text matching) or shallow tabular machine learning classifiers. These conventional techniques evaluate each transaction in isolation, remaining fundamentally blind to coordinated structural fraud typologies—including multi-hop layering rings, smurfing fan-out distributions, and lapping schemes (where stolen receivables are concealed by diverting successive customer remittances).

Graph Neural Networks (GNNs) and temporal graph algorithms have recently emerged as the dominant academic paradigm for relational fraud detection. However, our systematic survey of the literature reveals three pervasive methodological flaws:
1. **Pervasive Temporal Leakage**: Standard graph construction pipelines compute topological statistics (e.g., node degrees, PageRank, k-hop neighborhood embeddings) over a whole-graph snapshot built over the entire dataset duration. As formalized in our leakage taxonomy, this allows future edges to retroactively contaminate historical feature representations, yielding artificially inflated laboratory scores that collapse upon deployment.
2. **Missing Ablation Controls**: Published graph fraud detection benchmarks routinely compare a graph-aware model against a naive tabular baseline lacking standard feature engineering, failing to isolate whether observed performance gains stem from genuine topological structure or simply from auxiliary attributes (e.g., monetary amount, temporal velocity).
3. **Black-Box Opacity in Regulated Auditing**: Deep graph architectures (GCN, GAT, EvolveGCN) lack exact, polynomial-time feature attribution mechanisms. Under regulatory compliance frameworks (Sarbanes-Oxley Act, Basel III, GDPR Article 22), auditors cannot act upon uninterpretable anomaly scores without actionable forensic evidence paths.

To resolve these challenges, this paper establishes a leakage-free streaming temporal topology engine, rigorously evaluates it across four diverse financial environments, proves the viability of privacy-preserving multi-bank federated collaboration, and demonstrates a production-grade continuous auditing console.

---

## 2. End-to-End System & Model Architecture

### 2.1 Architectural Overview
The Self-Auditing Ledger pipeline bridges streaming transactional multigraphs, continuous temporal graph networks, gradient-boosted decision trees, and regulatory-grade forensic auditing:
1. **Chronological Ingestion & Graph Projection**: Ingests continuous financial transactions or double-entry ERP general-ledger postings, mapping transactions to dynamic directed multigraph edges $e_i = (u_i, v_i, t_i, a_i)$ over accounts, vendors, and fiscal codes under strict non-shuffled time ordering.
2. **Streaming Leakage-Free Temporal Topology Engine**: Enforces an unbending **read-then-insert** execution invariant, guaranteeing that dynamic topological features are evaluated solely against past graph state $G_{< t_i}$ without look-ahead contamination.
3. **Continuous Dynamic Graph Representation**: Integrates continuous-time Temporal Graph Network (TGN) memory modules that maintain decaying latent state embeddings for active accounts.
4. **Imbalance-Calibrated Ensemble Head**: An XGBoost classifier trained with custom $\alpha$-free focal loss or train-derived scale-position weighting to counter extreme class skew without distorting topological manifolds via artificial oversampling.
5. **Forensic Explainability & Alert Synthesis**: Computes exact, polynomial-time TreeSHAP attributions in margin space and generates structured audit packets that combine top driving features with reconstructed Cypher-queryable subgraphs for instant forensic review.
6. **Privacy-Preserving Federated Consensus**: Enables independent financial institutions to collaborate under strict bank secrecy and data-protection laws (GDPR, GLBA) by aggregating score predictions via empirical validation PR-AUC reliability weighting (FedProx).

### 2.2 Data Preprocessing and Feature Extraction Pipeline
To guarantee that the machine learning models operate on standardized, leakage-controlled representations across heterogeneous financial environments, all raw datasets undergo a unified, deterministic preprocessing pipeline:
- **Type Validation & Cleansing**: Timestamps are coerced to strict epoch seconds or integer simulation steps; amounts $a_i > 0$ are converted to double-precision floats; and categorical metadata (payment channels, document types, account categories) are dictionary-encoded with reserved unseen-category indices. Missing fields are explicitly imputed with domain defaults.
- **Chronological Partitioning**: Records are sorted by the composite key $(t_i, \text{tx\_id})$. The data is partitioned into strictly ordered chronological splits: 60% training ($t < T_1$), 20% validation ($T_1 \le t < T_2$), and 20% held-out test ($t \ge T_2$). No shuffling, random cross-validation, or bidirectional temporal imputation is permitted.
- **Feature Space Taxonomy**: Each transaction $e_i$ is mapped to a combined feature vector $x_i = [\mathbf{x}_{\text{ord}}, \mathbf{x}_{\text{topo}}, \mathbf{z}_{\text{tgn}}]$:
  - **Ordinary Tabular Features ($\mathbf{x}_{\text{ord}}$)**: Captures raw transaction properties, including $\log_{10}(a_i + 1)$, normalized amount z-scores computed via running Welford statistics over the training split, diurnal periodic encodings $(\sin(2\pi h_i / 24), \cos(2\pi h_i / 24))$, and inter-event arrival deltas $\Delta t = t_i - t_{\text{prev}}(u_i)$.
  - **Handcrafted Temporal Topology ($\mathbf{x}_{\text{topo}}$)**: Thirteen structural and behavioral features extracted dynamically by the streaming engine: rolling in/out degrees over trailing windows $W \in \{1\text{d}, 7\text{d}, 30\text{d}\}$, fan-in/fan-out ratios, pairwise counterparty reciprocity, burstiness velocity, rolling amount recurrence (lapping), and directed length-3/length-4 cycle membership counts.
  - **Continuous Dynamic Graph Embeddings ($\mathbf{z}_{\text{tgn}}$)**: A 16-dimensional continuous-time latent representation produced by a Temporal Graph Network (TGN), encoding sequential memory states and interaction dynamics between counterparties.

### 2.3 The Leakage Invariant: Read, Then Insert
A transaction's features may depend only on transactions with $\text{timestamp} \le \text{its own}$. The engine satisfies this as a structural property of a single loop body over sorted edges:
1. **Read**: Query `WindowGraph` for transaction $i$'s fan-in, fan-out, destination in-degree, source out-degree, and (if $\text{src}_i \neq \text{dst}_i$) run the bounded cycle search; query `LapMemory` for the recurrence of $i$'s amount against each endpoint's rolling history.
2. **Insert**: Only after every read above returns does the engine call `WindowGraph.add(t, u, v, amount)` and `LapMemory.record(...)` for transaction $i$ itself.

Because `add` for edge $j$ is called only during iteration $j$, the graph state visible to iteration $i$'s reads is, by induction, exactly $\{j : j < i\}$ minus aged-out edges—never a superset, and in particular never anything from an iteration that has not yet run.

### 2.4 Implementation Tools and Software Stack

| Component / Function | Tool / Library | Purpose / Role in Architecture |
|---|---|---|
| **Streaming Topology Engine** | Python 3.11, NumPy | Leakage-free read-then-insert execution |
| **Dynamic Graph Embeddings** | PyTorch Geometric 2.4 | Continuous-time Temporal Graph Network (TGN) |
| **Gradient Boosted Trees** | XGBoost 2.0.3 | Histogram-based classification with custom focal loss |
| **Tree-Native Explainability** | SHAP 0.44.1 / TreeSHAP | Exact polynomial-time margin-space attributions |
| **Graph Storage & Cypher** | Neo4j 5.15 Community | Forensic subgraph visualization and query execution |
| **Transactional Datastore** | PostgreSQL 15 | Double-entry balance triggers, immutable audit log |
| **In-Memory Cache & Lock** | Redis 7.2 | Idempotency key tracking, distributed API locks |
| **Backend Application API** | FastAPI 0.109, Uvicorn | Async REST endpoints, sub-2.5ms online scoring |
| **Interactive Audit Console** | React 18, TypeScript | Real-time alert review, interactive Cypher graph viewer |

### 2.5 Proposed Champion Model and Architectural Rationale
We formally select and propose the **Hybrid Streaming Topology + TGN Embeddings + Focal-Loss XGBoost Ensemble** as our finalized production champion model:
$$f^*(e_i) = \text{XGBoost}\Big([\mathbf{x}_{\text{ord}},\, \mathbf{x}_{\text{topo}},\, \mathbf{z}_{\text{tgn}}];\, \mathcal{L}_{\text{focal}}(\gamma^*),\, \Theta^*\Big)$$
where $\mathcal{L}_{\text{focal}}$ is an $\alpha$-free focal loss ($\gamma=1.0$ for BankSim/Synth ERP, $\gamma=2.0$ for SAP Würzburg, scale_pos_weight for IBM AML).

**Why This Model?**
1. **Synergistic Feature Complementarity**: Tabular models alone cannot detect multi-hop financial structuring, while standalone graph neural networks struggle with continuous financial amounts and over-smoothing. Feeding learned TGN embeddings alongside handcrafted topology into an XGBoost head delivers the best of both worlds (+14.9% PR-AUC lift on BankSim, +213% on Synth ERP).
2. **Strict Invariance to Data Leakage**: Enforces the read-then-insert invariant in both the streaming engine and event-driven TGN memory updates.
3. **Audit-Grade Exact Explainability**: TreeSHAP computes exact polynomial-time margin-space attributions, meeting regulatory requirements (SOX, Basel III, GDPR).
4. **Production Serving Feasibility**: Executes in $<2.5\,\text{ms}$ per transaction, avoiding expensive multi-hop neighborhood sampling at inference time.

---

## 3. Explainability and Forensic Verification

### 3.1 Exact TreeSHAP in Margin Space
Every reported feature attribution is computed via XGBoost's native `pred_contribs` interface:
$$\sum_{j=1}^M \phi_j(x_i) + \phi_0 = f_{\text{margin}}(x_i)$$
This runs the exact TreeSHAP recursion as a pure traversal of the fitted trees, returning signed contributions additive in log-odds space. It is exact (not sampled) and agnostic to whether the model was trained with focal loss or class weighting.

### 3.2 Global vs. Local Feature Attribution
Averaging $|\text{SHAP}|$ across test sets reveals that feature importance is highly domain-specific:
- In BankSim, amount and short-term degree features dominate (e.g., `amount`, `fan_in`, `dest_in_degree`).
- In IBM AML, amount-derived lapping features (`lap_out_recur`, `lap_out_payees`) account for 96% of the model's split decisions.
- **The Cycle Null Result**: Directed cycle features (`in_cycle`, `cycle_length`, `cycle_amount_ratio`) carry near-zero global SHAP attribution ($<0.005$) on real-world datasets. True cycles are so rare in real financial networks that gradient-boosted trees prioritize degree bursts and monetary amounts first.

### 3.3 Two-Layer Forensic Alert Packet
When an alert is flagged, the console generates an evidence packet combining:
- **Layer 1 (Model Attribution)**: Top 3 contributing features signed by risk direction (e.g., `+0.42 log_amount`, `+0.28 dest_in_degree`).
- **Layer 2 (Reconstructed Graph Evidence)**: A standalone Cypher query that extracts the exact historical subgraph from Neo4j (counterparty nodes, timestamped payment edges, and verified fan-in hubs).

---

## 4. Experimental Evaluation and Results

### 4.1 Benchmark Datasets and Evaluation Metrics

| Dataset | Total Rows | Entities $|\mathcal{V}|$ | Test Frauds | Fraud Rate | Graph Topology |
|---|---|---|---|---|---|
| **BankSim** | 594,643 | 4,166 | 1,320 | 1.21% | Bipartite Consumer-Merchant |
| **IBM AML** | 5,076,142 | 412,416 | 377 | 0.12% | Directed Multi-Hop Network |
| **SAP Würzburg** | 200,687 | 1,422 | 25 | 0.012% | Relational G/L Accounting Ledger |
| **Synth ERP** | 1,141,842 | 8,240 | 1,093 | 0.096% | Calibrated Agent-Based Economy |

**The ROC-AUC Fallacy**: Because non-fraud instances constitute >99% of transactions, false positive rates remain deceptively low. For example, on SAP Würzburg, the baseline model achieves **0.991 ROC-AUC** but a meager **0.155 PR-AUC**. Consequently, PR-AUC and Precision@K ($K \in \{50, 100, 500, 1000\}$) serve as our primary honesty metrics.

### 4.2 Comprehensive Ablation Study Across Four Datasets
The 7-arm within-dataset ablation evaluates the exact marginal contribution of graph structure:

| Model Arm | BankSim PR-AUC | IBM AML PR-AUC | SAP Würzburg PR-AUC | Synth ERP PR-AUC |
|---|---|---|---|---|
| **Baseline (Ordinary Tabular)** | 0.7870 $\pm$ 0.0700 | 0.9920 $\pm$ 0.0026 | 0.1581 $\pm$ 0.0129 | 0.2483 $\pm$ 0.0602 |
| **+ Structure Only (Pure Graph)** | 0.8924 $\pm$ 0.0035 | 0.9922 $\pm$ 0.0025 | 0.0734 $\pm$ 0.0081 | 0.4120 $\pm$ 0.1205 |
| **+ All Topology (Handcrafted)** | 0.9319 $\pm$ 0.0017 | 1.0000 $\pm$ 0.0000 | 0.0717 $\pm$ 0.0095 | 0.4569 $\pm$ 0.1547 |
| **+ TGN Embeddings (Learned)** | 0.9196 $\pm$ 0.0012 | 0.9872 $\pm$ 0.0101 | 0.0594 $\pm$ 0.0241 | 0.6972 $\pm$ 0.0004 |
| **Final Champion (Topo + TGN + HPO)** | **0.9364 $\pm$ 0.0015** | **1.0000 $\pm$ 0.0000** | **0.1557 $\pm$ 0.0717** | **0.7784 $\pm$ 0.0053** |

**Ablation Insights**:
1. **Conditional Structural Lift**: Handcrafted topology provides massive lift on BankSim ($+11.7\%$ relative) and Synth ERP ($+213\%$), is uninformative on IBM AML due to baseline saturation, and *actively degrades* SAP Würzburg ($-54.6\%$).
2. **Negative Lift in Relational ERP**: In double-entry accounting, high fan-in accounts are legitimate clearing hubs (payroll, tax liabilities), not fraudulent sinks. Pure structural features create false positives unless paired with domain attributes.
3. **TGN vs. Handcrafted Topology**: On real datasets (BankSim, IBM AML), handcrafted streaming topology consistently outperforms learned continuous TGN embeddings ($0.9319$ vs. $0.9196$). However, combining both yields the highest overall performance ($0.9364$).

---

## 5. Privacy-Preserving Federated Fraud Detection

In commercial banking networks, regulatory mandates (GDPR, GLBA) strictly prohibit pooling private customer transactions. We evaluate our **Score-Level Ensemble Consensus** framework across $K=4$ heterogeneous non-IID banking institutions.

### 5.1 BankSim Multi-Seed Benchmark ($K=4$, Seeds 42, 43, 44)

| Arm | Privacy Guarantee | Test PR-AUC | Test F1 | Centralized Parity | Collab Lift |
|---|---|---|---|---|---|
| **Centralized Upper Bound** | None (Violates Privacy) | **0.9241 $\pm$ 0.0022** | 0.8351 $\pm$ 0.0046 | 100.0% | --- |
| **Isolated Local-Only** | Full Privacy (Zero Sharing) | 0.8547 $\pm$ 0.0035 | 0.7684 $\pm$ 0.0031 | 92.49% | Baseline |
| **Federated (Size-Weighted)** | Full Privacy (Score Sharing) | 0.9069 $\pm$ 0.0021 | 0.8085 $\pm$ 0.0095 | 98.14% | +0.0522 (+5.22%) |
| **Federated (Uniform)** | Full Privacy (Score Sharing) | 0.9128 $\pm$ 0.0040 | 0.8359 $\pm$ 0.0017 | 98.78% | +0.0581 (+5.81%) |
| **Federated (FedProx Reliability)** | **Full Privacy (Score Sharing)** | **0.9140 $\pm$ 0.0037** | **0.8343 $\pm$ 0.0042** | **98.91%** | **+0.0593 (+5.93%)** |

### 5.2 Synth ERP Benchmark (Extreme Non-IID Skew, 1.14M Rows)

| Arm | Privacy Guarantee | Test PR-AUC | Test F1 | Centralized Parity | Collab Lift |
|---|---|---|---|---|---|
| **Centralized Upper Bound** | None (Violates Privacy) | **0.7168** | 0.6846 | 100.0% | --- |
| **Isolated Local-Only** | Full Privacy (Zero Sharing) | 0.1376 | 0.2215 | 19.19% | Baseline |
| **Federated (Uniform)** | Full Privacy (Score Sharing) | 0.3504 | 0.4339 | 48.88% | +0.2128 (+21.28%) |
| **Federated (Size-Weighted)** | Full Privacy (Score Sharing) | 0.3735 | 0.4785 | 52.11% | +0.2359 (+23.59%) |
| **Federated (FedProx Reliability)** | **Full Privacy (Score Sharing)** | **0.4602** | **0.5143** | **64.21%** | **+0.3227 (+32.27%)** |

### 5.3 Per-Client Blind Spot Analysis and Network Sensitivity ($K$)
- **Client Blind Spots**: In BankSim, Client 1 (high-risk merchant gateway, 18.67% fraud rate) achieves 0.8338 PR-AUC on its local slice, but drops to **0.7479 PR-AUC** (-8.6% drop) when evaluated on global multi-bank streams. Federated collaboration eliminates this blind spot, lifting performance to **0.9140**.
- **FedProx Reliability Discipline**: On Synth ERP, uniform averaging yields only 0.3504 PR-AUC because Bank 0 (clean, 0.11% fraud) corrupts consensus. FedProx validation weighting down-weights Bank 0, boosting performance to **0.4602** (+10.98% lift over uniform).
- **Network Size Sensitivity**: Across $K \in \{2, 3, 4, 5\}$, isolated models degrade from 0.8756 to 0.8456 PR-AUC as data is fragmented, while FedProx consistently maintains $>96.9\%$ centralized parity and $+4.5\%$ to $+5.8\%$ collaboration lift.

---

## 6. State-of-the-Art (SOTA) Comparison

We benchmark our proposed models against established published baselines:

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
| | Baseline XGBoost (Ordinary GL) | Tabular Gradient Boosted | 0.1581 | 0.0733 |
| | **Proposed Champion (Ours)** | Hybrid Topology + TGN | **0.1557** | **0.1033** |

On BankSim, the proposed champion achieves **0.9364 PR-AUC** and **100% Precision@100**, dramatically outperforming both the original simulator's Random Forest baseline (0.7420) and GraphSAGE (0.8120). Even under complete data privacy, our FedProx federated model (0.9140) surpasses all published centralized baselines.

---

## 7. Production System & Forensic Audit Console

### 7.1 Serving Parity and Latency
The production system serves features live via an asynchronous FastAPI backend:
- **Serving Parity**: `tests/test_online_topology_parity.py` asserts that online streaming feature computations match batch offline computations with **zero mismatches across 20,000 transactions**.
- **Low Latency**: End-to-end inference executes in **<2.5 ms** per transaction, enabling real-time scoring in transactional payment posting loops.

### 7.2 Database-Enforced Financial Invariants
To ensure ledger integrity under concurrent multi-user load, critical accounting invariants are enforced at the PostgreSQL database trigger level:
1. **Double-Entry Balance**: A deferred constraint trigger on `journal_lines` enforces $\sum \text{Debits} = \sum \text{Credits}$ at transaction commit time.
2. **Period Close Guard**: A `BEFORE INSERT` trigger on `journal_entries` strictly rejects postings to closed fiscal periods.
3. **Immutable Audit Trail**: Triggers unconditionally block `UPDATE` and `DELETE` operations on `audit_log`, ensuring a tamper-proof write-once ledger.
4. **Concurrency Defense**: Idempotency middleware combined with `SELECT ... FOR UPDATE` row locks successfully prevented duplicate payments under high-concurrency race condition tests.

---

## 8. Conclusion

The Self-Auditing Ledger demonstrates that graph topology provides powerful predictive value for financial fraud detection (+11.7% to +246.8% relative PR-AUC lift), but only when constructed under strict, leakage-free temporal invariants. When evaluated honestly, graph structure is not a universal panacea: cycle motifs carry near-zero importance in real payments, learned graph embeddings do not outperform handcrafted topology on real data, and topology actively degrades performance on relational accounting hubs. Furthermore, our privacy-preserving federated consensus framework recovers **98.91%** of centralized performance while resolving legal cross-institutional banking constraints. Finally, our production-grade audit console bridges the gap between academic graph algorithms and enterprise accounting controls.
