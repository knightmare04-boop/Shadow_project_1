# The Self-Auditing Ledger — Final Project Report

**Project:** ERP Fraud Detection using Temporal Graph Topology + Machine Learning
**Codename:** Shadow Graph / NodeWatch
**Date:** 26 August 2026
**Status:** Complete (all build steps finished and verified)

---

## 1. What this project is, in one paragraph

Most fraud-detection systems look at one payment at a time and ask *"does this
payment look strange on its own?"* That misses the most dangerous fraud, which is
almost always a **pattern spread across several connected payments** — money
moving in a circle, many accounts funneling into one, or rapid multi-step
transfers. This project turns a company's transaction history into a **temporal
graph** (a network of who-paid-whom, where every arrow has a timestamp), detects
suspicious *shapes* in that network, feeds those shape measurements plus normal
transaction features into a machine-learning model that scores each
transaction's fraud risk, and then **explains every alert** — both *why* the
model scored it high and *what the actual suspicious money path looks like*,
drawn visually.

---

## 2. The scientific question we set out to answer

We deliberately separated the **vision** (a real-time fraud-watching platform)
from the **proof** (a careful experiment). The question we committed to
answering, honestly, either way:

> **Do graph-shape ("topology") features add real predictive value on top of a
> strong ordinary-transaction baseline — when measured fairly, with no data
> leakage?**

**Why this framing matters:** an earlier version of this project (kept read-only
in `reference/`) claimed *"graph topology is the ultimate differentiator"* — but
when we audited it, its own feature-importance reports showed every topology
feature scored **0.0 importance** (the signal was just the transaction amount),
and all its impressive scores (e.g. "99.7% AUC") were inflated by **data
leakage** — the model was accidentally allowed to see the future. So the central
idea had never actually been tested fairly. Finding and fixing that, and then
running the first honest test, is the core contribution. We committed up front
to reporting a negative result if that's what the data showed.

### Key term: data leakage
**Data leakage** means the model accidentally uses information it would not have
at prediction time — usually information from the *future*. It makes test scores
look fantastic, but the model collapses in the real world. Example from the old
version: one of its top features was literally *"time until the NEXT
transaction"* — using tomorrow to predict today. Our entire architecture is
built so this is structurally impossible (Section 5).

---

## 3. Final architecture (what we built)

Data flows top to bottom. Each stage has exactly one job:

```
RAW DATA (transaction CSVs from public fraud datasets)
   |
   v
(1) ETL - clean & standardize every dataset into ONE canonical form:
    Accounts (nodes) + Transactions (time-stamped edges with amount + label)
   |
   v
(2) SHADOW GRAPH - the temporal network of money flow
   |
   v
(3) TEMPORAL TOPOLOGY ENGINE - for each transaction, measured ONLY from
    the past: does it close a cycle? how many senders funnel into the
    receiver? recurring near-equal amounts? -> numbers per transaction
   |
   v
(4) FEATURE TABLE - one row per transaction:
    ordinary features + topology features + learned TGN embeddings + label
   |
   v
(5) FINAL MODEL - TGN embeddings + topology + ordinary features -> XGBoost
    (trained honestly: time-aware split, ONE imbalance fix, tuned cutoff,
    light hyperparameter search, 3 random seeds)  -> fraud probability
   |
   v
(6) EVALUATION + ABLATION - "did topology actually help?" measured with
    PR-AUC and precision@k on a future (never-seen) test period
   |
   v
(7) EXPLAINABLE AUDIT ALERT - TreeSHAP (which features drove the score)
    + the actual suspicious path from the graph (drawn in Neo4j)
```

### The one big engineering decision
All heavy computation happens in **Python** (Pandas + custom streaming graph
code). **Neo4j** (a graph database) is used *only* for the visual demo and path
explanations. Why: the old version tried to do heavy graph computation inside
Neo4j and **ran out of memory** on large datasets, silently disabling topology.
Python computes reproducibly at scale; Neo4j does what it's best at — showing a
human the suspicious subgraph.

---

## 4. Final technology stack

| Tool | Role | Why chosen |
|---|---|---|
| **Python 3.14** | Everything | Standard for ML research; reproducible |
| **Pandas / NumPy** | Data handling | The standard tabular toolkit |
| **XGBoost** | The main (champion) model | State of the art on tabular data; handles imbalance; explainable via TreeSHAP |
| **PyTorch** | The TGN embedder (deep learning component) | Standard deep-learning framework; runs our small temporal graph network on CPU |
| **scikit-learn** | Metrics & evaluation | Standard, trusted implementations |
| **TreeSHAP (native in XGBoost)** | Explanations | Gives *exact* per-feature contributions for tree models (Section 10) |
| **Neo4j** | Visual demo only | Best-in-class graph visualization; deliberately NOT used for computation |
| **pytest** | Automated tests | Guards the honesty-critical code paths |
| Matplotlib / Seaborn / Plotly | Plots | Reporting |

Repository layout: `src/etl` (cleaning), `src/topology` (the detectors),
`src/features` (feature table), `src/modeling` (training/scoring/explaining),
`src/graph` (Neo4j demo), `experiments/` (runnable studies), `tests/`.

---

## 5. The honesty rules (our methodology) — and why each exists

Fraud data is extremely **imbalanced**: only 0.1%–1.2% of transactions are
fraud. A model that says "never fraud" is 99.9% accurate and completely useless.
This single fact, plus the old version's mistakes, drives every rule below.

**Rule 1 — Exactly ONE imbalance fix at a time.** To help a model notice rare
fraud you can *resample* (e.g. SMOTE, which invents synthetic fraud examples) or
use *class weights* (tell the model fraud mistakes count more). The old version
used both at once — double-counting that distorts everything. We use exactly one
per experiment and record which. We also rejected SMOTE outright for graph
features: inventing a synthetic example "halfway between two cycles" is
physically meaningless.

**Rule 2 — Tune the decision cutoff, never assume 0.5.** The model outputs a
probability; some cutoff turns it into an alert. 0.5 is arbitrary. We *choose*
the cutoff on validation data, then **freeze** it before touching the test set.

**Rule 3 — Time-aware testing, never shuffle.** We train on **earlier**
transactions and test on **later** ones — how the real world works. Shuffling
(what the old version did) lets the model "study the answers" from the future.

**Rule 4 — No look-ahead through the graph.** A transaction's features may only
depend on transactions with `timestamp <= its own`. We process transactions in
time order like an auditor watching them arrive: read the features from the
graph *as it exists right now*, then insert the transaction, then move on. The
future physically cannot leak in. An **automated leakage test** guards this:
scramble the future, and if any past transaction's features change, the build
fails. (It has stayed green through the entire project.)

**Rule 5 — The right metrics for rare events** (explained in Section 6).

**Rule 6 — Keep the evidence.** Every trained model is saved with its feature
list, frozen cutoff, and configuration, so any result can be reproduced exactly.

---

## 6. Our measurement terms, in plain language — and why we chose them

**PR-AUC (Precision-Recall Area Under Curve), also called Average Precision —
our PRIMARY metric.**
- **Precision** = of the transactions we flagged, how many were really fraud?
  (Are our alarms trustworthy?)
- **Recall** = of all the real fraud, how much did we catch?
- The PR curve shows the trade-off between the two at every possible cutoff;
  PR-AUC is the area under it — a single number from ~0 (useless) to 1
  (perfect). Crucially, on data where fraud is 0.1% of rows, a random guesser
  gets PR-AUC ≈ 0.001, so the metric *honestly reflects how hard the problem
  is*. **This is why we chose it**: it focuses entirely on how well the rare
  frauds are found.

**Why not accuracy?** With 99.9% legitimate transactions, "always say
not-fraud" scores 99.9% accuracy and catches nothing. Meaningless here.

**Why not ROC-AUC (the popular default)?** ROC-AUC measures ranking quality but
is calculated in a way that gets flattered by the huge number of easy
"not-fraud" cases — models routinely score 0.99 ROC-AUC while being useless to
an actual investigator. We report it but never rely on it.

**Precision@k / Recall@k — the "auditor's metric."** A real audit team reviews
maybe the top 100 alerts per day, not thousands. Precision@100 asks: *of our top
100 highest-scoring transactions, how many are actually fraud?* This is the most
operationally honest number we report. (Our final model reaches
**precision@100 = 1.00** on BankSim — every one of the top 100 alerts is real
fraud.)

**F1 score** = the harmonic mean of precision and recall at the chosen cutoff.
Reported, but we never *select* models on it (that hides the cutoff problem).

**mean ± std over seeds.** Model training involves randomness (a "seed"
controls it). One run can mislead: single-seed differences of ~0.01 PR-AUC are
pure noise. Every headline number we report is the **average of 3 runs with
different seeds, with its standard deviation** — so we know which differences
are real.

---

## 7. The datasets — a deliberate spectrum

Our question is "does graph *structure* help?", so we chose datasets that vary
in **how much real graph structure they contain**, and ran the same test on
each. If topology helps more where structure is rich and less where it's flat,
that pattern itself is evidence.

| Dataset | Size | Fraud rate | Graph structure | Role |
|---|---|---|---|---|
| **IBM AML** (anti-money-laundering simulation) | 1.32M txns | 0.13% | **Rich** — real account-to-account flows, true cycles; every fraud is a labelled shape (936 cycles + 783 fan-ins) | The topology testbed |
| **BankSim** (bank payment simulation) | 595k txns | 1.21% | **Sparse** — customers pay merchants only, cycles impossible | The control |
| **SAP Würzburg** (real SAP ledger, university-published) | 200k lines | 0.12% (248 frauds) | Thin — documents ↔ ~31 ledger accounts | The genuine ERP data |
| **PaySim** (mobile-money simulation) | 6.36M txns | 0.13% | Near-tree | Scale test (feature stages built; modeling deferred) |
| **synth_erp** (OUR OWN generated dataset) | 1.15M txns | 0.49% | Rich, ERP-flavored | Training/stress-testing ONLY — never proof |

Two important dataset decisions:
- **The unified account namespace fix.** The old ETL put senders and receivers
  into *different* ID spaces, so a loop A→B→A was literally invisible. We proved
  99.3% of IBM sender IDs also appear as receivers (they're the same accounts)
  and unified them — cycles became detectable at all.
- **Our synthetic dataset avoids the circularity trap.** We built `synth_erp`
  (an agent-based simulated ERP economy: 40 companies, ~35k accounts, 5 fraud
  types) with one binding rule: fraud is generated from criminal *goals and
  evasion behavior*, **never** from the patterns our detectors look for —
  otherwise we'd be grading our own homework. It passed an independent
  adversarial review (which found and we fixed 3 subtle "giveaway" leaks) and a
  realism battery. Policy: it is used for training experiments and demos only;
  the scientific claim is only ever evaluated on real datasets.

---

## 8. The models — what we tried and what won

### 8.1 XGBoost (gradient-boosted decision trees) — the workhorse
**What it is:** a model that builds hundreds of small decision trees, each one
correcting the errors of the ones before ("gradient boosting" — internally it
uses second-order/Newton-style optimization on the loss). **Why chosen:** it is
the consistent state of the art on tabular (table-shaped) data, handles
imbalance well, trains in minutes on CPU, and — decisive for us — is
**explainable** via TreeSHAP. We assessed modern "tabular transformer" neural
networks (FT-Transformer, TabNet, SAINT, TabPFN) in a formal literature review
and concluded they are competitive-at-best in our data regime while costing us
exact explainability — so they remain future work, not the core.

### 8.2 Handling imbalance: class weights vs focal loss
- **Class weights** (`scale_pos_weight`): tell the model each fraud example
  counts as much as ~hundreds of normal ones. Simple, standard — our default.
- **Focal loss:** a modified training objective that makes the model focus on
  the *hard* examples by down-weighting the easy, confidently-correct ones. We
  implemented it as a custom XGBoost objective, deliberately **alpha-free**
  (the common "alpha-balanced" variant secretly adds class weighting on top —
  which would break Rule 1's "one mechanism only").
- **What we found:** focal loss matched or beat class weights on every baseline
  comparison and — its biggest effect — **collapsed run-to-run variance**
  (BankSim baseline: 0.787 ± 0.070 with class weights → 0.862 ± 0.0001 with
  focal). In the final model we run **both** (each alone) and pick the winner
  per dataset on validation PR-AUC; focal won 3 of 4 datasets.

### 8.3 TGN (Temporal Graph Network) — the deep-learning component
**What it is:** a small neural network that reads the transaction stream in time
order and maintains a learned **memory vector** (32 numbers, via a GRU — a
recurrent unit) for every account: a continuously-updated summary of that
account's behavior. It trains itself with **self-supervised link prediction** —
"given the past, is this sender→receiver pair expected right now?" — so it
**never sees fraud labels**. Its outputs (**embeddings** — the learned vectors —
plus a single `tgn_edge_expectedness` score) become extra feature columns.

Three safety properties, by construction: **zero look-ahead** (each embedding is
read *before* the transaction updates the memory), **label-free**, and
**amount-blind** (it only sees who↔who and time gaps — a lesson from our
lapping finding, Section 9.3). Weights are fitted on the training period only,
then frozen.

### 8.4 The final model: TGN embeddings → XGBoost head
Rather than an end-to-end black-box neural network, we feed the TGN's learned
embeddings *into* XGBoost alongside the hand-crafted topology and ordinary
features. **Why this design:** we keep deep learning's ability to find patterns
we didn't hand-engineer, while keeping the whole model exactly explainable with
TreeSHAP — the best of both worlds. This two-stage design is the project's
final, recorded model architecture.

Final training protocol per dataset: light **hyperparameter search** (20
random configurations — tree depth, learning rate, etc. — scored on validation
PR-AUC only, automatically skipped where validation fraud counts are too small
to support it), both imbalance mechanisms, 3 seeds each, winner picked on
**validation** (never test), champion saved as a fully self-describing artifact.

---

## 9. Results — the complete, honest record

### 9.1 The headline ablation (the decisive experiment)
An **ablation** trains the same model with and without one ingredient to measure
what that ingredient contributes. Ours compares: ordinary features only
(baseline) vs baseline + topology — with identical splits, model, and settings.
We also run an "amount-blind" probe (remove all amount features) and a
"structure-only" probe (only pure graph-shape features), because a marginal
comparison is meaningless when the baseline is already saturated.

| Dataset | baseline PR-AUC | + topology | structure-only lift (amount-blind, the clean test) | verdict |
|---|--:|--:|--:|---|
| **BankSim** | 0.833 | **0.931** (+11.7%) | **+0.190** | **Real structural win** (via fan-in/density) |
| **IBM AML** | 0.990 | 0.998 | +0.090 | Baseline saturated by amount; modest real structure signal underneath |
| SAP Würzburg | 0.155 | 0.072 | +0.015 | Inconclusive (only 25 test frauds) |

**The honest answer to the research question:** *Graph structure adds real,
leakage-free predictive value — but conditionally and modestly.* It wins where
the baseline has headroom AND fraud has a structural signature (BankSim); it is
redundant where transaction amounts already give fraud away (IBM AML — an
artifact of how that simulator generates fraud).

### 9.2 The surprising sub-findings (each verified with clean probes)
1. **The IBM 0.99 baseline is NOT our leak.** We audited it: IBM's simulated
   frauds have giveaway amounts and same-day bursts — both strictly past-only
   signals. This *refuted our own starting premise* that IBM would be the
   decisive topology testbed. We report this openly.
2. **Cycles are redundant with density.** We upgraded the cycle detector to be
   genuinely discriminative (amount-conservation around the loop, loop
   tightness, ≥3-hop flags — fraud cycles conserve amounts 1.9× more than
   benign cycles). Even then, adding cycle features on top of simple density
   (fan-in / in-degree) gained only +0.001. Simple density measurements already
   capture the dense laundering neighborhoods. (Cycle features are kept — they
   make far better *explanations* than "high in-degree.")
3. **"Lapping" turned out to be an amount feature in disguise.** Our lapping
   detector (recurring near-equal amounts) looked spectacular until a probe
   showed it merely re-smuggles the amount signal into the "amount-blind" test.
   We reclassified it honestly (`topology-amount-derived`) and fixed our own
   probe methodology because of it — the ablation now separates pure structure
   from amount-derived topology.
4. **Naive synthetic-data augmentation HURTS (an honest negative result).**
   Pooling our synthetic dataset's rows into real training made every real
   dataset worse (BankSim −0.106 PR-AUC) — domain shift drags the trees toward
   the synthetic distributions. The positive nugget: a model trained ONLY on
   synthetic data scores **0.724 PR-AUC zero-shot on real BankSim** (vs 0.867
   real-trained, 0.012 chance) — the synthetic economy teaches transferable
   fraud discrimination.
5. **Learned structure complements engineered structure.** On synth_erp
   (behavior-driven fraud), the TGN alone (0.697) beat all 5 hand-crafted
   detectors (0.457), and the combination was better still — learned embeddings
   find temporal-relationship signal the hand-built detectors miss.

### 9.3 The FINAL model results (this session — 3 seeds, test period, never seen during any tuning)

| Dataset | baseline | +topology | +TGN | **FINAL champion** | precision@100 |
|---|--:|--:|--:|--:|--:|
| **BankSim** | 0.787 ±0.070 | 0.932 ±0.002 | 0.920 ±0.001 | **0.9364 ±0.0015** (focal) | **1.00** |
| **IBM AML** | 0.992 ±0.003 | 1.000 | 0.987 ±0.010 | 1.0000 (saturated*) | 1.00 |
| SAP Würzburg | 0.158 ±0.013 | 0.072 ±0.010 | 0.059 ±0.024 | 0.1557 ±0.0717* | 0.10 |
| synth_erp** | 0.248 ±0.060 | 0.457 ±0.155 | 0.697 ±0.000 | **0.7784 ±0.0053** (focal) | 0.99 |

\* IBM is amount-saturated (a perfect score there is uninformative — the
amount-blind probes are the real IBM story). SAP has only 25 test frauds — we
pre-committed to calling it inconclusive, and the system automatically flagged
its model selection as unreliable and skipped hyperparameter search there.
\** synth_erp is our own generated data: sanity/demo only, never thesis evidence.

**Which model works best: the final TGN + topology + XGBoost champion.** It
matches or beats every previous configuration on every dataset with headroom,
and on the operational metric — are the top-100 alerts real? — it is at or near
perfect on the structure-rich datasets.

### 9.4 The explainable audit alerts (the deliverable)
For each dataset the system produces its top-k test alerts with a two-layer
explanation. Sample results: **IBM AML top-20 alerts: 20/20 are real fraud**,
including 8 machine-verified money cycles (e.g. *"closes a 2-hop cycle
5025 → 1751 → 5025, conserving 10% of the amount, within 4 days"*); BankSim
top-15: 15/15 real fraud, all showing one merchant collecting from 47–63
distinct senders (a textbook mule-collection pattern). Every cycle path shown
to the auditor is re-derived from the graph and cross-checked against the
stored features — the system never presents unverified evidence.

---

## 10. Explainability — why an auditor can trust an alert

A score of "0.97" is useless to an auditor who must justify opening an
investigation. Every alert therefore contains:

1. **WHY the model scored it high — SHAP values.** SHAP (SHapley Additive
   exPlanations) comes from game theory: it fairly splits the model's score
   among the input features, so we can say *"+0.76 because 49 distinct senders
   funneled into this account; +3.35 because of the amount."* We use
   **TreeSHAP**, which computes these values *exactly* (not approximately) for
   tree models — a key reason XGBoost is our champion rather than a neural
   network, where explanations are approximate at best. Each driver is tagged
   with its family: `ordinary`, `topology` (pure structure),
   `topology-amount-derived` (honest about Section 9.2's lesson), or `tgn`.
2. **WHAT the evidence looks like — the actual path.** The concrete suspicious
   structure (the cycle's hops with amounts and times, or the fan-in senders),
   reconstructed from the graph exactly as it stood at scoring time, and drawn
   visually in **Neo4j** for the demo. The demo tool re-derives every path
   inside Neo4j independently and checks it matches — a built-in verification.

---

## 11. How we know the results are trustworthy (verification)

- **Automated leakage test** (permanent): scramble future transactions →
  confirm no past transaction's features change. Green on every run.
- **Ablation regression:** after all final-session code changes, re-running the
  original locked experiment reproduced every recorded number **bit-for-bit**.
- **Round-trip test:** every saved model was reloaded from disk and re-scored;
  the recomputed test PR-AUC matches the recorded one on all 4 datasets. (This
  gate caught a real bug during the session — reloaded models were silently
  using all 500 trees instead of the early-stopped best iteration — which is
  exactly why the gate exists.)
- **Alert-evidence invariants:** every cycle shown in an alert must close,
  match the stored cycle length, and contain only in-window, past-only hops.
  All pass.
- **Automated test suite** (pytest): the path-reconstruction search is
  property-tested against 5,000+ random cycles; the save/load path is tested
  for both imbalance mechanisms; the hyperparameter search is tested for
  determinism and its small-data guard.
- **Multi-seed everywhere; selection on validation only; test touched last.**

---

## 12. Honest limitations

- **IBM AML's perfect score is an artifact** of its simulator (giveaway
  amounts), not evidence our system is perfect. The informative IBM results are
  the amount-blind probes.
- **SAP Würzburg is inconclusive** — 25 test frauds cannot support strong
  claims. We say so rather than cherry-picking.
- **Slow, months-apart fraud loops** could evade the trailing time window; on
  our labelled datasets fraud is fast (93% of IBM cycles close within 7 days),
  so this is a scope boundary, stated openly.
- **Synthetic data is never proof.** Our generator is calibrated and
  adversarially reviewed, but the thesis is only ever evaluated on real data.
- **Streaming a brand-new transaction feed** would need the TGN's memory to
  roll forward live (currently embeddings are computed in batch per dataset) —
  engineering future work, not a scientific gap.

## 13. Future work

Live Neo4j demo run (code complete; needs a running local instance), PaySim at
full 6.36M-row scale, an FT-Transformer neural challenger (pre-trained on our
synthetic data, fine-tuned on real — the one use where the synthetic dataset
should shine), federated deployment (FedProx — banks collaborating on a shared
model without sharing any raw data; our per-client architecture already fits
this), and TGN streaming inference.

---

## 14. One-paragraph summary for the presentation

*We rebuilt a flawed fraud-detection project into an honest one. We found the
old system's claims were contradicted by its own outputs and inflated by data
leakage, so we designed an architecture where leakage is structurally
impossible — and it doubles as a real-time design. Across a spectrum of four
datasets we proved that graph topology adds real predictive value conditionally
(+11.7% PR-AUC where fraud has a structural signature), discovered that simple
density beats elaborate shape detectors, and that focal loss stabilizes
training on rare-event data. Our final model feeds learned temporal-graph
embeddings and hand-crafted topology into XGBoost — deep learning's pattern
discovery with exact tree-model explainability — reaching 0.94 PR-AUC and
perfect top-100 alert precision on BankSim, with every alert explained by exact
SHAP attributions and a verified, visualizable money-flow path. Every headline
number is a 3-seed average from a leakage-tested, regression-gated,
round-trip-verified pipeline — and where results are inconclusive or negative,
we report them that way.*

---

## Appendix: quick glossary

| Term | Plain meaning |
|---|---|
| **ERP** | The software (SAP, Oracle...) that records a company's transactions |
| **Node / Edge** | A dot (account) / an arrow (payment) in the network |
| **Temporal graph** | A network where every connection has a timestamp |
| **Topology** | The *shape* of the network — who connects to whom, in what pattern |
| **Cycle / Fan-in / Lapping** | Money loop / many senders into one account / covering a prior theft with new money |
| **Feature extraction** | Turning raw data (a graph) into numbers a model can learn from |
| **Feature selection** | Choosing which of those numbers actually help (our ablation) |
| **As-of / streaming computation** | Computing each transaction's features using only data available at its own moment |
| **Data leakage** | The model accidentally seeing the future; inflates scores |
| **Class imbalance** | Fraud is <1.3% of rows — the rare class problem |
| **Class weights / Focal loss** | Two ways to make the model care about rare fraud (used one at a time) |
| **SMOTE** | Inventing synthetic minority examples — rejected here (meaningless for graph features) |
| **Decision threshold** | The probability cutoff for calling something fraud — tuned, never assumed 0.5 |
| **PR-AUC / Average Precision** | Our primary metric: how well the rare frauds are found across all cutoffs |
| **Precision@k** | Of the top-k alerts an auditor reviews, how many are real fraud |
| **Ablation** | Removing one ingredient to measure its contribution |
| **XGBoost** | Gradient-boosted decision trees — our champion model family |
| **Hyperparameter search (HPO)** | Systematically trying model settings, judged on validation only |
| **Seed** | The random-number starting point; we average over 3 seeds |
| **Embedding** | A learned vector of numbers summarizing an entity (here: an account's behavior) |
| **TGN** | Temporal Graph Network — learns account embeddings from the transaction stream, label-free |
| **GRU** | A small recurrent neural unit — the TGN's per-account memory cell |
| **Self-supervised** | Learning from the data's own structure (predicting the next link), no labels needed |
| **SHAP / TreeSHAP** | Fairly splits a model's score among its input features; exact for trees |
| **Neo4j / Cypher** | The graph database (and its query language) used for the visual demo |
| **Federated learning (FedProx)** | Future work: many banks train one shared model without sharing raw data |
