# Models, Techniques, and Algorithms: From ETL to Feature Extraction and Classification

> **Project:** The Self-Auditing Ledger: Fraud Detection in ERP Systems Using Temporal Graph Topology  
> **Scope:** Comprehensive technical reference detailing every model, mathematical formulation, algorithm, and data engineering technique across all pipeline stages.

---

## Architectural Pipeline Overview

The Self-Auditing Ledger converts heterogeneous, streaming financial transactions into audit-grade fraud alerts through an end-to-end, leakage-free pipeline. The workflow transitions across seven core architectural stages:

`mermaid
flowchart TB
    %% ==========================================
    %% INPUT
    %% ==========================================
    subgraph INP ["Raw Inputs"]
        RAW["Raw Transaction CSVs / ERP Ledgers"]
    end

    %% ==========================================
    %% STAGE 1: ETL & INGESTION
    %% ==========================================
    subgraph S1 ["Stage 1: ETL and Ingestion"]
        M_SCHEMA["Canonical Schema Normalizer"]
        M_UNIF["Unified Account Namespace Engine"]
        M_BIP["Bipartite Graph Projector"]
        M_SORT["Deterministic Chronological Sorter"]
    end

    %% ==========================================
    %% STAGE 2: STREAMING TOPOLOGY ENGINE
    %% ==========================================
    subgraph S2 ["Stage 2: Streaming Temporal Topology Engine"]
        M_WG["WindowGraph Multigraph Structure"]
        M_ASOF["As-Of Streaming Causality Gate"]
        M_DFS["Depth-Bounded DFS Cycle Detector"]
        M_FLOW["Flow Conservation and Tightness Analyzer"]
        M_DEG["Sliding-Window Degree and Fan-In Velocity"]
        M_LAP["LapMemory Rolling Recurrence Detector"]
        M_INV["Invariance Regression Unit Testing"]
    end

    %% ==========================================
    %% STAGE 3: CONTINUOUS-TIME TGN
    %% ==========================================
    subgraph S3 ["Stage 3: Deep Dynamic Representation"]
        M_T2V["Time2Vec Temporal Harmonic Encoder"]
        M_TGN["Temporal Graph Network (TGN)"]
        M_GRU["Dual Asymmetric GRU Cells"]
        M_SSL["Self-Supervised Link Prediction Head"]
    end

    %% ==========================================
    %% STAGE 4: FEATURE ASSEMBLY & BASELINE
    %% ==========================================
    subgraph S4 ["Stage 4: Feature Assembly and Baseline"]
        M_EXP["Expanding Past-Only Statistics"]
        M_VEL["Backward Temporal Velocity"]
        M_FUSE["Multi-Family Feature Fusion Table"]
    end

    %% ==========================================
    %% STAGE 5: SUPERVISED CLASSIFICATION & HPO
    %% ==========================================
    subgraph S5 ["Stage 5: Supervised Classification and Optimization"]
        M_SPLIT["Chronological Time-Aware Split (70/15/15)"]
        M_FOCAL["Alpha-Free Custom Binary Focal Loss"]
        M_HPO["Optuna Bayesian HPO (TPE Sampler)"]
        M_XGB["XGBoost Decision Tree Ensemble"]
        M_THRESH["Validation Threshold Calibration"]
    end

    %% ==========================================
    %% STAGE 6: FORENSIC EXPLAINABILITY & AUDIT
    %% ==========================================
    subgraph S6 ["Stage 6: Forensic Explainability and Audit"]
        M_SHAP["TreeSHAP Feature Attribution Explainer"]
        M_TRI["Tri-Family Attribution Decomposition"]
        M_CYPHER["Neo4j Cypher Subgraph Traversal"]
        M_D3["Interactive D3/SVG Visual Trail"]
    end

    %% ==========================================
    %% STAGE 7: PRIVACY-PRESERVING FEDERATION
    %% ==========================================
    subgraph S7 ["Stage 7: Privacy-Preserving Federation"]
        M_DIR["Non-IID Dirichlet Partitioner"]
        M_FEDPROX["FedProx Proximal Optimizer"]
        M_CONSENSUS["Reliability-Weighted Score Consensus Server"]
    end

    %% Flow connections
    RAW --> M_SCHEMA
    RAW --> M_BIP
    M_SCHEMA --> M_UNIF
    M_BIP --> M_UNIF
    M_UNIF --> M_SORT
    
    M_SORT --> M_ASOF
    M_ASOF <--> M_WG
    M_WG --> M_DFS
    M_WG --> M_FLOW
    M_WG --> M_DEG
    M_ASOF <--> M_LAP
    M_WG -. Verified by .-> M_INV
    
    M_SORT --> M_T2V
    M_T2V --> M_GRU
    M_T2V --> M_SSL
    M_TGN <--> M_GRU
    
    M_SORT --> M_EXP
    M_SORT --> M_VEL
    
    M_DFS --> M_FUSE
    M_FLOW --> M_FUSE
    M_DEG --> M_FUSE
    M_LAP --> M_FUSE
    M_TGN --> M_FUSE
    M_SSL --> M_FUSE
    M_EXP --> M_FUSE
    M_VEL --> M_FUSE
    
    M_FUSE --> M_SPLIT
    M_SPLIT --> M_XGB
    M_FOCAL --> M_XGB
    M_HPO --> M_XGB
    M_XGB --> M_THRESH
    
    M_XGB --> M_SHAP
    M_SHAP --> M_TRI
    M_TRI --> M_D3
    M_SPLIT --> M_CYPHER
    M_CYPHER --> M_D3
    
    M_FUSE --> M_DIR
    M_DIR --> M_FEDPROX
    M_FEDPROX --> M_CONSENSUS
`

### High-Level Stage Flowchart

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   END-TO-END PIPELINE MAP                                       │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
  [Raw ERP Logs & CSVs]
         │
         ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ STAGE 1: ETL & Ingestion (Data Canonicalization & Namespace Unification)│
  └────────────────────────────────────────────────────────────────────────┘
         │
         ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ STAGE 2: Streaming Temporal Topology Engine (WindowGraph & Detectors)  │
  └────────────────────────────────────────────────────────────────────────┘
         │
         ├────────────────────────────────────────┬─────────────────────────┐
         ▼                                        ▼                         ▼
  ┌─────────────────────────┐      ┌─────────────────────────┐     ┌─────────────────────┐
  │ STAGE 3: Continuous-Time│      │ Handcrafted Streaming   │     │ STAGE 4: Tabular    │
  │ TGN Dynamic Embeddings  │      │ Topology Features       │     │ Expanding Statistics│
  └─────────────────────────┘      └─────────────────────────┘     └─────────────────────┘
         │                                        │                         │
         └────────────────────────────────────────┴─────────────────────────┘
                                                  │
                                                  ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ STAGE 4 (Cont.): Feature Fusion Table (Ordinary + Topology + TGN)      │
  └────────────────────────────────────────────────────────────────────────┘
         │
         ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ STAGE 5: Supervised Classification (XGBoost + Focal Loss + Optuna HPO) │
  └────────────────────────────────────────────────────────────────────────┘
         │
         ├────────────────────────────────────────┐
         ▼                                        ▼
  ┌────────────────────────────────────────┐  ┌────────────────────────────────────────┐
  │ STAGE 6: Dual Explainability Dispatch   │  │ STAGE 7: Privacy-Preserving Federation │
  │ (TreeSHAP Attributions + Neo4j Paths)  │  │ (Non-IID FedProx Score Consensus)     │
  └────────────────────────────────────────┘  └────────────────────────────────────────┘
```

---

## Stage 1: ETL & Ingestion (Data Canonicalization & Graph Construction)

The ETL stage (`src/etl/build.py`) ingests raw, disparate financial formats (IBM AML, BankSim, PaySim, SAP Würzburg) and transforms them into an immutable, chronological event stream while establishing the foundation for structural graph analysis.

```
       RAW CSVs (Heterogeneous Schemas)
                   │
                   ▼
  ┌─────────────────────────────────┐
  │ 1.1 Canonical Schema Mapping    │ ──► Maps source, dest, amount, timestamp, label
  └─────────────────────────────────┘
                   │
                   ▼
  ┌─────────────────────────────────┐
  │ 1.2 Unified Account Namespace   │ ──► Hashes senders & receivers into single ID space
  └─────────────────────────────────┘
                   │
                   ▼
  ┌─────────────────────────────────┐
  │ 1.3 Bipartite Projection (SAP)  │ ──► DOC:run:id ──[Line Item]──► GL:Account
  └─────────────────────────────────┘
                   │
                   ▼
  ┌─────────────────────────────────┐
  │ 1.4 Stable Chronological Sort   │ ──► (timestamp, transaction_id) deterministic order
  └─────────────────────────────────┘
```

### 1.1 Technique: Canonical Schema Normalization
* **File:** `src/etl/build.py` (`build_dataset`)
* **How It Works:** 
  Financial transaction datasets use conflicting column conventions (`nameOrig`, `nameDest`, `step`, `isFraud` vs. `Sender_Account`, `Receiver_Account`, `Timestamp`, `Is_Laundering`). The canonical mapping engine maps these heterogeneous fields into a strict standard edge schema:
  $$\mathcal{E} = \{\langle \text{transaction\_id}, \text{source\_account}, \text{dest\_account}, \text{amount}, \text{timestamp}, \text{label} \rangle\}$$
* **Why It Matters:** Decouples all downstream feature extractors, graph algorithms, and machine learning models from dataset-specific quirks.

### 1.2 Technique: Unified Account Namespace Transformation
* **File:** `src/etl/build.py`
* **How It Works:** 
  In naive implementations, sender accounts and receiver accounts are placed into disjoint string namespaces (e.g., prefixing `C_` for customer and `M_` for merchant). This caused a critical **99.3% identity-splitting bug** in predecessor frameworks: an entity receiving money in one transaction and sending money in another appeared as two disconnected nodes. The unified namespace normalizes all accounts into a single global set:
  $$\mathcal{V} = \text{Unique}(\text{source\_account} \cup \text{dest\_account})$$
* **Mathematical Consequence:** Makes directed multi-hop graph patterns (such as circular payment round-tripping $A \to B \to C \to A$) structurally traversable. Without this unification, cycles cannot exist in the graph.

### 1.3 Technique: Bipartite Document-Account Projection (SAP General Ledgers)
* **File:** `src/etl/build.py` (`_build_erp_ledger`)
* **How It Works:** 
  Real enterprise ERP systems (like SAP S/4HANA general ledgers `BKPF`/`BSEG`) operate on double-entry bookkeeping rather than peer-to-peer transfers. A single accounting journal document links multiple debit and credit postings across different General Ledger (G/L) accounts without explicit peer-to-peer sender/receiver pairs.
  We project this into a bipartite multigraph:
  $$\text{Source Node} = \text{"DOC:"} + \text{run\_id} + \text{":"} + \text{Belegnummer (Document ID)}$$
  $$\text{Dest Node} = \text{"GL:"} + \text{Hauptbuchkonto (G/L Account Number)}$$
* **Synthetic Continuous Time Axis:** Because SAP test runs only record time-of-day strings (`HH:MM:SS`), multi-run ledgers are assigned a run-contiguous time coordinate:
  $$\text{timestamp} = (\text{run\_index} \times 10^6) + \text{seconds\_since\_midnight}$$
  This prevents cross-run lookahead while maintaining chronological execution within each ledger run.

### 1.4 Technique: Evaluation Metadata Isolation
* **File:** `src/etl/build.py`
* **How It Works:** 
  Attributes like `alert_type` (e.g., `CYCLE`, `FAN_IN`) or `is_fraud_account` are label-derived metadata. The ETL pipeline strictly isolates these fields into an evaluation-only metadata track. They are persisted solely for post-hoc error analysis and audit logging, and are programmatically blocked from entering the feature assembly stage.

### 1.5 Technique: Deterministic Event Sequencing & Tie-Breaking
* **File:** `src/etl/build.py`
* **How It Works:** 
  Transactions are sorted using a stable chronological sort:
  $$\text{Order Key} = (\text{timestamp} \uparrow, \text{transaction\_id} \uparrow)$$
  Transactions sharing the exact same integer timestamp are processed strictly in monotonic ID order. A transaction can observe same-timestamp transactions that preceded it in sequence, but can never observe transactions with greater IDs or higher timestamps.

---

## Stage 2: Streaming Temporal Topology Engine

The Temporal Topology Engine (`src/topology/engine.py`, `src/topology/window_graph.py`, `src/topology/lap_memory.py`) computes structural graph anomaly features **as-of** the instant each transaction occurs, enforcing zero temporal lookahead.

```
Incoming Transaction e = (u, v, t, amount)
              │
              ▼
   ┌────────────────────────────────────────┐
   │ 2.1 FIFO Eviction: Drop edges < t - W  │
   └────────────────────────────────────────┘
              │
              ▼
   ┌────────────────────────────────────────┐
   │ 2.2 As-Of Feature Extraction (t < t_e) │
   │ • Shortest Cycle Search (DFS, L ≤ 5)   │
   │ • Amount Conservation & Time Span      │
   │ • Trailing Fan-In / In-Degree Velocity │
   │ • LapMemory Counterparty Recurrence    │
   └────────────────────────────────────────┘
              │
              ▼
   ┌────────────────────────────────────────┐
   │ 2.3 Edge Insertion into WindowGraph    │ ──► Edge added ONLY AFTER features recorded
   └────────────────────────────────────────┘
```

### 2.1 Data Structure & Model: `WindowGraph` (Incremental Directed Multigraph)
* **File:** `src/topology/window_graph.py`
* **How It Works:** 
  An in-memory directed multigraph operating over an explicit trailing time window $W \in \{\text{1h}, \text{24h}, \text{7d}, \text{30d}\}$.
  * Internal representation uses `collections.defaultdict(dict)` mapping integer-factorized accounts:
    $$\text{out}[u][v] = \text{multiplicity of directed edges } u \to v$$
    $$\text{in\_}[v][u] = \text{multiplicity of directed edges } v \leftarrow u$$
    $$\text{indeg}[v] = \sum_{u} \text{in\_}[v][u], \quad \text{outdeg}[u] = \sum_{v} \text{out}[u][v]$$
  * A FIFO queue `_edges = deque([(ts, u, v)])` tracks chronological additions.
  * **FIFO Eviction:** Calling `evict(now)` pops all edges where $\text{timestamp} < \text{now} - W$, decrementing degree counters and removing empty dictionary keys in amortized $\mathcal{O}(1)$ time.

### 2.2 Technique: As-Of Temporal Causality Discipline
* **File:** `src/topology/engine.py` (`extract_features`)
* **How It Works:** 
  The core structural safeguard against data leakage:
  1. The engine checks the current graph state for node $u$ and node $v$.
  2. All topological features for transaction $e_k = (u, v, t_k)$ are extracted from the graph **before** edge $e_k$ is added to the graph.
  3. Edge $e_k$ is inserted into `WindowGraph` **only after** its feature row is completely written.
* **Mathematical Guarantee:** Transaction $k$ cannot observe its own edge or any edge occurring at $t > t_k$.

### 2.3 Algorithm: Depth-Bounded Temporal Shortest Cycle Traversal
* **File:** `src/topology/window_graph.py` (`cycle_features`)
* **How It Works:** 
  When a candidate transfer $u \to v$ is evaluated, it will close a directed cycle if and only if there already exists an active path from $v$ back to $u$ in the trailing window ($v \rightsquigarrow u$).
  * The engine executes a depth-limited Breadth-First Search (BFS) / Depth-First Search (DFS) starting from destination $v$ aiming to reach source $u$.
  * Search is bounded by maximum cycle length $L_{\max} \le 5$ and an execution search budget of $4,000$ visited edges to prevent exponential blowup on dense nodes.
  * Generates:
    * `in_cycle`: Binary indicator ($1$ if path $v \rightsquigarrow u$ exists, else $0$).
    * `cycle_length`: Edge length of the shortest path $+ 1$ (closing edge).
    * `in_cycle_ge3`: Excludes simple 2-hop reciprocal transfers (e.g., standard merchant refunds $A \to B \to A$), focusing strictly on collusive rings of 3 or more entities ($A \to B \to C \to A$).

### 2.4 Mathematical Formulations: Flow Conservation & Tightness
* **File:** `src/topology/window_graph.py`
* **How It Works:** 
  Raw cycle membership produces high false-positive rates on common commercial loops. The engine extracts discriminative physical properties of the loop:
  1. **Amount-Conservation Ratio (`cycle_amount_ratio`):**
     $$\rho_{\text{amount}} = \frac{\min_{e \in \text{cycle}} \text{amount}(e)}{\max_{e \in \text{cycle}} \text{amount}(e)}$$
     In benign commercial trade, a payment and a partial refund have $\rho \ll 1$. In criminal money laundering and wash trading, capital is routed through intermediary accounts with minimal leakage, yielding $\rho \approx 1.0$.
  2. **Cycle Temporal Tightness (`cycle_time_span`):**
     $$\Delta t_{\text{cycle}} = t_{\text{current}} - \min_{e \in \text{cycle}} \text{timestamp}(e)$$
     Measures the total elapsed duration of the loop. Coordinated layering and round-tripping execute rapidly (minutes or hours) to minimize exposure.

### 2.5 Technique: Streaming Degree & Fan-In / Fan-Out Concentration Velocity
* **File:** `src/topology/engine.py`
* **How It Works:** 
  Detects money-mule aggregation funnels and smurfing operations:
  * `fan_in`: Distinct accounts that transferred funds to the destination $v$ within window $W$:
    $$\text{fan\_in}(v, W) = |\text{in\_}[v]|$$
  * `dest_in_degree`: Total transaction volume (with multiplicity) directed into $v$:
    $$\text{dest\_in\_degree}(v, W) = \text{indeg}[v]$$
  * `fan_out`: Distinct recipient accounts targeted by source $u$:
    $$\text{fan\_out}(u, W) = |\text{out}[u]|$$
  * `src_out_degree`: Total transaction volume directed out of $u$:
    $$\text{src\_out\_degree}(u, W) = \text{outdeg}[u]$$

### 2.6 Algorithm: Count-Based Rolling Memory Lapping Detector
* **File:** `src/topology/lap_memory.py` (`LapMemory`)
* **How It Works:** 
  Lapping fraud involves concealing a stolen remittance from Customer A by applying a subsequent payment from Customer B. This creates a distinctive signature: **recurring near-equal amounts arriving from diverse, unlinked counterparties**.
  * `LapMemory` maintains a per-account rolling deque of the last $k=25$ transactions:
    $$\text{mem}[u] = \text{deque}(\langle \text{amount}_i, \text{counterparty}_i \rangle, \text{maxlen}=k)$$
  * For each new transaction amount $a$, it queries history within a relative tolerance $\tau = 0.01$ (1%):
    $$\text{Match Condition: } |a_i - a| \le \tau \cdot a$$
  * Computes:
    * `lap_in_recur`: Count of historical incoming amounts matching $a$.
    * `lap_in_payers`: Count of **distinct counterparties** among those matching amounts.
  * **Discriminative Insight:** A high `lap_in_recur` with `lap_in_payers == 1` represents benign recurring subscription billing. A high `lap_in_recur` with `lap_in_payers > 5` indicates high-risk lapping or mule aggregation.

### 2.7 Technique: Automated Invariance-Based Leakage Regression Testing
* **File:** `src/topology/leakage_test.py`
* **How It Works:** 
  A formal verification harness integrated into the test suite that mathematically validates the zero-lookahead contract through two tests:
  1. **Truncation Invariance:** Features computed for the first $k$ transactions of a stream must be bitwise identical to features computed when the stream is abruptly truncated at $k$:
     $$\mathbf{X}_{\text{topo}}[1..k] \mid_{\text{Stream}_{1..N}} \equiv \mathbf{X}_{\text{topo}}[1..k] \mid_{\text{Stream}_{1..k}}$$
  2. **Future-Corruption Invariance:** Corrupting the amounts, destinations, or labels of transactions at indices $k+1 \dots N$ must produce exactly zero change in the features computed for transaction $k$. Any variance triggers an immediate build failure.

---

## Stage 3: Representation Learning (Continuous-Time TGN)

The TGN module (`src/modeling/tgn.py`) provides the learned representation arm of the framework, mapping continuous-time interaction dynamics into inductive node embeddings without human feature crafting.

```
Transaction at time t: u (src) ──► v (dst) with gap dt
              │
              ▼
   ┌────────────────────────────────────────────────────────┐
   │ 3.1 Time2Vec Periodic Encoding: z = cos(w·log(1+dt)+b) │
   └────────────────────────────────────────────────────────┘
              │
              ▼
   ┌────────────────────────────────────────────────────────┐
   │ 3.2 Read Memory Prior to Event: s_mem(t-), d_mem(t-)   │
   └────────────────────────────────────────────────────────┘
              │
              ▼
   ┌────────────────────────────────────────────────────────┐
   │ 3.3 Link Expectedness Score: P(u ──► v)                │
   └────────────────────────────────────────────────────────┘
              │
              ▼
   ┌────────────────────────────────────────────────────────┐
   │ 3.4 Asymmetric GRU Memory Update (Amount-Blind):       │
   │ s_mem(t) = GRU_src(s_mem, [d_mem, time_enc])          │
   │ d_mem(t) = GRU_dst(d_mem, [s_mem, time_enc])          │
   └────────────────────────────────────────────────────────┘
```

### 3.1 Model Architecture: Temporal Graph Network (`_TGN`)
* **File:** `src/modeling/tgn.py`
* **How It Works:** 
  Based on Rossi et al. (2020), this model maintains a stateful 32-dimensional continuous vector memory $\mathbf{s}_u(t) \in \mathbb{R}^{32}$ for every account $u \in \mathcal{V}$.
  * As transactions stream through the network, account memories are continuously updated via Gated Recurrent Units (GRU).
  * Nodes not seen before start with a zero-initialized memory vector $\mathbf{s}_{\text{init}} = \mathbf{0}$.

### 3.2 Technique: Time2Vec Periodic Temporal Gap Encoding
* **File:** `src/modeling/tgn.py` (`time_enc`)
* **How It Works:** 
  To capture both short-term velocity bursts and long-term circadian/weekly rhythms, the time elapsed since an account's previous transaction $\Delta t = t - t_{\text{last}}$ is projected into an 8-dimensional harmonic space using learnable frequencies and phase shifts:
  $$\mathbf{\Phi}(\Delta t) = \cos\left(\mathbf{w} \cdot \log(1 + \Delta t) + \mathbf{b}\right), \quad \mathbf{w}, \mathbf{b} \in \mathbb{R}^8$$
  Taking $\log(1 + \Delta t)$ compresses high-variance inter-arrival times (seconds to weeks) into a stable representation.

### 3.3 Technique: Dual Asymmetric GRU Memory Update Cells
* **File:** `src/modeling/tgn.py` (`_fold_batch`)
* **How It Works:** 
  Financial networks exhibit asymmetric behavioral dynamics: the act of sending money reflects spending or transfer behavior, whereas receiving money reflects collection or deposit behavior. 
  The TGN maintains two distinct GRU cells:
  * **Source Update:**
    $$\mathbf{m}_{\text{src}} = [\mathbf{s}_v(t^-) \,\|\, \mathbf{\Phi}(\Delta t_{\text{src}})]$$
    $$\mathbf{s}_u(t) = \text{GRU}_{\text{src}}(\mathbf{s}_u(t^-), \mathbf{m}_{\text{src}})$$
  * **Destination Update:**
    $$\mathbf{m}_{\text{dst}} = [\mathbf{s}_u(t^-) \,\|\, \mathbf{\Phi}(\Delta t_{\text{dst}})]$$
    $$\mathbf{s}_v(t) = \text{GRU}_{\text{dst}}(\mathbf{s}_v(t^-), \mathbf{m}_{\text{dst}})$$

### 3.4 Technique: Self-Supervised Link Prediction Head
* **File:** `src/modeling/tgn.py` (`link_logit`)
* **How It Works:** 
  The TGN is trained completely **label-free** (without observing fraud labels). It learns general transaction network topologies through self-supervised contrastive link prediction on the chronological training split:
  $$\text{Logit}(u, v) = \text{MLP}\left([\mathbf{s}_u(t^-) \,\|\, \mathbf{s}_v(t^-) \,\|\, \mathbf{\Phi}(\Delta t)]\right)$$
  * **Objective:** Binary Cross-Entropy with Logits loss:
    $$\mathcal{L}_{\text{link}} = -\log \sigma(\text{Logit}(u, v_{\text{pos}})) - \log(1 - \sigma(\text{Logit}(u, v_{\text{neg}})))$$
    where $v_{\text{neg}}$ is a randomly sampled negative destination account.
  * **Expectedness Metric:** The output $\sigma(\text{Logit}(u, v))$ is emitted as `tgn_edge_expectedness`—an anomaly signal representing how statistically normal this edge is based on historical network structure.

### 3.5 Technique: Amount-Blind & Structure-Pure Message Passing
* **File:** `src/modeling/tgn.py`
* **How It Works:** 
  Messages $\mathbf{m}$ passed into the GRU cells contain strictly the counterparty memory and the temporal gap encoding—**zero transaction amount information**. This ensures that the resulting 64 embedding dimensions ($32 \text{ source} + 32 \text{ destination}$) capture pure structural and temporal graph dynamics, isolating the topology signal from amount correlations.

### 3.6 Technique: Frozen-Weight Streaming Memory Replay
* **File:** `src/modeling/tgn.py` (`TGNEmbedder.transform`)
* **How It Works:** 
  After training the TGN weights $\boldsymbol{\theta}$ on the chronological training split, $\boldsymbol{\theta}$ is permanently frozen. The entire chronological stream (train $\to$ validation $\to$ test) is then replayed sequentially. Node memories evolve continuously based on past interactions, ensuring that test embeddings depend strictly on historical interactions up to time $t < t_{\text{event}}$.

---

## Stage 4: Feature Assembly & Tabular Baseline Engineering

The Feature Assembly module (`src/features/build.py`) builds the unified model table, combining the handcrafted topology features, TGN embeddings, and a leakage-free tabular baseline.

```
Canonical Edges ────────► [Expanding Past-Only Statistics] ──┐
                                                             │
Topology Engine ────────► [13 Causal Topology Columns]     ──┼──► [Fused Feature Table]
                                                             │    (features_model.parquet)
TGN Module      ────────► [65 Dynamic Embedding Columns]   ──┘
```

### 4.1 Technique: Expanding (Past-Only) Per-Account Running Statistics
* **File:** `src/features/build.py` (`_expanding_account_stats`)
* **How It Works:** 
  Computes historical behavioral profiles per account without lookahead leakage. Using grouped `cumsum` and `cumcount` shifted by $+1$ (excluding the current row):
  * `src_count_prior`: Cumulative transactions sent by this account prior to now:
    $$N_{\text{prior}}(u, t) = \sum_{e \in \text{Past}(u, t)} 1$$
  * `src_amt_mean_prior`: Running historical mean amount:
    $$\mu_{\text{prior}}(u, t) = \frac{1}{N_{\text{prior}}(u, t)} \sum_{e \in \text{Past}(u, t)} \text{amount}(e)$$
  * `amount_zscore_src`: Standardized score of current amount against the account's own past:
    $$z(e) = \frac{\text{amount}(e) - \mu_{\text{prior}}(u, t)}{\sigma_{\text{prior}}(u, t)}$$
* **No Global Normalization:** The system deliberately avoids whole-dataset $z$-score standardization, which leaks future distribution parameters into past transactions.

### 4.2 Technique: Past-Facing Temporal Velocity vs. Lookahead Leaks
* **File:** `src/features/build.py`
* **How It Works:** 
  The predecessor implementation achieved artificial performance through `time_to_next_txn` (the duration until an account's *next* transaction). In production, this value is unknowable.
  We replaced this with the causal backward counterpart:
  $$\text{time\_since\_prev\_src} = t_{\text{current}} - t_{\text{previous}}(u)$$
  Computed via grouped `shift(1)`. For an account's first transaction, this evaluates to `NaN`, which gradient-boosted trees handle natively.

### 4.3 Technique: Categorical Encoding Discipline
* **File:** `src/features/build.py`
* **How It Works:** 
  Edge-level categorical variables (e.g., transaction type, merchant category) are one-hot encoded only if their cardinality falls within the range $[2, 30]$. High-cardinality identifiers (vendor IDs, line item numbers) and zero-variance columns are dropped to prevent overfitting and high-dimensional noise.

### 4.4 Feature Family Partitioning
The fused dataset (`features_model.parquet`) partitions features into three explicit families tracked in `features_manifest.json`:
1. **Ordinary Tabular Features (Baseline):** `amount`, `log_amount`, `src_count_prior`, `src_amt_mean_prior`, `amount_zscore_src`, `time_since_prev_src`, `dest_count_prior`, one-hot categories.
2. **Handcrafted Topology Features (13 columns):**
   * Structure (8): `in_cycle`, `cycle_length`, `in_cycle_ge3`, `cycle_time_span`, `fan_in`, `fan_out`, `dest_in_degree`, `src_out_degree`.
   * Amount-Derived (5): `cycle_amount_ratio`, `lap_in_recur`, `lap_in_payers`, `lap_out_recur`, `lap_out_payees`.
3. **Learned TGN Embeddings (65 columns):** `tgn_s0`..`tgn_s31`, `tgn_d0`..`tgn_d31`, `tgn_edge_expectedness`.

---

## Stage 5: Supervised Classification & Optimization

The modeling engine (`src/modeling/`) trains, tunes, and evaluates downstream classifiers under strict rare-event conditions.

### 5.1 Model: Extreme Gradient Boosted Decision Trees (XGBoost)
* **File:** `src/modeling/harness.py`, `src/modeling/trainer.py`
* **How It Works:** 
  Gradient boosted ensembles build additive decision trees minimizing a regularized objective:
  $$\mathcal{L}^{(t)} = \sum_{i=1}^n l\left(y_i, \hat{y}_i^{(t-1)} + f_t(\mathbf{x}_i)\right) + \Omega(f_t)$$
  Selected as the champion classifier over deep tabular transformers because tree models consistently outperform neural architectures on tabular data (Grinsztajn et al., NeurIPS 2022) while supporting exact polynomial-time SHAP attributions.

### 5.2 Objective Function: Alpha-Free Custom Binary Focal Loss
* **File:** `src/modeling/objectives.py` (`focal_binary_objective`)
* **How It Works:** 
  Standard binary cross-entropy treats all misclassifications uniformly. In financial fraud detection where positive labels account for only 0.01% to 0.1% of transactions, gradients are overwhelmed by easy negative examples.
  We implemented custom focal loss:
  $$\text{FL}(p_t) = -(1 - p_t)^\gamma \log(p_t), \quad p_t = \begin{cases} p & \text{if } y = 1 \\ 1 - p & \text{if } y = 0 \end{cases}$$
  With focusing parameter $\gamma = 2.0$:
  * If an example is well-classified ($p_t \approx 0.99$), the modulating factor $(1 - p_t)^2 \approx 0.0001$, scaling down its gradient contribution.
  * Hard, ambiguous fraud instances receive significantly higher gradient weight.
  * **Custom Gradient & Hessian:** XGBoost requires first and second derivatives:
    $$g_i = \frac{\partial \text{FL}}{\partial \hat{y}_i}, \quad h_i = \frac{\partial^2 \text{FL}}{\partial \hat{y}_i^2}$$
    These were derived and implemented in NumPy, collapsing run-to-run seed variance from $0.070$ to $0.002$ on BankSim.

### 5.3 Technique: The Single-Imbalance Rule
* **Principle:** Standard machine learning literature frequently combines synthetic oversampling (SMOTE) with cost-sensitive loss weighting (`scale_pos_weight`). In financial graph topology, this causes severe gradient instability. Synthetic interpolation of nodes creates non-physical graph structures (e.g., fractional cycle lengths). We enforced a strict architectural invariant: **exactly one imbalance mechanism is permitted (either focal loss or class weighting, never both; zero SMOTE on graph features)**.

### 5.4 Optimization: Bayesian Hyperparameter Optimization (Optuna TPE)
* **File:** `src/modeling/hpo.py`
* **How It Works:** 
  Uses the Tree-structured Parzen Estimator (TPE) algorithm across 20 trials optimizing for validation PR-AUC over:
  * `max_depth` $\in [3, 9]$
  * `learning_rate` $\in [0.01, 0.2]$ (log scale)
  * `subsample` $\in [0.6, 1.0]$
  * `colsample_bytree` $\in [0.5, 1.0]$
  * `min_child_weight` $\in [1, 20]$

### 5.5 Technique: Chronological Validation Threshold Tuning
* **File:** `src/modeling/harness.py` (`tune_threshold`)
* **How It Works:** 
  Default classification thresholds ($0.5$) are ineffective on rare-event distributions. The optimal decision threshold $\tau^*$ is found via sweep over the chronological validation set to maximize the Precision-Recall $F_{\beta}$-score or PR-AUC. Once selected, $\tau^*$ is permanently locked and evaluated on the held-out test split.

---

## Stage 6: Forensic Explainability & Audit Dispatch

The explainability engine (`src/modeling/explain.py`, `src/graph/queries.py`) bridges machine learning predictions and regulatory compliance under Sarbanes-Oxley (SOX Section 404).

### 6.1 Model / Algorithm: Exact TreeSHAP Local Attributions
* **File:** `src/modeling/explain.py`
* **How It Works:** 
  Lundberg et al. (Nature Machine Intelligence, 2020). Computes exact game-theoretic Shapley values across all decision paths in polynomial time $\mathcal{O}(T L D^2)$:
  $$\phi_i(x) = \sum_{S \subseteq F \setminus \{i\}} \frac{|S|!(|F| - |S| - 1)!}{|F|!} \left[f(S \cup \{i\}) - f(S)\right]$$
  Guarantees additivity: $\sum_{i=1}^M \phi_i(x) = f(x) - \mathbb{E}[f(x)]$. Every fraud alert outputs exact numerical score contributions for every feature.

### 6.2 Technique: Tri-Family Feature Attribution Decomposition
* **File:** `src/modeling/explain.py`
* **How It Works:** 
  Individual feature Shapley values are aggregated into three high-level buckets to answer the statutory auditor's question: *"Why was this transaction flagged?"*
  $$\Phi_{\text{total}} = \Phi_{\text{ordinary}} + \Phi_{\text{handcrafted\_topology}} + \Phi_{\text{tgn\_embeddings}}$$
  If $\Phi_{\text{topology}} > \Phi_{\text{ordinary}}$, the alert indicates an account whose individual attributes appear normal, but whose network graph connectivity matches a coordinated laundering topology.

### 6.3 Technique: Deterministic Neo4j Subgraph Path Traversal
* **File:** `src/graph/queries.py`, `src/topology/paths.py`
* **How It Works:** 
  Quantitative SHAP scores cannot be submitted directly as legal evidence. For every flagged transaction $e = (u, v)$, the engine executes Cypher queries against a synchronized Neo4j graph store to reconstruct the physical path:
  ```cypher
  MATCH path = (v:Account)-[:TRANSFERRED*1..4]->(u:Account)
  WHERE all(r in relationships(path) WHERE r.timestamp <= $current_timestamp)
  RETURN path ORDER BY length(path) ASC LIMIT 1
  ```
  The resulting nodes, edges, timestamps, and amounts are packaged into the alert payload and displayed as an interactive SVG/D3 path diagram in the audit console.

---

## Stage 7: Privacy-Preserving Federated Consortium (FedProx)

The federated learning engine (`src/federated/`) enables multi-institution collaborative defense against cross-bank fraud networks without sharing raw customer data.

### 7.1 Technique: Non-IID Account-Clustering Dirichlet Partitioning
* **File:** `src/federated/partition.py`
* **How It Works:** 
  Real financial networks are severely non-IID (Independent and Identically Distributed): Bank A may specialize in retail credit, Bank B in commercial payroll, and Bank C in high-risk foreign exchange.
  We simulate this through Dirichlet distribution sampling $\text{Dir}(\alpha)$ combined with Louvain community partitioning on the graph, assigning distinct fraud typologies to different banking clients $K \in \{2, 3, 4, 5\}$.

### 7.2 Model & Protocol: FedProx Score-Level Consensus
* **File:** `src/federated/server.py`, `src/federated/client.py`
* **How It Works:** 
  Standard Federated Averaging (FedAvg) suffers from catastrophic weight divergence under non-IID data. FedProx (Li et al., MLSys 2020) introduces a proximal regularization term:
  $$\min_{\mathbf{w}} h_k(\mathbf{w}; \mathbf{w}^t) = F_k(\mathbf{w}) + \frac{\mu}{2} \|\mathbf{w} - \mathbf{w}^t\|^2$$
  * Clients train local models with proximal parameter $\mu = 0.01$, constraining local gradient steps to remain close to the global consortium consensus $\mathbf{w}^t$.
  * In the score-level consensus mode, local tree prediction ensembles exchange calibration parameters and validation reliability weights without transmitting raw transaction logs or feature vectors.

### 7.3 Technique: Reliability-Weighted Consensus Aggregation
* **File:** `src/federated/server.py`
* **How It Works:** 
  When aggregating updates from $K$ distributed banking clients, the central consortium server weights each bank's update by its sample volume $n_k$ and its observed validation PR-AUC reliability score $R_k$:
  $$\mathbf{w}^{t+1} = \sum_{k=1}^K \frac{n_k R_k}{\sum_j n_j R_j} \mathbf{w}_k^{t+1}$$
  Prevents a client experiencing temporary distribution shift from degrading the accuracy of the global model.

---

## Summary Mapping Table: Stages, Techniques, and Outputs

| Pipeline Stage | Module / File Path | Models & Algorithms | Core Technique / Equation | Primary Artifact Output |
| :--- | :--- | :--- | :--- | :--- |
| **Stage 1: ETL & Ingestion** | `src/etl/build.py` | Canonical Schema Mapper, Bipartite Graph Projector | $\mathcal{V} = \text{Unique}(\text{src} \cup \text{dst})$ (Unified Namespace); Deterministic stable time sorting | `edges_transactions.csv`<br>`nodes_accounts.csv`<br>`audit.json` |
| **Stage 2: Topology Engine** | `src/topology/engine.py`<br>`window_graph.py`<br>`lap_memory.py` | `WindowGraph`, Depth-Bounded DFS, `LapMemory` | As-Of temporal causality ($t < t_{\text{edge}}$); $\rho = \frac{\min \text{amt}}{\max \text{amt}}$; Invariance unit tests | `features_topology.csv` (13 columns) |
| **Stage 3: Dynamic Embeddings** | `src/modeling/tgn.py` | `_TGN`, Time2Vec, Dual GRU Cells | $\mathbf{\Phi}(\Delta t) = \cos(\mathbf{w}\log(1+\Delta t) + \mathbf{b})$; Self-supervised link prediction (amount-blind) | `features_tgn.parquet` (65 columns) |
| **Stage 4: Feature Assembly** | `src/features/build.py` | Expanding Window Aggregator | Shifted past-only stats ($z = \frac{x - \mu_{\text{past}}}{\sigma_{\text{past}}}$); `time_since_prev_src` | `features_model.parquet`<br>`features_manifest.json` |
| **Stage 5: Classification** | `src/modeling/trainer.py`<br>`objectives.py`<br>`hpo.py` | XGBoost Decision Trees, Optuna Bayesian HPO | $\text{FL}(p_t) = -(1-p_t)^2 \log(p_t)$; Single-Imbalance Rule; Validation threshold sweep | `model_champion.json`<br>`metrics.json` |
| **Stage 6: Explainability** | `src/modeling/explain.py`<br>`src/graph/queries.py` | TreeSHAP Explainer, Neo4j Cypher Path Traversal | Game-theoretic attributions: $\Phi_{\text{ord}} + \Phi_{\text{topo}} + \Phi_{\text{tgn}}$; Deterministic subgraphs | `alerts.json`<br>Interactive D3/SVG UI |
| **Stage 7: Federation** | `src/federated/server.py`<br>`client.py`<br>`partition.py` | FedProx Consortium Optimizer, Dirichlet Partitioner | $\min F_k(\mathbf{w}) + \frac{\mu}{2}\|\mathbf{w} - \mathbf{w}^t\|^2$; Reliability-weighted score consensus | `federated_table.md` |
