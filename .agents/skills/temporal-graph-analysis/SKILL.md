---
name: temporal-graph-analysis
description: >-
  Expert guide for temporal graph analysis, streaming sliding-window topology extraction,
  leakage-free graph traversal, cycle detection, lapping patterns, and temporal invariance tests.
  Use when designing, optimizing, or debugging temporal graph algorithms or network features.
---

# Temporal Graph Analysis & Streaming Topology Engineering

This skill provides procedures, algorithmic patterns, and rules for building, extracting, and verifying **temporal graph features** on streaming transaction networks without look-ahead data leakage.

---

## 1. Core Principles: Streaming & Leakage-Free Graph Analytics

In temporal financial graphs (e.g., money flow, transaction ledgers, fraud detection), the graph evolves continuously over time.

### Golden Rule: Read As-Of Past State, Then Insert
For every transaction $e = (u, v, t, \text{amount}, \text{id})$:
1. **Compute Features**: Query the graph state considering **only edges where $t_e \le t$** (and within trailing window $[t - W, t]$).
2. **Attribute to Closer**: Signal for structural completion (e.g., a cycle $A \to B \to C \to A$) is credited **only** to the closing transaction $e$, never backpropagated to earlier transactions.
3. **Insert Edge**: Add $e$ into the active graph memory *after* feature extraction.
4. **Evict Stale Edges**: Prune edges older than $t - W$ (sliding window FIFO).

```
   Incoming Txn (A -> B, t=10:05)
           │
           ▼
   [Query Past Graph [10:00, 10:05]] ──▶ Extract: in_cycle, fan_in, lap_recur...
           │
           ▼
   [Insert (A -> B) into Graph]
           │
           ▼
   [Evict edges with t < (10:05 - Window)]
```

---

## 2. Structural & Topological Feature Detectors

### 2.1 Cycle Detection (Loop Laundering / Round-Tripping)
* **Goal**: Detect if an edge $(u, v)$ closes a directed path $v \leadsto u$ in the past window.
* **Bounded BFS Algorithm**:
  - Search from $v$ looking for $u$ using edges within the time window $[t - W, t]$.
  - Constrain BFS with `max_cycle_len` (e.g., $\le 5$ hops) and `search_budget` (e.g., $\le 1000$ visited nodes) to prevent combinatorial explosion on dense nodes.
* **Cycle Sub-metrics**:
  - `in_cycle`: Binary flag ($1$ if path $v \leadsto u$ exists).
  - `cycle_length`: Number of edges in shortest path $+ 1$.
  - `in_cycle_ge3`: $1$ if cycle length $\ge 3$ (excludes self-loops and reciprocal 2-hop pairs).
  - `cycle_amount_ratio`: $\min(\text{amounts}) / \max(\text{amounts})$ along the loop. Ratio $\approx 1.0$ indicates tight amount conservation (layering / wash).
  - `cycle_time_span`: $t_{\text{close}} - \min(t_{\text{loop edges}})$. Small span indicates rapid automated looping.

### 2.2 Fan-In / Fan-Out (Mule Collection & Dispersion Hubs)
* `fan_in`: Count of **distinct** source accounts sending to $v$ in window $[t - W, t]$.
* `fan_out`: Count of **distinct** destination accounts receiving from $u$ in window $[t - W, t]$.
* `dest_in_degree` / `src_out_degree`: Total edge counts (with multiplicity).

### 2.3 Lapping Memory (Robbing Peter to Pay Paul)
* Lapping schemes involve sequential near-equal amounts received or sent over extended periods.
* **Count-Based Deque Pattern (`LapMemory`)**:
  - Maintain a bounded deque of size $K$ (e.g., last 50 transactions) per account.
  - Query: Count prior transactions where $|\text{amount}_{\text{prev}} - \text{amount}| / \text{amount} \le \epsilon$ (e.g., 1%).
  - Extract: `lap_in_recur`, `lap_in_payers`, `lap_out_recur`, `lap_out_payees`.
  - Must be count-based (not time-windowed) to capture slow-rolling embezzlement across billing cycles.

---

## 3. Implementation Patterns

### Memory-Efficient Window Multigraph (Python/NumPy)
```python
from collections import defaultdict, deque
import numpy as np

class WindowGraph:
    def __init__(self, window_seconds: float, max_cycle_len: int = 5, search_budget: int = 1000):
        self.window = window_seconds
        self.max_cycle_len = max_cycle_len
        self.search_budget = search_budget
        
        # Adjacency: u -> list of (v, ts, amount, edge_id)
        self.adj = defaultdict(list)
        # FIFO queue for window eviction: (ts, u, v, amount, edge_id)
        self.edge_queue = deque()
        # In-degree / Out-degree tracker
        self.in_senders = defaultdict(lambda: defaultdict(int))
        self.out_receivers = defaultdict(lambda: defaultdict(int))

    def evict(self, current_ts: float):
        min_ts = current_ts - self.window
        while self.edge_queue and self.edge_queue[0][0] < min_ts:
            ts, u, v, amt, eid = self.edge_queue.popleft()
            # Remove from adj
            self.adj[u] = [e for e in self.adj[u] if e[3] != eid]
            if not self.adj[u]:
                del self.adj[u]
            
            # Decrement sender/receiver counters
            self.in_senders[v][u] -= 1
            if self.in_senders[v][u] <= 0:
                del self.in_senders[v][u]
            self.out_receivers[u][v] -= 1
            if self.out_receivers[u][v] <= 0:
                del self.out_receivers[u][v]

    def find_cycle(self, u: str, v: str, current_ts: float):
        """Find path v -> ... -> u in past graph."""
        if u == v:
            return True, 1, [0.0], 0.0
        
        queue = deque([(v, 1, [], current_ts)])
        visited = {v: 1}
        budget = self.search_budget
        
        while queue and budget > 0:
            curr, depth, path_amts, earliest_ts = queue.popleft()
            budget -= 1
            
            if depth >= self.max_cycle_len:
                continue
                
            for nxt, ts, amt, _ in self.adj.get(curr, []):
                new_earliest = min(earliest_ts, ts)
                if nxt == u:
                    all_amts = path_amts + [amt]
                    return True, depth + 1, all_amts, current_ts - new_earliest
                if nxt not in visited or visited[nxt] > depth + 1:
                    visited[nxt] = depth + 1
                    queue.append((nxt, depth + 1, path_amts + [amt], new_earliest))
                    
        return False, 0, [], float('nan')

    def insert(self, u: str, v: str, ts: float, amount: float, edge_id: int):
        self.adj[u].append((v, ts, amount, edge_id))
        self.edge_queue.append((ts, u, v, amount, edge_id))
        self.in_senders[v][u] += 1
        self.out_receivers[u][v] += 1
```

---

## 4. Leakage Verification Protocol

Always validate temporal feature pipelines with automated leakage tests:

1. **Truncation Invariance**:
   $$\text{Features}(T_1 \dots T_K) = \text{Features}(T_1 \dots T_N)[:K] \quad (\forall K \le N)$$
   Processing only the first $K$ transactions must yield identical feature rows for those $K$ transactions.

2. **Future-Corruption Invariance**:
   Permuting or corrupting transactions occurring at $t > T_K$ must not alter features calculated for $t \le T_K$.

```python
def test_leakage_invariance(engine_fn, df_raw):
    df_sorted = df_raw.sort_values(["timestamp", "transaction_id"]).reset_index(drop=True)
    k = len(df_sorted) // 2
    
    # 1. Extract on full dataset
    feat_full = engine_fn(df_sorted)
    
    # 2. Extract on truncated dataset
    feat_trunc = engine_fn(df_sorted.iloc[:k].copy())
    
    # Assert truncation equality
    assert np.allclose(
        feat_full.iloc[:k].values,
        feat_trunc.values,
        equal_nan=True
    ), "Data leakage detected: past features changed when future was truncated!"
```
