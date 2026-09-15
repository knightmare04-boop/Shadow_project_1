# The Self-Auditing Ledger — Project Overview & Finalized Architecture

*A complete, plain-language explanation of what we are building, why, how it
works, what we have done so far, and what comes next. Written so it can be
presented and defended to a reviewer. This document also serves as the **locked
architecture** — once approved, we build from exactly what is described here.*

> **⚙️ If you are an AI assistant being handed this project:** this file is your
> complete context — read all of it. **Sections 0–15** are the reasoning and the
> locked architecture; **Appendix A (at the very end)** is the precise operational
> state — environment, how to run things, file-by-file code status, exact dataset
> results, the non-negotiable rules, and a dated changelog. The project's private
> context (`CLAUDE.md`, `docs/DESIGN.md`, the user's memory) is **not** available to
> you, so this document is designed to stand alone. **Standing rule for this
> project: after every step or change, update Appendix A's changelog and any
> section it affects**, so this file always reflects the latest state.
> **Resuming after a context `/clear`? Jump straight to Appendix A.0** — it is the
> re-bootstrap procedure that keeps you from drifting or acting on stale state.

---

## How to read this document

It is long because it is complete, but it is built in layers. If you only have
five minutes, read **Section 0 (Executive Summary)** and **Section 14 (The Locked
Decisions)**. Everything in between explains *why* those decisions are correct.
Section 15 is a plain-language glossary — if any word confuses you, look there.

A note on the word "phase":
- **Phase 1 / Phase 2** = the two *conceptual* halves of the system (build the
  graph and extract features → train a model).
- **Build Step 0–6** = our *work plan* (the order we actually do things).

These are different things. We keep them separate on purpose.

---

## 0. Executive Summary (the elevator pitch)

**What it is.** An ERP* fraud-detection research system. Instead of judging each
transaction on its own, we turn a company's transaction history into a
**temporal graph** (a network of who-paid-whom, stamped with time) and look for
**suspicious shapes** in that network — money moving in circles, many accounts
funneling into one, rapid multi-step transfers. We then feed those "shape"
measurements to a machine-learning model that scores each transaction's fraud
risk, and we explain every alert by showing the exact suspicious path.

**The honest scientific claim.** A real-time production platform is the long-term
*vision*. The thing we actually set out to *prove* is narrower and defensible:

> **Do graph-shape ("topology") features add real predictive value on top of a
> strong ordinary-transaction baseline — when measured fairly, with no cheating
> (no data leakage)?**

**Why this is worth doing.** A previous version of this project claimed "graph
topology is the differentiator," but when we audited it, its *own results
contradicted that claim*, and all its scores were inflated by data leakage (the
model was accidentally allowed to see the future). So the central idea has never
actually been tested fairly. We rebuilt the project to test it properly — and we
commit to reporting the result **either way**, even if it turns out topology does
*not* help. Designing the fair test is the contribution.

**Key talking points for the presentation:**
1. We are testing a hypothesis, not just shipping a tool.
2. We found and fixed a serious flaw (data leakage) in the prior approach.
3. Our architecture is designed so that "cheating" (seeing the future) is
   structurally impossible.
4. We pick datasets along a spectrum of "graph richness" so we can show *when*
   graph structure helps and when it doesn't.
5. We will report a negative result honestly if that is what the data shows.

*ERP = Enterprise Resource Planning, the software (SAP, Oracle, etc.) that records
a company's financial transactions. See glossary.*

---

## 1. The big idea, in plain English

Most fraud-detection systems look at one transaction at a time: *Is this $5,000
payment unusual on its own?* That misses an entire class of fraud, because real
financial fraud is usually **a pattern made of several connected transactions**,
not one obviously-bad payment. Examples:

- **Circular payments:** A pays B, B pays C, C pays A. Money goes in a loop.
  Legitimate business almost never sends money in circles.
- **Lapping:** new incoming money is used to cover a previously stolen amount,
  forming a chain of "robbing Peter to pay Paul."
- **Fan-in / collection:** many accounts rapidly funnel money into one account
  (a classic money-mule collection pattern).
- **Rapid transfer chains:** money hops A→B→C→D→E in seconds (layering, to hide
  the trail).

None of these look wrong if you stare at a single row in a spreadsheet. They only
become visible when you **draw the money flow as a network and look at its
shape**. That network is what we call the **Shadow Graph** — a live "shadow" or
mirror of the company's real transactions:

```
   account = a dot (node)        payment = an arrow (edge), stamped with time + amount

        (A) ──$10k, 10:00──▶ (B) ──$10k, 10:03──▶ (C)
         ▲                                          │
         └──────────────$10k, 10:05────────────────┘      ←  a 3-step money LOOP
```

The word **temporal** matters: every arrow carries a timestamp, so the graph
preserves both **structure** (who connects to whom) and **chronology** (in what
order). Fraud patterns are defined by *both* — a loop that closes within 5 minutes
is suspicious; the same accounts transacting months apart is not.

---

## 2. The scientific question we are actually answering

It is important (especially for a research project) to separate the **vision**
from the **proof**.

- **The vision** (from the original project description): a real-time platform
  that watches an ERP system live, maintains the Shadow Graph, and raises instant,
  explainable fraud alerts. This is the inspiring story and the demo we will build.
- **The proof** (what earns a defensible result): a careful, leakage-free
  experiment answering one question —

> **Claim:** Topology features (the graph-shape measurements) improve fraud
> detection compared to a strong baseline that uses only ordinary transaction
> features — and this improvement survives a fair, no-leakage evaluation.

Everything in the architecture is built to make that claim **testable and
trustworthy**. The decisive test is described in Section 9 (the "ablation").

### Is this still a real-time auditor? Yes.

"Vision vs. proof" is about what we scientifically *claim*, **not** about what we
build. We are **not** dropping the real-time, explainable auditor — we are building
it. The distinction only means: we *prove* the narrow, measurable claim above
(rather than claiming "we shipped a finished product").

The reassuring part: **our leakage-free design and the real-time design are the
same design.** The core rule — "for each transaction, look only at the past, then
move on" — is *literally how a real-time system works* (it reacts to events as they
arrive and cannot see the future). So being scientifically careful did not cost us
the real-time auditor; it **is** the real-time auditor. We get rigor for free.

What that means concretely:

| We ARE building | We are NOT claiming |
|---|---|
| The streaming engine: event in → graph updates → topology features from the past → risk score | A product deployed live inside a company's running SAP server |
| The explainable audit alert (SHAP + the detected fraud path, shown in Neo4j) | Millisecond-latency production hardening / live ERP integration |
| A **live demo**: replay a real dataset transaction-by-transaction through the engine and watch alerts fire | "We shipped a finished commercial platform" |

The demo runs on **recorded** datasets replayed *as if* streaming — which is
necessary for research, because we need *labeled* data (known fraud / not-fraud) to
measure accuracy; a live production system never tells you the ground truth.

**One-line framing for the presentation:** *"We built the real-time, explainable
fraud-detection engine, **and** we rigorously proved its graph features add value
without leakage."* Two deliverables, both real — not one instead of the other.

---

## 3. Why we rebuilt — what went wrong before (and why that is good to present)

There was an earlier version of this project (kept in the repo under `reference/`,
read-only). It ran 6 datasets and concluded *"graph topology is the ultimate
differentiator."* We audited it thoroughly before writing any new code. We found
two serious problems. Presenting this honestly is a strength — it shows scientific
rigor.

**Problem 1 — the headline claim was contradicted by its own results.**
On its flagship dataset, the model's own "feature importance" report showed the
predictive signal came almost entirely from `total_amount` (62%) and a couple of
amount statistics. **Every graph-shape feature — cycles, lapping, density, chains —
scored 0.0 importance.** The very features the project was about contributed
nothing. The success was claimed, not demonstrated.

**Problem 2 — the impressive scores were inflated by data leakage.**
"Data leakage" means the model was accidentally allowed to use information it would
not have at prediction time — usually information from the **future**. This makes
test scores look great but they collapse in the real world. There were two leaks
stacked together:

- *The feature engine looked into the future.* It computed each transaction's
  graph features using the **entire** graph, including transactions that happened
  *later*. One of its top features was literally "time until the **next**
  transaction." That is using tomorrow to predict today.
- *The evaluation protocol leaked too.* It mixed past and future randomly when
  splitting data for testing, used a careless way of handling the rare-fraud
  imbalance, and never tuned its decision cutoff. (Details in Section 8.)

**Conclusion.** The good idea was never given a fair test. The old numbers (e.g.
"99.7% AUC") are not trustworthy. So we are not "improving" those numbers — we are
**discarding them and producing the first honest ones.** We keep the old code only
as a source of proven data-cleaning tricks, never its model/evaluation code.

---

## 4. The finalized architecture (LOCKED)

This is the pipeline. Data flows top to bottom. Each box is one responsibility.

```
   ┌──────────────────────────────────────────────────────────────────┐
   │  RAW DATA  (transaction CSVs from public fraud datasets)          │
   └───────────────────────────────┬──────────────────────────────────┘
                                    ▼
   (1) ETL  ─ "clean + standardize" ───────────────────────────────────
        Turn each dataset's messy raw columns into ONE canonical form:
        Accounts (nodes) + Transactions (edges with time, amount, label).
                                    ▼
   (2) SHADOW GRAPH  ─ the temporal network of money flow ─────────────
        Accounts = nodes;  transactions = time-stamped directed edges.
                                    ▼
   (3) TEMPORAL TOPOLOGY ENGINE  ─ "find the shapes" ──────────────────
        For each transaction, measured ONLY from the past (no future!):
        cycle? fan-in? rapid chain? lapping? how dense/central?  → numbers
                                    ▼
   (4) FEATURE TABLE  ─ one row per transaction ──────────────────────
        ordinary features (amount, time gaps, account info)
        + topology features (the shape measurements)  + the fraud label
                                    ▼
   (5) MODEL  ─ machine learning risk scorer ─────────────────────────
        Gradient-boosted trees (XGBoost / LightGBM), trained the RIGHT way
        (time-aware, one imbalance fix, tuned cutoff)  → fraud probability
                                    ▼
   (6) EVALUATION + THE ABLATION  ─ "did topology actually help?" ─────
        Compare: baseline (ordinary only)  vs  ordinary + topology.
        Measured with PR-AUC and precision@k on a future test period.
                                    ▼
   (7) EXPLAINABLE AUDIT ALERT  ─ "why was this flagged?" ─────────────
        SHAP (which features drove the score) + the actual suspicious
        path drawn from the graph (shown live in Neo4j for the demo).
```

### The one big engineering decision (and why)

We compute everything in **Python (Pandas + NetworkX/igraph)**, and use **Neo4j
only for the visual demo and path explanations** — *not* for the heavy
computation. Why: the old version tried to do the heavy computation inside Neo4j
and it **ran out of memory** on the larger datasets, which forced it to silently
turn topology off (another reason its results were meaningless). Python computes
the features reproducibly, at scale, and lets us guarantee no leakage. Neo4j is
where we *show* the shadow graph and the detected fraud path — its real strength
(visualization and explanation), without betting the whole pipeline on it.

### The code layout (so the work maps cleanly to the architecture)

| Folder (`src/…`) | Architecture box | Responsibility |
|---|---|---|
| `common`   | (all)        | Config loader, logging, Neo4j connection |
| `etl`      | (1)          | Raw CSV → canonical accounts + transactions |
| `graph`    | (2)          | Load the graph into Neo4j (for the demo) |
| `topology` | (3)          | The detectors + structural features (single copy) |
| `features` | (4)          | Assemble the per-transaction feature table |
| `modeling` | (5)(6)       | Time-aware training, cutoff tuning, evaluation, saving |
| `experiments` | (6)       | `run_dataset.py` (full pipeline), `ablation.py` (the test) |

---

## 5. The datasets — and why we use several of them

A subtle but important design choice. Our question is *"does graph structure
help?"* — so the natural thing to vary across datasets is **how much real graph
structure each one has.** We line the datasets up on a spectrum from "rich
structure" to "no structure," and run the **same test** on each. If topology
features help more on the structure-rich datasets and less on the flat ones, that
pattern is strong evidence. (The old project compared *across* datasets that
differed in *everything* at once, which proves nothing. We instead test *within*
each dataset, then look at the trend.)

| Tier | Dataset | Size | Fraud rate | Graph structure | Role in our study |
|---|---|---|---|---|---|
| **1** | **IBM AML** | 1.32M txns | 0.13% | **Rich** — real account↔account, true cycles | The decisive testbed for topology |
| **1** | **BankSim** | 595k txns | 1.21% | **Sparse** — customer→merchant only, no cycles possible | The control: topology *should* help less here |
| 2 | **SAP Würzburg** | 200,629 lines / 59,852 docs | 0.12% (248 frauds) | Thin ERP **bipartite** — doc↔G/L account, only ~31 accounts | Real ERP domain + the explainability demo (topology signal expected weak) |
| 2 | **PaySim** | 6.36M txns | 0.13% | **Sparse** — near-forest (sender/receiver overlap 0.0002), at scale | Proves the engine scales; transfer→cash-out fraud |
| ~~3~~ | ~~**FIFAR**~~ | 506k rows | 1.13% | None (pure tabular) | **Dropped from Phase 1** — no counterparty graph, so topology cannot be extracted |
| — | ~~SAP IDES~~ | — | — | **Dropped** | A trial-watermarked file left only 7 frauds — unusable |

**Why this is the right answer to "should we use all of them?"** Yes — but for a
*reason*, not just to show work. Each dataset is a different point on the
structure spectrum, so together they map out *when* the method helps. We do them
in **tiers** (start with the two that matter most) so we get a trustworthy answer
quickly before investing in the giant 6.3M-row dataset.

**About fraud rates:** notice every dataset is **extremely imbalanced** — fraud is
0.08%–1.2% of transactions. This single fact drives almost all of our modeling
rules (Section 8). When 99.9% of cases are "not fraud," ordinary accuracy is
worthless (a model that says "never fraud" is 99.9% accurate and catches nothing).

---

## 6. Phase 1, part A — building the Shadow Graph (the data layer)

**Goal:** turn four very different raw datasets (FIFAR dropped — see Section 5)
into one consistent shape so the rest of the pipeline does not care which dataset
it is looking at.

**The canonical form** (the single standard we convert everything into):
- **Nodes = Accounts.** Each account is one dot, with attributes when available
  (country, account type, starting balance, "known bad actor" flag).
- **Edges = Transactions.** Each transaction is one arrow from sender account to
  receiver account, carrying `amount`, `timestamp`, and the fraud `label` (0/1).
- **The prediction unit is one transaction** (one edge). We score each transaction.

**The single most important fix vs. the old version — the "unified account
namespace":** In the datasets with real account-to-account money flow, the old ETL
put senders in one bucket ("Account") and receivers in a *different* bucket
("Vendor"). That meant account #6456-as-a-sender and #6456-as-a-receiver became
**two different dots** — so a loop A→B→A was *impossible to see*. We verified this
was the bug and fixed it: **senders and receivers share one account identity**, so
loops and chains are visible again. (We confirmed in the data that 99.3% of sender
IDs also appear as receiver IDs — they really are the same accounts.)

---

## 7. Phase 1, part B — the Temporal Topology Engine (the heart of the project)

This is where we turn **shapes into numbers**. It is also the part most vulnerable
to leakage, so its design is the most important thing in the whole project.

### 7.1 The golden rule: only ever look at the past (no look-ahead)

**The auditor analogy.** Imagine an auditor sitting at a desk as transactions
arrive one by one. When transaction #500 lands, the auditor may look at #1–#500 to
judge it — but *cannot* see #501 onward, because those have not happened yet. Our
engine works **exactly** like this:

> Process transactions in time order. For a transaction at time **T**, compute its
> features using only transactions with timestamp **≤ T** (optionally only those in
> a recent window, e.g. the last 24 hours or 7 days). Then add it to the graph and
> move on.

Because we *only ever look at edges already added*, **the future cannot leak in —
it is structurally impossible.** This is the same "incremental / streaming" idea
the original vision describes for real-time operation, so the realistic design and
the leakage-safe design are the **same** design. Two supporting rules:

1. **No whole-dataset statistics.** Any average or z-score (e.g. "is this amount
   unusual for this account?") is computed only over that account's *past*
   transactions, growing as time goes on — never over the entire dataset (which
   would include the future).
2. **Credit the closer, not the openers.** When a loop A→B→C→A finally closes, the
   "this is part of a cycle" signal is attached to the transaction that *closed*
   it (the one we are scoring now) — not pasted backward onto A's earlier payment
   (which, at the time, could not have known a loop would form).

We will also include an automated **leakage test**: scramble the *future*
transactions and confirm a past transaction's features do **not** change. If they
change, we have a leak and the build fails.

### 7.2 The detectors (what shapes we look for)

Each detector scans the *as-of-T* graph (past only, within a time window) and
outputs a few numbers per transaction. We start with the two that match the
**known** fraud shapes in our decisive dataset (IBM AML's frauds are literally
labeled as cycles and fan-ins), then add the rest:

| Detector | The shape it finds | Plain meaning |
|---|---|---|
| **Cycle** | A→B→…→A loop within a time window | Money returning to its origin — laundering / round-tripping |
| **Fan-in / Fan-out (density)** | Many edges into/out of one account fast | Collection (mule) or distribution hub |
| **Rapid chain** | A→B→C→D… with tiny time gaps | Layering — moving money fast to hide the trail |
| **Lapping** | Near-equal sequential amounts on one entity | Covering a prior shortfall with new money |
| **Real centrality** | PageRank / betweenness / degree on the as-of graph | How "central" or busy an account is in the network |

Each becomes features like: `in_cycle` (yes/no), `cycle_length`, `cycle_amount`,
`fan_in_count`, `max_chain_length`, `account_pagerank`, etc. (The old version's
"centrality" was fake — it was just counting edges. Ours uses real graph
algorithms.)

### 7.3 The output

A **feature table**: one row per transaction, columns = ordinary features +
topology features + the label. This table is what Phase 2 trains on. Crucially,
the ordinary and topology columns are kept clearly separable so we can switch
topology on and off for the ablation (Section 9).

---

## 8. Phase 2 — how the model works (and the rules that keep it honest)

### 8.1 The two-phase logic

The graph engine **finds and measures** the shapes (Phase 1). The model does *not*
re-discover shapes — it **learns which shape-measurements actually predict real
fraud** and combines them with ordinary features into a single risk score
(Phase 2). Input = the feature row; output = a fraud probability (0 to 1).

### 8.2 Which model, and why

We use **gradient-boosted decision trees** (XGBoost / LightGBM) as the workhorse,
with logistic regression as a simple baseline. Why gradient-boosted trees:
- They are the state of the art on **tabular** (table-shaped) data like ours.
- They handle **imbalance** well.
- They are **interpretable** — we can see exactly which features drove a score
  (via SHAP). That matters because **explainability is our selling point.**

We deliberately treat fancy Graph Neural Networks (GNNs) as *optional future
comparison only* — they are black boxes, which works against our goal of giving
auditors clear, explainable reasons.

### 8.3 The five non-negotiable rules (each is a fix for a real old-version flaw)

These are the difference between trustworthy and meaningless results. Each is
simple once explained:

1. **One imbalance fix, never two.** Because fraud is so rare, models need help
   noticing it. There are two common tools: *resampling* (e.g. SMOTE, which
   invents synthetic fraud examples) and *class weights* (telling the model "fraud
   mistakes count more"). The old version used **both at once**, which
   double-counts and distorts. We use **exactly one — class weights** — per
   experiment. (We avoid SMOTE for graph features because inventing a synthetic
   "halfway between two cycles" example is physically meaningless.)

2. **Tune the decision cutoff; never assume 0.5.** A model outputs a probability;
   we need a cutoff to call it "fraud." The default 0.5 is arbitrary. We **choose**
   the cutoff on a validation period (e.g. the one that best balances catching
   fraud vs false alarms), then **freeze** it before touching the test data.

3. **Time-aware testing; never shuffle time.** We train on **earlier** transactions
   and test on **later** ones — exactly how the real world works (you predict the
   future from the past). The old version shuffled transactions randomly, letting
   the model effectively "study the answers" from the future. That is the single
   biggest evaluation leak, and we forbid it.

4. **No look-ahead through the graph.** (Already enforced in Phase 1, Section 7.1 —
   listed again here because it is a modeling-integrity rule too.)

5. **Right metrics for rare events.** We report **PR-AUC** (a.k.a. average
   precision) — which focuses on how well we find the rare frauds — as the *primary*
   metric, and **precision@k / recall@k** ("of the top-N alerts an auditor actually
   reviews per day, how many are real fraud?"). We de-emphasize plain accuracy and
   ROC-AUC, which look flattering on imbalanced data. We never pick the "best"
   model by its 0.5-cutoff score.

**One more rule — keep the evidence.** Every trained model is saved together with
its data-scaler and its frozen cutoff, so any result can be reproduced exactly.

---

## 9. The experiment that decides everything — the ablation

This is the core scientific test, and the old project never ran it.

> Take one dataset. Use the **same** time-aware split, the **same** model, the
> **same** single imbalance fix. Train it **twice**:
> - **(A) Baseline:** ordinary transaction features only.
> - **(B) Baseline + Topology:** the same, plus our graph-shape features.
>
> Compare their PR-AUC (and precision@k). Repeat for each dataset.

- If **(B) clearly beats (A)** — especially on the structure-rich IBM AML data —
  then the thesis is **proven**, properly and for the first time.
- If **(B) does not beat (A)**, that is an honest, publishable **negative result**:
  *"explicit topology features add no value beyond ordinary features on these
  datasets."* That is far more credible than the old, leakage-inflated "success,"
  and still a real scientific contribution (a fair test designed and run).

We commit, up front, to reporting **whichever way it lands.** (`experiments/
ablation.py` is the script that runs this.)

---

## 10. Explainability — the audit alert (our differentiator)

A risk score of "0.97" is useless to an auditor who must justify an investigation.
So when a transaction is flagged, we produce a human-readable alert with two parts:

1. **Why the model scored it high** — via **SHAP**, which lists the features that
   pushed the score up (e.g. "+0.4 because it closes a 3-step cycle within 5
   minutes; +0.2 because the amount is unusual for this account").
2. **The actual evidence** — the concrete suspicious **path** drawn from the
   graph (e.g. `Vendor_A → Vendor_B → Vendor_C → Vendor_A, $50,000, 5 minutes`),
   shown visually in **Neo4j** for the demo.

This is the part of the original vision most worth keeping, and the old version
never actually built it.

---

## 11. What we have done so far (concrete progress)

**Build Step 0 — Audit & honest re-baseline. ✅ Done.**
- Read the entire old project (feature engine, ETL, all training scripts, reports).
- Confirmed the two leakage problems and the "topology scored 0 importance"
  finding (Section 3). This is *why* we rebuild.

**Architecture & decisions — Locked. ✅ Done.**
- All major decisions agreed and written into `CLAUDE.md` (the project rulebook),
  `docs/DESIGN.md` (the technical reasoning), and this document.

**Build Step 1 — ETL / Shadow Graph for all four datasets. ✅ Done & verified.**
We built the canonical-graph builder and ran it on every dataset in the roster:

| Dataset | Transactions | Accounts | Fraud rate (verified) | Namespace overlap | Result |
|---|---|---|---|---|---|
| **IBM AML** | 1,323,234 | 10,000 | 0.13% (1,719 frauds) | **99.3% → unified ✓** | Cycles now detectable |
| **BankSim** | 594,643 | 4,162 | 1.21% (7,200 frauds) | **0.0% → bipartite ✓** | The sparse (pure-bipartite) control |
| **PaySim** | 6,362,620 | 9.07M | 0.13% (8,213 frauds) | **0.0002 → near-forest ✓** | Engine scales to 6.3M rows |
| **SAP Würzburg** | 200,629 lines | 31 G/L (+ 59,852 docs) | 0.12% (248 frauds) | **0.0 → bipartite ✓** | Genuine ERP ledger as doc↔account |

- The unified-account fix is **working and verified** (it was the #1 bug before).
- **A key finding that makes IBM AML the perfect testbed:** *every one* of its
  1,719 frauds is a known shape — **936 cycles + 783 fan-ins**. So if our graph
  features cannot beat the baseline here, they cannot anywhere — and we have the
  ground-truth shape labels to check our detectors against.
- We also discovered two bonus files the old version ignored: per-account
  attributes (`accounts.csv`) and the fraud-shape labels (`alerts.csv`). We use the
  shape labels for *evaluation only* — never as a model input (that would be
  cheating).
- **SAP Würzburg** has no sender/receiver columns — it is a real SAP double-entry
  ledger. We derive a **document↔G/L-account bipartite graph** (each posting line
  is one edge), carry the real fraud typologies (Larceny, Invoice Kickback, …) as
  eval-only metadata, and synthesise an honest per-run time axis. Its entity graph
  is tiny (≈31 accounts), so we expect its topology signal to be weak — and we will
  report that honestly. It earns its place as the one **genuine ERP** dataset.
- **FIFAR is dropped from Phase 1:** it is purely tabular (no counterparty graph),
  so there is nothing to build a Shadow Graph from.

**In short: the foundation (clean, correct, leakage-aware data layer) is built and
verified for all four datasets — spanning the full structure spectrum from
pure-bipartite (BankSim, Würzburg) through near-forest (PaySim) to dense and
cycle-rich (IBM AML).**

---

## 12. What comes next (the roadmap)

| Build Step | What | Status |
|---|---|---|
| 0 | Audit & re-baseline | ✅ Done |
| 1 | ETL / Shadow Graph (all 4 datasets; FIFAR dropped) | ✅ Done |
| **2** | **Temporal Topology Engine** — the leakage-free feature extractor (Section 7) | ✅ **Core done** — cycle (+ discriminative amount-conservation/tightness/≥3-hop), fan-in/density, lapping, automated leakage test. **Verdict (A.4d): plain density is the topology signal; cycles redundant, lapping is amount-derived.** Optional later detectors (rapid-chain, real centrality) expected density-correlated |
| 3 | Modeling harness — time-aware training, cutoff tuning, metrics, saving (Section 8) | ✅ **Built** — class-weighted XGBoost, val-tuned threshold, PR-AUC |
| 4 | **The Ablation** — does topology help? (Section 9) | ✅ **Done (structure-only)** — A.4d: banksim structure +11.7% (real); ibm modest, amount-dominated; sap inconclusive. Answers DESIGN §9 |
| **5** | Explainability — SHAP + Neo4j audit-alert demo (Section 10) | ✅ **Done (A.4e)** — TreeSHAP audit alerts with verified graph evidence on all 4 datasets; Neo4j demo code complete + self-verifying (live run needs a local instance, `docs/NEO4J_DEMO.md`) |
| — | **FINAL model** — TGN embeddings → XGBoost head, per-dataset mechanism selection, light HPO | ✅ **Done (A.4e)** — champions persisted + round-trip verified for all 4 datasets |
| 6 | Optional — PaySim scale, GNN end-to-end comparison, FT-Transformer challenger | Future work (synthetic ERP generator was pulled forward and shipped 2026-07-13) |

All build steps are complete; remaining items are future work (A.8).

---

## 13. The technology stack (one place)

- **Python** — everything.
- **Pandas / NumPy** — data handling.
- **NetworkX / igraph** — graph computation (the compute path).
- **Neo4j** — graph visualization & path explanation (the demo path only).
- **scikit-learn, XGBoost, LightGBM** — the models and evaluation.
- **PyTorch** — the TGN embedder (CPU; label-free, amount-blind temporal embeddings
  feeding the XGBoost head).
- **TreeSHAP** — model explanations, computed natively by XGBoost
  (`pred_contribs=True`); the `shap` package is an optional extra for plots only.
- **Matplotlib / Seaborn / Plotly** — plots and interactive visuals (Plotly for
  interactive result charts + standalone interactive fraud-path figures).

---

## 14. The LOCKED decisions (the architecture we commit to)

After approval, we build from exactly this. Nothing here changes without a
deliberate, recorded decision.

1. **Two-phase design:** (Phase 1) build a temporal Shadow Graph and extract
   topology features per transaction; (Phase 2) train an ML model on the resulting
   feature table.
2. **Goal = both** a rigorous research result *and* an explainable demo.
3. **Compute in Python (Pandas + NetworkX/igraph); Neo4j is the demo/explanation
   layer only.**
4. **Canonical data model:** Accounts (nodes) + Transactions (time-stamped edges);
   senders and receivers share **one** account namespace; the prediction unit is
   one transaction.
5. **Leakage-free by construction:** as-of / streaming feature computation, past
   only; no whole-dataset statistics; signal credited to the transaction that
   completes a structure; an automated leakage test guards it.
6. **Detectors:** cycle, fan-in/fan-out (density), rapid chain, lapping, plus real
   centrality. (Cycle + fan-in first, matching IBM AML's known fraud shapes.)
7. **Model:** gradient-boosted trees (XGBoost/LightGBM) + logistic baseline;
   GNNs are optional future comparison only.
8. **Honest evaluation:** time-aware splits; exactly one imbalance mechanism
   (class weights by default); decision cutoff tuned on validation and frozen;
   PR-AUC primary + precision@k; models saved with scaler and cutoff.
9. **Validation method:** the within-dataset **ablation** (baseline vs
   baseline+topology) is the decisive test; we report the result either way.
10. **Datasets (tiered):** Tier 1 IBM AML + BankSim; Tier 2 SAP Würzburg + PaySim;
    Tier 3 FIFAR (optional). SAP IDES dropped.
11. **Explainability:** SHAP feature attributions + the detected graph path, shown
    in Neo4j.
12. **Synthetic ERP generator:** deferred (and, if built later, designed to avoid
    the circularity trap — fraud injected by behavior, not by detector pattern).

---

## 15. Glossary (plain-language)

- **ERP:** the software that records a company's transactions (SAP, Oracle, etc.).
- **Topology / graph structure:** the *shape* of the money-flow network — who
  connects to whom, in what pattern.
- **Temporal graph:** a network where every connection has a timestamp, so order
  and timing matter, not just structure.
- **Shadow Graph:** our live network mirror of the ERP's transactions.
- **Node / Edge:** a node is a dot (an account); an edge is an arrow (a transaction).
- **Data leakage:** accidentally letting the model use information it would not
  have at prediction time (usually from the future). Makes test scores look great
  but they fail in reality.
- **Look-ahead:** a specific leak — using future transactions to compute a present
  transaction's features.
- **As-of / streaming computation:** computing each transaction's features using
  only data available *as of* its own time — the cure for look-ahead.
- **Class imbalance:** when one class (fraud) is extremely rare (here <1.3%).
- **SMOTE:** a method that invents synthetic minority (fraud) examples to balance
  the data. We avoid it for graph features (synthetic "half-cycles" are meaningless).
- **Class weights:** telling the model that mistakes on the rare class count more.
  Our chosen imbalance fix.
- **Decision threshold / cutoff:** the probability above which we call something
  fraud. We tune it instead of assuming 0.5.
- **Cross-validation:** a way of testing a model on data it did not train on. We use
  a **time-aware** version (train on the past, test on the future).
- **PR-AUC / Average Precision:** a metric that measures how well we find the rare
  positives (fraud). Our primary metric on imbalanced data.
- **Precision@k / Recall@k:** of the top-k alerts an auditor actually reviews, how
  many are real fraud (precision), and what fraction of all fraud do they cover
  (recall). The operationally honest metric.
- **ROC-AUC:** a popular ranking metric that looks flatteringly high on imbalanced
  data — we report it but do not rely on it.
- **Ablation:** an experiment that removes one ingredient (here, the topology
  features) to measure how much it was contributing.
- **Cycle / Fan-in / Lapping / Chain:** the fraud shapes (Section 1 / 7.2).
- **Segregation of Duties (SoD):** an internal-control rule that one person should
  not control multiple steps (create + approve + pay) of a transaction. Only the
  SAP dataset could support this detector, so we treat it as ERP-specific.
- **SHAP:** a method that explains a model's score by how much each feature pushed
  it up or down.
- **GNN (Graph Neural Network):** an ML model that learns directly on graphs. Powerful
  but a black box — we keep it as optional future comparison, not the core.
- **XGBoost / LightGBM:** gradient-boosted decision-tree models; our workhorse.

---

# Appendix A — AI Session-Continuity Brief

*This appendix exists so any fresh AI session can continue the project **identically**.
It captures the operational state the prose above does not: environment, how to run
things, exact code status, exact data results, the binding rules, and a running
changelog. **Standing rule: after every step or change, update this appendix (its
changelog and any affected entry) and any section above it touches.** This file is
the only context a new session gets — `CLAUDE.md`, `docs/DESIGN.md`, and the user's
memory are not shared with it.*

## A.0 — Re-bootstrap procedure (do this FIRST after a `/clear` or in a fresh session)

You are resuming a project whose chat context was just cleared. To pick up exactly
where the last session left off — **without drifting, hallucinating, or acting on
stale information** — follow these steps before doing anything else:

1. **This Appendix A is the single source of truth for the live state.** Trust it
   over any status you remember, any older line in the user's memory, or anything in
   chat. If they disagree, Appendix A wins.
2. **Read this whole appendix (A.0–A.9).** It is the operational state. Sections
   0–15 above are the *reasoning* and the locked architecture — consult a specific
   one only when a task needs the deeper "why" (don't re-read all 700 lines; that
   wastes the credits `/clear` is meant to save).
3. **Ground every important claim in the actual repo before acting — never trust
   prose alone.** Cheap checks that prevent hallucination:
   - `ls data/processed/` → which datasets are actually built (vs. what A.5 claims).
   - Read the file you are about to change (e.g. `src/etl/build.py`) before editing.
   - `git log --oneline -5` and `git status` → real recent history and working tree.
   If the repo contradicts this document, **the repo is right** — fix the document.
4. **The changelog (A.9) is the authoritative timeline** of what has been done;
   **"What's next" is A.8.** Start your work from A.8.
5. **When you finish a step, update this appendix** (the affected A.4/A.5/A.8 entry
   *and* a new dated A.9 line) before telling the user you're done. That is what
   keeps the next post-`/clear` session correct.

## A.1 — How to work on this project (collaboration norms)

- Act as a **co-engineer**, not an order-taker: challenge weak choices, explain
  plainly, recommend a path, and **confirm before proceeding** on anything
  irreversible or architecture-touching. The user explicitly wants pushback, not
  blind agreement.
- The **architecture (Sections 4 & 14) is FROZEN.** Build from it; do not propose
  architecture changes. Implementation details (window length, exact feature list,
  thresholds, detector internals) remain tunable.
- **Commit/push only when the user explicitly asks.** Never add AI attribution to
  commits or PRs.
- **Keep this document current** — it is the single source of truth a new session
  relies on. Updating it is the last sub-step of every task.

## A.2 — Environment & how to run

- **OS:** Windows 11. **Shells:** PowerShell (primary) + Git Bash (POSIX). Many
  paths contain spaces — always quote them.
- **Python 3.14, pandas 3.0.3.** One-time install: `pip install -e .` (makes
  `common`, `etl`, `topology`, … importable with no `sys.path` hacks).
- **Raw datasets live OUTSIDE the repo** at
  `C:/Users/Aarin Bhatta/OneDrive/Desktop/Projects/erp datasets/` (gitignored,
  never pushed).
- **Run the ETL for one dataset:** `python -m etl.build <dataset>` → writes
  `data/processed/<dataset>/{edges_transactions.csv, nodes_accounts.csv, audit.json}`.
- **Config:** `config/datasets.yaml`. Loader: `src/common/config.py::get_dataset(name)`
  returns the entry with absolute raw paths + a resolved `processed_dir`.

## A.3 — Repository & data hygiene

- **GitHub:** `Aarin062/NodeWatch` (private). Local folder is `shadowGraphs` (the
  name differs on purpose). Git identity `Aarin062 <aarinbhatta@gmail.com>`.
- **Never pushed / gitignored:** `reference/` (the old project), all of `data/`
  (raw + processed), `docs/` (including this file), `CLAUDE.md`,
  `.claude/settings.local.json`.
- **No AI attribution:** global `includeCoAuthoredBy: false`; existing
  `Co-Authored-By` trailers were purged from history. Do not reintroduce them.

## A.4 — Current code state (file-by-file)

| Path | Status | What it does right now |
|---|---|---|
| `config/datasets.yaml` | ✅ | 4 datasets configured: `ibm_aml`, `banksim`, `paysim`, `sap_wurzburg`. FIFAR intentionally absent. |
| `src/common/config.py` | ✅ | `load_config`, `get_dataset`; resolves a `raw` entry that is a **string OR a list** of paths; resolves `processed_dir`. |
| `src/etl/build.py` | ✅ | `build_dataset(name)` dispatches on `kind`. `transfer`/`bipartite` → generic path (rename schema cols → canonical, unify account namespace, binary label, attach alert typology). `erp_ledger` → `_build_erp_ledger` (derives a document↔G/L-account bipartite graph). Writes the 3 canonical files + audit. Helpers: `_to_binary_label`, `_strip_quotes`, `_seconds_since_midnight`. |
| `src/topology/window_graph.py` | ✅ | `WindowGraph` — incremental directed multigraph over a trailing window. O(1) fan-in/fan-out/degree; bounded BFS `cycle_features` (≤ `max_cycle_len` edges, ≤ `search_budget` nodes) that **reconstructs the loop path** and reports its amount/timestamp aggregates. Each directed pair remembers its most-recent `(amount, ts)` in `self.last` (correct under FIFO eviction). Holds only past edges (engine inserts each edge *after* reading its features). |
| `src/topology/lap_memory.py` | ✅ | `LapMemory` — per-account rolling deque of recent `(amount, counterparty)` for the **lapping** detector. Count-based (last `k`), NOT time-windowed, so it spans long periods cheaply (A.8 rule 1). `recurrence(acct, amount)` → `(#near-equal recent amounts, #distinct counterparties)`. Leak-safe by usage (read before `record`). |
| `src/topology/engine.py` | ✅ | `extract_features(edges, …)` streams transactions in `(timestamp, id)` order, reads each one's features from past-only state, then inserts it. Produces **13 cols**: structure `in_cycle, cycle_length, in_cycle_ge3, cycle_time_span, fan_in, fan_out, dest_in_degree, src_out_degree` + amount-derived `cycle_amount_ratio` + lapping `lap_in_recur, lap_in_payers, lap_out_recur, lap_out_payees`. Exposes **`STRUCTURE_COLS` vs `AMOUNT_DERIVED_COLS`** (the split the honest ablation needs — A.4d). `build_topology(name)` → `features_topology.csv` + `topology_audit.json` (incl. `among_cycles` + `lapping_separation`). `partition_col` resets BOTH the graph and lapping memories per partition. CLI: `python -m topology.engine <dataset>`. |
| `src/topology/leakage_test.py` | ✅ | Automated no-look-ahead guard: **truncation invariance** + **future-corruption invariance** on real data. **NaN-aware** (`equal_nan=True`). Passes on banksim + ibm with all 13 features. `python -m topology.leakage_test <dataset> [sample]`; exits non-zero on failure. |
| `src/features/build.py` | ✅ | `build_features(name)` assembles the model table: leakage-safe ORDINARY features (`log_amount`; **expanding** past-only per-account stats — `src_count_prior`, `src_amt_mean_prior`, `amount_zscore_src`, `time_since_prev_src`, `dest_count_prior`; static numeric account attrs; one-hot low-card edge categoricals) + the **13 TOPOLOGY cols** (picked up generically by name). Manifest now splits topology into **`topology_structure_cols` vs `topology_amount_cols`** (so the ablation can run a clean structure-only probe). Drops zero-variance / label-derived / id cols. Writes `features_model.{parquet,csv}` + `features_manifest.json`. Uses `time_since_prev` (past), never `time_to_next` (the old #1 leak). |
| `src/modeling/metrics.py` | ✅ | `evaluate` (PR-AUC primary, ROC-AUC, precision/recall/F1 at frozen threshold, precision@k/recall@k), `tune_threshold` (max-F1 on validation), `precision_recall_at_k`. |
| `src/modeling/harness.py` | ✅ | `time_split` (chronological; global quantile OR partition-aware within-run for SAP), `train_and_evaluate(df, feature_cols, …)` — class-weighted XGBoost (`scale_pos_weight`, the single imbalance mechanism), early-stop on val PR-AUC, threshold tuned on val & frozen, persists model+threshold+features to `artifacts/`. |
| `experiments/ablation.py` | ✅ | `run_ablation(name)` fits **7 models** (baseline, +topology, **+structure**, no-amount ×3, topology-only). Reports the full-model marginal AND the **structure-only** marginal, plus **two** amount-blind lifts: all-topology (contaminated) and **structure-only (the clean test)** — the distinction that matters per A.4d. Writes `results/<name>/ablation.json`. |
| `experiments/augmentation.py` | ✅ | **The synthetic-augmentation experiment** (3 arms × N seeds on a shared 6-ordinary+13-topology feature space, time features unit-normalised to days): real-only vs real+synth (synth rows appended to TRAIN only; val/test always real & later) vs synth-only zero-shot. **Verdict 2026-07-14: naive pooling HURTS everywhere** (banksim Δ −0.106±0.001; ibm −0.005; sap −0.107 @25 test frauds) — domain shift; **but synth-only transfers zero-shot to banksim at 0.724 PR-AUC** (vs 0.867 real-trained, 0.012 base). Policy: no pooled tree training; synth's training role = pretrain→fine-tune for the neural challenger. `results/<ds>/augmentation.json`. |
| `src/features/load.py` | ✅ | **Shared model-table loader** — the single place features_model meets the TGN embeddings: str ids, SAP dup-id drop (both sides), strict 1:1 merge, stable time sort; `split_partition(df)` is the one source of the SAP `run_id` partition series (post-merge). Used by modern/final/score/alerts. |
| `src/modeling/objectives.py` | ✅ | Alpha-free focal-loss custom XGBoost objective (closed-form grad, numeric hessian, γ=0 ≡ logloss). Alpha-free deliberately: alpha-balanced focal = focal + class weights = rule-1 violation. |
| `src/modeling/tgn.py` | ✅ | CPU TGN embedder — 32-dim GRU memory/account, Time2Vec log-gap encoding, self-supervised link prediction. Weights fit on TRAIN period only, frozen replay over val/test; **zero-lookahead** (memory read before update), **label-free**, **amount-blind** (A.4d lesson). → `features_tgn.parquet` (65 cols: `tgn_s0..31`, `tgn_d0..31`, `tgn_edge_expectedness`) + manifest. Cached; `--force` to rebuild. |
| `src/modeling/hpo.py` | ✅ | Light seeded random search (~20 configs) over XGBoost params; **config #0 is always the locked defaults**; selection on **val PR-AUC only** (test recorded for audit, never consulted); **guard: skipped when val frauds < 20** (fires on SAP, 19 val frauds). |
| `src/modeling/score.py` | ✅ | Inference entry point: `load_bundle` (bundle v2 + Booster) + `score_frame`/`score_dataset`. Uniform margin→sigmoid scoring (a reloaded focal model must NEVER use predict_proba) and **`iteration_range` from `best_iteration`** (a reloaded Booster otherwise predicts with all 500 trees — silently different scores; caught by tests/test_bundle_roundtrip.py). `--verify` = round-trip gate. |
| `src/modeling/explain.py` | ✅ | **Exact TreeSHAP via XGBoost native `pred_contribs`** (no shap dep; works with the focal objective; same iteration_range). `global_importance` (mean abs-SHAP) replaces gain importances in final reporting; `top_drivers` per alert; optional beeswarm plot behind `pip install -e .[explain]`. |
| `src/modeling/alerts.py` | ✅ | **The audit-alert generator (Build Step 5 layer 1)**: top-k test scores → TreeSHAP drivers (tagged ordinary/topology/tgn + auditor gloss) + graph evidence from `topology/paths.py` → `results/<ds>/alerts/alerts.{json,txt}`. Cross-checks reconstructed cycle length against the stored `cycle_length` (falls back to `path_nodes: null` on mismatch — never presents unverified evidence). Zero Neo4j dependency. |
| `src/topology/paths.py` | ✅ | Evidence reconstruction by **replaying** the as-of stream (same ordering/window/partition resets/factorization as the engine) and capturing, for flagged txns only, the actual cycle hops (`WindowGraph.cycle_path` — additive method, same BFS as `cycle_features`; property-tested vs 5k+ cycles) and the fan-in senders. Engine untouched (leakage test still green). |
| `src/graph/` | ✅ | **Neo4j demo layer (Build Step 5 layer 2), visualization ONLY**: `db` (env-config driver, graceful `ping()` + setup hint), `load` (constraints + UNWIND-batched alert-subgraph load; every edge carries `seq` = stream position so Cypher "past only" == engine semantics incl. same-day tie-breaks; `--full` for whole graph), `queries` (as-of cycle/fan-in Cypher), `demo` (per-alert Cypher path vs recorded evidence → PASS/FAIL gate). See `docs/NEO4J_DEMO.md`. |
| `experiments/modern.py` | ✅ | 6 arms × 3 seeds (A/B × cw/focal, C=+TGN, D=both) → `results/<ds>/modern.json`. Now loads via `features/load.py`. |
| `experiments/final.py` | ✅ | **The FINAL model** (arm D promoted): fixed feature set ordinary+topology+TGN; per mechanism (cw, focal) HPO → 3-seed fit; **winner selected on multi-seed mean val PR-AUC** (both arms' test published); champion copied to `artifacts/<ds>/final/` with a `selection` block; TreeSHAP global top-20 on a 50k val sample → `results/<ds>/final.json`. ASCII-only console. |
| `experiments/report_final.py` | ✅ | Consolidated table (baseline/+topology/+TGN rows from modern.json, champion from final.json; auto-footnoted caveats) → `results/final_table.md`. Re-runs nothing. |
| `experiments/run_dataset.py` | ✅ | One-command idempotent driver: etl → topology → **leakage (hard gate)** → features → tgn → final; `--steps`, `--force`. |
| `tests/` | ✅ | pytest suite: cycle_path↔cycle_features property test; **bundle round-trip for BOTH mechanisms** (catches the iteration_range and focal-predict_proba failure modes); HPO determinism/config-0/guard. `pip install -e .[test]`. |
| `src/synth/` (base, world, normal, fraud, generate, calibrate, validate) | ✅ | **The synthetic ERP generator** (recorded decision 2026-07-13 pulled it forward from Phase 6). Agent-based, behavior-driven economy: 40 companies / 1.2k vendors / ~2.9k employees / ~34k customers, 8 benign flows + **5 fraud typologies written as goal+evasion behaviors — NEVER detector patterns** (imports nothing from `topology`). `calibrate` measures the real datasets (anchors params); `generate` writes raw CSVs (IBM-AML-layout) + provenance (scenarios.json, manifest with **SHA-256; rerun = byte-identical**); `validate` runs the realism battery vs the real reference. Config: `config/synthetic.yaml` (seed 20260713). Full doc: `docs/SYNTHETIC_DATASET.md`. **Usage policy: training/augmentation only — the thesis is only ever proven on real data.** |
| `pyproject.toml` | ✅ | Pinned deps: pandas, numpy, scikit-learn, xgboost, lightgbm, neo4j, pyyaml, matplotlib, seaborn, plotly, **torch** (TGN is core). Optional extras: `[explain]` (shap, plots only), `[test]` (pytest). |

**Topology output contract** (`features_topology.csv`, one row per transaction, keyed
by `transaction_id`, topology columns ONLY — kept separable so the ablation can
switch them on/off): `in_cycle` (1 if this txn *closes* a directed cycle within the
window — credit-the-closer), `cycle_length` (edges of the shortest such cycle, else
0), `in_cycle_ge3` (1 if that shortest cycle is ≥3 hops — excludes self-loops +
reciprocal pairs), `cycle_amount_ratio` (min/max of the amounts around the loop incl.
the closing edge; ≈1 ⇒ amounts conserved ⇒ laundering/wash; **NaN** where no cycle
closes), `cycle_time_span` (closing-ts − earliest-loop-edge-ts; small ⇒ tight; **NaN**
where no cycle), `fan_in` / `fan_out` (distinct past senders to dest / receivers from
source, in window), `dest_in_degree` / `src_out_degree` (past edge counts with
multiplicity), and the **lapping** cols `lap_in_recur` / `lap_in_payers` (count and
distinct-payer count of the dest's recent INCOMING amounts within 1% of this amount)
and `lap_out_recur` / `lap_out_payees` (same for the source's OUTGOING amounts). All
strictly as-of (timestamp ≤ own, id-order tie-break). **Two families:** pure
*structure* (`STRUCTURE_COLS`: the cycle-membership/length/ge3/time + fan/degree) vs
*amount-derived* (`AMOUNT_DERIVED_COLS`: `cycle_amount_ratio` + the 4 `lap_*`). Only
structure is valid in the amount-blind probe (A.4d). `topology_audit.json` carries
params + ground-truth blocks (`among_cycles`, `lapping_separation`).

**Canonical ETL output contract** (identical for every dataset, so everything
downstream is dataset-agnostic):
- `edges_transactions.csv` — one row per **prediction unit** (a transaction /
  posting line). Core columns: `transaction_id, source_account, dest_account,
  amount, timestamp, label` (+ dataset extras such as `tx_type`, `alert_type`,
  `run_id`). Sorted by `timestamp`.
- `nodes_accounts.csv` — one row per node: `account_id` (+ attributes / `node_kind`).
- `audit.json` — row & account counts, observed vs expected fraud rate, namespace
  overlap, timestamp range, fraud-typology counts.

## A.4b — Ablation findings (SMOKE TEST, 2026-06-29) — read this before modeling work

First leakage-free ablation, 6 topology features, single seed, XGBoost. **Directional,
not final** — re-run as detectors improve. The decisive question (DESIGN §9): does
topology beat a strong tabular baseline, no leakage?

| Dataset | baseline PR-AUC | +topology | marginal | topology-only | read |
|---|--:|--:|--:|--:|---|
| **ibm_aml** | 0.990 | 0.998 | +0.008 | 0.097 | baseline **SATURATED by amount** → no headroom; topology redundant |
| **banksim** | 0.833 | **0.932** | **+0.099 (+11.9%)** | 0.429 | **topology HELPS** — via fan-in / `dest_in_degree`; cycles correctly 0 |
| **sap_wurzburg** | 0.155 | 0.073 | −0.082 | 0.128 | **inconclusive** — only 25 test frauds, ~31-node graph; negative is noise |

**What this established (all verified, honest):**
1. **The pipeline is honest — IBM's 0.99 is NOT our leak.** It's an AMLSim data
   artifact: fraud has giveaway amounts (`log_amount` univariate ROC 0.91) and arrives
   in same-day bursts (`time_since_prev_src` ROC 0.87). Both are strictly past-only.
   `INIT_BALANCE` is *not* a fraud proxy. So IBM is tabular-trivial, which **refutes the
   old A.5 premise that "IBM AML is the decisive topology testbed"** — it has no headroom.
2. **Topology carries real, independent signal** (topology-only beats chance ~30–70×;
   on IBM, removing amount makes topology lift PR-AUC 0.030→0.143, +386% rel).
3. **The working topology features are DENSITY (fan-in / `dest_in_degree`), NOT cycles.**
   Cycle features scored ~0 importance everywhere they could fire — reproducing the old
   version's "topology=0 importance" pattern, but now EXPLAINED: cycle *membership* is
   non-discriminative (19.5% benign background on IBM — too common). The fix is more
   *discriminative* cycle features (tightness, amount-conservation, rarity), not more
   shape-detection.
4. **Topology's marginal value is conditional**: it appears where the baseline has
   headroom AND fraud has a topological signature the tabular features miss (banksim),
   not where amount already saturates (ibm). Real-world ERP fraud hides amounts, so
   synthetic data likely *understates* topology's value.

Adopted protocol: every ablation reports the **amount-blind probe** + **topology-only**
alongside the marginal lift (a marginal test is meaningless when the baseline saturates).

## A.4c — Discriminative cycle features (2026-06-29) — the verdict on cycles

A.4b found cycle *membership* adds ~0 because it's too common (19.5% benign). The
hypothesis: cycles fail because the feature is non-discriminative, and **better** cycle
features (amount-conservation, tightness, ≥3-hop) would earn their keep. We built them
(leakage-safe, leakage-test green) and tested cleanly. **Verdict: the hypothesis is
half-right — the features ARE now discriminative, but they're REDUNDANT with density.**

*IBM is the only testbed for this — banksim/sap are bipartite (accounts are sinks → no
cycles), paysim is a near-forest; all three have `in_cycle=0`, so cycle features there
are correctly all-NaN/0 and the ablation is unchanged (no regression).*

**Evidence the features became discriminative (real signal):**
- Audit `among_cycles` (only rows that closed a cycle): cycle-frauds conserve amount
  **1.9×** more than benign cycles (`cycle_amount_ratio` 0.279 vs 0.150) and are ≥3-hop
  loops more often (75% vs 55%). (Tightness does NOT separate — 4.79 vs 4.60 — because
  IBM time is integer **days**, too coarse.)
- Amount-blind, **NEW cycle features alone** lift PR-AUC **0.093 → 0.157** (vs the old
  raw `in_cycle` which was useless). So they carry genuine independent signal.

**Evidence they're redundant with density (clean within-run probe, same split+seed,
XGBoost verified deterministic — toggling ONLY the 3 new features):**

| amount-blind feature set | PR-AUC |
|---|--:|
| no_amount (no topology) | 0.0932 |
| no_amount + OLD density (`fan_in`/degrees + crude cycle) | 0.1859 |
| no_amount + OLD + **NEW cycles** | 0.1872 |
| no_amount + **NEW cycles only** | 0.1566 |

→ **marginal value of the discriminative cycle features = +0.0013 (amount-blind),
−0.0003 (full, amount-saturated).** Density alone (0.186) ≈ density+cycles (0.187).

**What this means (honest, for the write-up).** On IBM AML the topological fraud signal
is **low-dimensional**: node degree / fan-in already captures it, and explicit
loop-shape detection — *even when made discriminative and leakage-free* — adds nothing
on top. This **refines, not contradicts** A.4b: cycles aren't dead because they're
non-discriminative (we fixed that); they're redundant because density covers the same
dense laundering subgraph. Caveat: AMLSim's frauds are dense by construction; real ERP
fraud that hides amounts and stays sparse may not let density substitute for cycles —
but we have no labelled data to show that, so we don't claim it.

**Cycles still earn their keep for EXPLAINABILITY (Step 5).** "Closes a 3-hop loop
returning 95% of the amount in 2 days" is a far better auditor-facing reason than "high
in-degree," even when the two are predictively equivalent. The features stay in the engine.

## A.4d — Lapping + the structure-only verdict (2026-06-29) — READ THIS for the topology bottom line

Built a **lapping** detector (per-account rolling memory of near-equal amounts +
distinct-counterparty counts; 4 `lap_*` features) and, in doing so, found and fixed a
flaw in our own ablation. This is the consolidated topology verdict.

**1. Lapping is an AMOUNT feature, not topology (verified, kept but reclassified).**
On IBM the `lap_*` features looked spectacular — amount-blind PR-AUC jumped 0.31→0.87,
`lap_out_recur`/`lap_out_payees` took 0.54/0.42 importance, full model hit 1.0000. All a
mirage. The lapping features are computed from *amounts* (recurrence of near-equal
values), so they re-introduce the amount signal the "amount-blind" probe removes. Proof
(IBM, same split/seed): `no_amount`+lapping = **0.838**, which sits right among the plain
amount features (`no_amount`+`amount_zscore_src` = 0.764, `no_amount`+`log_amount` =
0.989). A single amount column beats all 4 lapping features. In the realistic FULL model
lapping adds **+0.002** on IBM and **+0.000** on banksim. The IBM separation is also an
AMLSim artifact (normal accounts are simulated as periodic/recurring → high recurrence;
fraud isn't → ~0), the same giveaway family as the amount signal (A.4b). Kept the code
(leak-safe; lapping is a named typology that could matter on a real lapping dataset), but
tagged `lap_*` as `AMOUNT_DERIVED_COLS`.

**2. The methodology fix.** The amount-blind probe (A.4b) silently assumed all topology
is amount-free. It isn't (`cycle_amount_ratio` + `lap_*` are amount-derived). The ablation
now reports a **structure-only** probe — pure graph shape (cycle membership/length/ge3/
time + fan/degree), no amounts — which is the *only* honest test of "does graph STRUCTURE
beat a tabular baseline."

**3. The definitive verdict (structure-only, leakage-free):**

| dataset | structure marginal (FULL) | structure lift (AMOUNT-BLIND, clean) | all-topology amount-blind (dirty) | read |
|---|--:|--:|--:|---|
| **banksim** | **+0.097 (+11.7%)** | **+0.190** | +0.188 | **real structural win** (density/fan-in); clean==dirty ⇒ amount-derived adds nothing |
| **ibm_aml** | +0.008 (saturated) | +0.090 | +0.774 | modest real structure signal; the +0.774 was ~88% amount-derived illusion |
| **sap_wurzburg** | ~0 | +0.015 | +0.006 | inconclusive (25 test frauds, ~31-node graph) |

**Bottom line for the write-up.** *Graph structure adds real, leakage-free predictive
value — but conditionally and modestly.* It wins where the baseline has headroom AND
fraud has a structural signature the tabular features miss (banksim, via simple density:
`fan_in`/`dest_in_degree`, +11.7% PR-AUC). On amount-saturated IBM it carries a modest
independent signal (amount-blind +0.09) but is dominated by amount. **The fancy detectors
do not earn their keep predictively: cycle-shape is redundant with density (A.4c); lapping
is amount in disguise. Plain density is the topology signal.** (Real-world ERP fraud that
hides amounts and stays sparse may favour structure more — but we have no labelled data to
claim that, so we don't.) This is the honest answer to DESIGN §9, reported either way.

## A.4e — The FINAL model & consolidated results (2026-08-26) — the finished product

**The final model (recorded decision, user session 2026-08-26): TGN embeddings →
XGBoost head** — arm D of the modernization experiment promoted to the single
production model. Fixed feature set = ordinary + hand-crafted topology + 65 TGN
embedding cols. Per dataset, BOTH imbalance mechanisms (class weights, focal —
each alone, rule 1) get a light HPO pass (20 seeded random configs, config #0 =
locked defaults, selected on val PR-AUC only, **skipped when val frauds < 20** —
fires on SAP) and a 3-seed fit; the **champion is selected on multi-seed mean
VALIDATION PR-AUC** (never test) and persisted to `artifacts/<ds>/final/` as a
self-describing bundle v2 (features + families, threshold, mechanism, score_fn,
xgb_params, best_iteration, TGN provenance incl. parquet SHA-256, selection
record). Reload/score via `python -m modeling.score <ds> --artifact final
--split test --verify`.

**Consolidated test-period results (mean ± std over seeds 42/43/44; full table
in `results/final_table.md`, per-dataset detail in `results/<ds>/final.json`):**

| dataset | baseline | +topology | +TGN | **FINAL champion** | champion mechanism |
|---|--:|--:|--:|--:|---|
| banksim | 0.787 ±0.070 | 0.932 ±0.002 | 0.920 ±0.001 | **0.9364 ±0.0015** (p@100 1.00) | focal(γ=1.0), HPO |
| ibm_aml | 0.992 ±0.003 | 1.000 | 0.987 ±0.010 | **1.0000** (saturated) | class_weight (tie), HPO |
| sap_wurzburg | 0.158 ±0.013 | 0.072 ±0.010 | 0.059 ±0.024 | 0.1557 ±0.0717 | focal(γ=2.0), HPO skipped |
| synth_erp | 0.248 ±0.060 | 0.457 ±0.155 | 0.697 ±0.000 | **0.7784 ±0.0053** (p@100 0.99) | focal(γ=1.0), HPO |

Readings (honest): the champion beats the best recorded arm wherever there is
headroom (banksim +0.005 over B_cw; synth +0.036 over D_both — HPO's doing);
IBM is amount-saturated (margins uninformative — the amount-blind probes in
A.4b/A.4d are the informative IBM story); SAP stays **inconclusive** (25 test
frauds, selection flagged `reliable: false`, HPO guard fired). Focal won
selection on 3 of 4 datasets; both arms' test metrics are published in
final.json (transparency — e.g. on banksim class_weight actually tested 0.9395
vs focal's 0.9364; selection stays honestly on validation). synth_erp remains
sanity/demo only, never thesis evidence. `tgn_edge_expectedness` is the #2
global SHAP feature on synth_erp (learned structure earns its keep on
behavior-driven fraud); on banksim the top SHAP features are the A.4d density
story (`fan_in`, `dest_in_degree`) plus TGN components.

**Audit alerts (Build Step 5 layer 1 — DONE).** `python -m modeling.alerts <ds>`
→ `results/<ds>/alerts/alerts.{json,txt}`: top-k test alerts with exact TreeSHAP
drivers (family-tagged `ordinary` / `topology` / `topology-amount-derived` /
`tgn`, auditor glosses) + actual graph evidence (cycle hops from the as-of
replay, or fan-in senders). Results: ibm 20/20 true fraud in top-20 (8 verified
cycle paths, 9 fan-ins); banksim 15/15 (all fan-in — one merchant collecting
from 47-63 senders); synth 20/20 (6 cycles, 13 fan-ins); sap 2/10 (weak signal,
reported honestly). **Neo4j demo (layer 2 — code DONE, live run pending a local
instance):** `graph/load` + `graph/demo` self-verify every cycle alert's Cypher
path against the recorded evidence; see `docs/NEO4J_DEMO.md`.

**Verification record (all gates green, 2026-08-26):** leakage test passes
banksim + ibm (the additive `cycle_path` changed nothing); banksim ablation
re-run **bit-identical** to the recorded ablation.json (harness changes fully
backward-compatible); bundle round-trips verified on all 4 datasets (this gate
caught a real bug: a reloaded Booster predicts with all 500 trees unless
`iteration_range=(0, best_iteration+1)` is passed — fixed in score/explain/
alerts); alert-JSON invariants pass on both cycle datasets (loops close, lengths
match stored features, hops as-of & in-window); pytest suite (6 tests) green.

## A.5 — Datasets: exact verified state (Build Step 1 ✅)

| dataset | kind | txns (edges) | nodes | frauds | rate | namespace overlap | structure |
|---|---|--:|--:|--:|--:|--:|---|
| `ibm_aml` | transfer | 1,323,234 | 10,000 | 1,719 | 0.13% | **0.993** | dense, cycle-rich — the decisive testbed |
| `banksim` | bipartite | 594,643 | 4,162 | 7,200 | 1.21% | 0.000 | pure bipartite control |
| `paysim` | transfer | 6,362,620 | 9,073,900 | 8,213 | 0.13% | 0.0002 | sparse near-forest, at scale |
| `sap_wurzburg` | erp_ledger | 200,629 | 59,883 | 248 | 0.12% | 0.000 | ERP doc↔G/L-account bipartite |
| `synth_erp` | transfer (synthetic) | 1,148,503 | 39,393 | 5,609 | 0.49% | 0.941 | our generated ERP economy — **training/augmentation ONLY** |

All four modeled datasets (not paysim) additionally carry `features_tgn.parquet`
(+ manifest; dim=32, seed 42) under `data/processed/<ds>/`, and
`artifacts/<ds>/{final, final_class_weight, final_focal}/` bundles (A.4e).
paysim remains stalled after the topology stage (no features/tgn/model) — see
A.8(c).

Per-dataset specifics a new session must know:
- **ibm_aml** — schema `TX_ID/SENDER_ACCOUNT_ID/RECEIVER_ACCOUNT_ID/TX_AMOUNT/
  TIMESTAMP`(int day 0–199)`/TX_TYPE/IS_FRAUD`. Bonus files: `accounts.csv` (node
  attributes) and `alerts.csv` (`ALERT_TYPE` typology — **eval-only, never a
  feature**). Every fraud is a labelled shape: **936 cycles + 783 fan-ins** — so the
  detectors can be checked against ground truth here.
- **banksim** — values are single-quote-wrapped (`quote_char: "'"`); customer→merchant;
  `step` = day. Pure bipartite (no cycles possible) → the control.
- **paysim** — `nameOrig→nameDest`, `step` = hour, `type` carried as `tx_type`; label
  `isFraud` (**ignore** the broken `isFlaggedFraud`). Near-forest (overlap 0.0002).
- **synth_erp** — OUR generated dataset (`src/synth/`, seed 20260713; regenerate
  with `python -m synth.generate` — byte-identical, SHA-256 in the raw folder's
  `generation_manifest.json`). Timestamps are integer **seconds** over 365 days;
  raw layout mirrors IBM AML (transactions/accounts/alerts CSVs). Fraud = 5
  behavior-generated typologies (`laundering_cycle` 1,442, `mule_fanin` 2,327,
  `lapping` 760, `invoice_kickback` 625, `larceny` 455) carried as `alert_type`
  (eval-only) + per-scenario `alert_id`. Accounts carry `role` (provenance,
  string→never a feature) and `creation_day` (numeric, legitimate). Survived an
  **adversarial review** (Opus): 2 critical tabular leaks found & fixed
  (receiver-side creation_day rule at precision 1.0 → 0.03; transfer
  concentration 18×→6×); `synth.validate` now runs a **tabular-leak probe gate**
  (shipped build: leak_flag FALSE, worst rule precision 0.093). Leakage test
  PASSES; realism battery green (Benford MAD 0.0047 — best in roster; in-band
  amount ROC 0.49 = camouflaged). Sanity ablation: baseline 0.163, +structure
  +0.403 (structure carries the signal — sanity only, NOT thesis evidence).
  **Training/augmentation only; never cite as proof of DESIGN §9.** Full
  datasheet: `docs/SYNTHETIC_DATASET.md`.
- **sap_wurzburg** — real SAP double-entry postings, **German column headers**, 5
  files (`fraud_1..3` + `normal_1..2`; note `normal_2` actually contains frauds).
  **No source/dest columns** → edges are derived: one per posting line,
  `DOC:<run>:<Belegnummer>` → `GL:<Hauptbuchkonto>`. `amount` = `Betrag Hauswaehr`;
  `label` = (`Label != "NonFraud"`); fraud typologies (Larceny, Invoice Kickback,
  Corporate Injury, Discounts, Scrap) carried as `alert_type` (eval-only).
  **Timestamps are time-only**, so the canonical `timestamp` is synthetic:
  `run_index * 1e6 + seconds-since-midnight`, and a `run_id` column is carried.
  **Downstream MUST partition by `run_id` and never look across runs.** The entity
  graph is tiny (~31 G/L accounts) → expect a weak topology signal (report honestly).

## A.6 — The non-negotiable methodology rules (restate precisely; never regress)

1. **One imbalance mechanism per experiment** — resampling **or** class weights,
   never both. **Default = class weights** (SMOTE interpolates non-physical
   topology vectors). Record which was used.
2. **Tune the decision threshold on validation**, freeze it before the test set —
   **never** report metrics at a fixed 0.5.
3. **Time-aware CV** — train on earlier periods, test on later. **Never** shuffle
   folds (that leaks the future).
4. **No look-ahead through the graph** — a transaction's features at time T use only
   data with `timestamp ≤ T` (as-of / streaming). **No whole-dataset normalization**
   (every stat expanding/rolling over the past). Attribute a structure's signal to
   the transaction that **completes** it. An automated **leakage test** must guard
   this (scramble the future → past features must not change).
5. **PR-AUC / average precision is primary AND the model-selection metric**; also
   report **precision@k / recall@k**. ROC-AUC may be reported but not relied on.
6. **Persist** every model with its fitted scaler and frozen threshold.

## A.7 — The `reference/` folder

`reference/shadowGraphs_old/` is the earlier version (a flat `step1…step9` script
pile over 5 datasets). **Read-only.** **DO** mine it for proven Cypher queries and
hard-won ETL fixes. **DO NOT** copy its training/evaluation code — it commits exactly
the sins above (SMOTE + class weights together, fixed 0.5 threshold, shuffled CV).
**Do not trust its reported metrics** (leakage-contaminated; its own feature-
importance shows the topology detectors scored 0.0 — the signal was `total_amount`).

## A.8 — What's next / open items

- **Build Step 2 (topology engine) — first increment ✅ DONE** (cycle + fan-in +
  degrees + automated leakage test). Topology features now built for **all 4
  datasets** (incl. paysim 6.36M rows: in_cycle=0 near-forest, fan-in only).
- **Build Step 3 (modeling harness) + Step 4 (ablation) — pulled forward & DONE as a
  smoke test.** `features/build.py`, `modeling/{metrics,harness}.py`,
  `experiments/ablation.py` built; ran the spectrum (ibm/banksim/sap). **Findings in
  A.4b** — headline: pipeline is honest; topology HELPS on banksim (+11.9% PR-AUC) via
  density, is redundant on amount-saturated ibm, inconclusive on sap; the *cycle*
  features add ~0 (membership too common) while *density* (fan-in/degree) does the work.
- **Discriminative cycle features ✅ DONE — verdict A.4c.** Redundant with density on IBM
  (+0.001). Committed `805a911`.
- **Lapping detector ✅ DONE — verdict A.4d.** Built `lap_*` (4 features). Turned out to be
  an **amount-derived feature, not topology** (verified: amount-blind it sits among plain
  amount features; full-model marginal +0.002 IBM / +0.000 banksim). Kept + tagged
  `AMOUNT_DERIVED_COLS`. Prompted the **structure-only ablation probe** (the honest test).
- **Topology investigation effectively CLOSED — verdict A.4d.** Across all detectors, the
  only clean structural win is **banksim density (+11.7%)**; cycles redundant, lapping is
  amount. Plain `fan_in`/`dest_in_degree` is the topology signal. The core DESIGN §9
  question is answered (structure helps conditionally + modestly, leakage-free).
- **Synthetic ERP dataset (`synth_erp` v1) ✅ DONE (recorded decision 2026-07-13,
  pulled forward from Phase 6).** Behavior-driven generator + calibration +
  realism battery + leakage test (green) + sanity ablation. See `docs/
  SYNTHETIC_DATASET.md` + A.4/A.5 rows. **Follow-on augmentation experiment ✅ DONE
  (2026-07-14, `experiments/augmentation.py`) — honest NEGATIVE result:** naive
  pooled augmentation hurts the XGBoost champion on all three real datasets
  (banksim −0.106 paired ±0.001; ibm −0.005; sap −0.107 but only 25 test frauds);
  **zero-shot transfer is the positive nugget** — synth-only scores 0.724 PR-AUC on
  real banksim (vs 0.867 real-trained, 0.012 base rate), nil on ibm (whose fraud
  signature is inverted: tiny amounts, day-bursts). Refined usage policy: synth's
  training value is pretrain→fine-tune for the data-hungry FT-Transformer
  challenger (MODERNIZATION_REPORT), never naive pooling with trees.
- **Finalization session ✅ DONE (2026-08-26) — see A.4e.** Final TGN→XGBoost
  champion (HPO + per-dataset mechanism selection) trained/persisted/verified for
  all 4 datasets; TreeSHAP audit alerts with verified graph evidence; Neo4j demo
  layer coded + self-verifying; run_dataset driver; pytest suite; all gates green.
- **Remaining (future work, none blocks the deliverable):**
  - (a) **Live Neo4j demo run** — code done; needs a local Neo4j instance +
    `NEO4J_PASSWORD`, then `python -m graph.load ibm_aml` and `python -m graph.demo
    ibm_aml` (self-verifies every cycle alert). `docs/NEO4J_DEMO.md`.
  - (b) **Commits** — the finalization workstream is uncommitted (user gate);
    planned 9 source-only commits are listed in the session plan.
  - (c) **PaySim runs** to complete the 4-dataset spectrum (6.36M rows; weak
    topology expected; completeness, not signal). `run_dataset.py paysim` now does
    the whole chain (features/tgn/final never built there).
  - (d) **FT-Transformer challenger** (MODERNIZATION_REPORT §6, incl. synth_erp
    pretrain→fine-tune per the 07-14 policy) — deliberately dropped from the
    finalization scope.
  - (e) **TGN weight persistence for streaming inference** — the final bundle
    references the cached embedding parquet (batch lookup); scoring a genuinely
    NEW transaction stream would need `tgn.py` to persist `state_dict` + node
    factorization and roll memory forward live.
  - (f) **More detectors** (rapid-chain, as-of centrality) — A.4c/A.4d say
    density-correlated, low payoff.
- **Slow-fraud design rules (decided 2026-06-29, from the windowing discussion).**
  The trailing window bounds only the *graph-shape* search, NOT the system's whole
  memory — so long-lasting fraud is handled deliberately, not ignored:
  1. **Lapping uses cheap, long per-account memory** (a small rolling history of an
     account's recent amounts), NOT the graph window — so it can span months at
     near-zero cost. Slow per-account drift lives in expanding/rolling scalars, not
     the windowed graph.
  2. **Multi-scale windows.** Compute the shape features at several time-scales at
     once (e.g. short + long), each its own column, so the model can catch fast
     layering *and* slow loops, learning which scale matters.
  3. **Known limitation (state it honestly in write-ups).** A *slow + multi-hop +
     cyclic* launder (loop hops months apart) is the one case the graph window can
     miss; detecting that structure needs a long, expensive window. On our actual
     datasets the labelled frauds are the fast kind (IBM: 93% caught at 7 days), so
     this is a generalisation/scope boundary, not a flaw in the current study.
- Possible tuning when modeling starts: the trailing **window** (currently 7 days
  for IBM/BankSim) trades benign-cycle noise vs. recall — explore in Step 3/4, do
  not over-fit to ground truth now.
- Then Step 3 (modeling harness), Step 4 (the ablation), Step 5 (explainability).

## A.9 — Changelog (append one dated entry per step)

- **2026-06-24** — *Build Step 0 + architecture lock.* Audited the old version;
  confirmed its thesis is unsupported (topology features scored 0.0 importance) and
  all its metrics are leakage-contaminated. Locked the architecture (Sections 4 & 14).
- **2026-06-24 → 06-28** — *Build Step 1, Tier-1 ETL.* Built `etl/build.py` +
  `common/config.py`; ran `ibm_aml` (unified-namespace fix verified — 99.3% overlap;
  frauds = 936 cycle + 783 fan-in) and `banksim` (bipartite control, overlap 0.0).
- **2026-06-29** — *Build Step 1 completed, Tier-2 ETL.* Added `paysim` (clean
  `transfer` fit, 6.36M txns, sparse near-forest overlap 0.0002) and `sap_wurzburg`
  (new `erp_ledger` kind → document↔account bipartite; extended `get_dataset` to
  resolve list-valued `raw`). **Dropped FIFAR** from Phase 1 (purely tabular, no
  counterparty graph). Corrected stale doc facts (Würzburg 49→248 frauds; PaySim
  "rich"→sparse). All 4 datasets built & verified.
- **2026-06-29** — *Repo hygiene + process rule.* Disabled AI commit attribution
  (`includeCoAuthoredBy: false`) and purged existing `Co-Authored-By: Claude`
  trailers from history (rewrite + force-push). Established the standing rule that
  **this document is updated after every step** (this Appendix A added as the
  AI-handoff layer).
- **2026-06-29** — *Adopted a `/clear`-between-steps workflow.* Made Appendix A the
  single source of truth for live state and added the **A.0 re-bootstrap procedure**
  (read A.0 → A.9 on resume, verify claims against the repo, start from A.8). Trimmed
  the user's memory status line to a pointer at Appendix A so stale memory can't
  contradict the doc after a `/clear`. Resume convention: user says **"resume"** →
  read Appendix A → continue.
- **2026-06-29** — *Build Step 2, first increment — Temporal Topology Engine.* Built
  `src/topology/{window_graph,engine,leakage_test}.py` + package API. Streaming as-of
  extractor: walk txns in `(timestamp, id)` order, read features from a past-only
  trailing-window multigraph, then insert (structurally leak-proof). Decision:
  **`≤T` with `transaction_id` tie-break** for same-day ordering (IBM time is integer
  days, ~6,600 txns/day) — keeps same-day cycles visible while staying strictly
  past-only. Ships **cycle** (credit-the-closer, bounded BFS ≤6 edges) + **fan-in/out**
  + degrees → 6 features in `features_topology.csv`. Added an automated **leakage
  test** (truncation + future-corruption invariance); passes on every dataset run.
  Added per-dataset `topology:` config + `partition_col: run_id` for SAP. Results:
  `banksim` in_cycle=0 (bipartite control ✓); `ibm_aml` cycle-alert recall **93.2%**
  (179/192 alerts), 2.03× enrichment — BUT background in_cycle rate 19.5% (115k benign
  length-2 reciprocal pairs), so raw `in_cycle` is **low-precision alone**, signal is
  in the combination (honest finding, consistent with the project's anti-hype stance);
  `sap_wurzburg` in_cycle=0 + per-run partitioning verified. IBM full run ≈ 5m33s.
  PaySim deferred (engine supports it). Remaining detectors (density/chain/lapping/
  centrality) are next.
- **2026-06-29** — *Windowing / slow-fraud design refinement.* Clarified that the
  trailing window bounds only the graph-shape search, not the whole system memory.
  Locked three rules (see A.8): lapping uses cheap long per-account memory (not the
  graph window); add multi-scale windows (short + long) so slow loops are catchable;
  and the slow + multi-hop + cyclic case is an acknowledged limitation (our datasets'
  labelled frauds are fast — IBM 93% at 7 days). Kicked off the PaySim topology run.
- **2026-06-29** — *PaySim topology built.* Ran the engine on paysim (6.36M rows,
  window=24h): in_cycle=0 (near-forest), fan-in only. All 4 datasets now have topology
  features. Engine scales.
- **2026-06-29** — *Build Step 3+4 pulled forward — modeling harness + first ablation
  (SMOKE TEST).* Built `features/build.py` (leakage-safe ordinary features: log_amount,
  expanding past-only per-account stats, one-hot edge categoricals; uses `time_since_prev`
  NOT `time_to_next`), `modeling/metrics.py` (PR-AUC primary, precision@k), `modeling/
  harness.py` (chronological + partition-aware split, class-weighted XGBoost, val-tuned
  frozen threshold, persistence), `experiments/ablation.py` (5 models incl. amount-blind
  probe + topology-only). **Ran ibm/banksim/sap — full findings in A.4b.** Headlines:
  (1) **pipeline is honest** — IBM's 0.99 baseline is an AMLSim amount-giveaway artifact,
  not our leak (verified: features past-only, INIT_BALANCE not a fraud proxy), which
  **refutes the "IBM = decisive testbed" premise** (it has no headroom); (2) **topology
  HELPS on banksim** (+0.099 PR-AUC, +11.9%) via fan-in/`dest_in_degree`; (3) **cycle
  features add ~0** everywhere (membership too common — 19.5% benign), while **density
  features do the work** → next detector effort should target *discriminative* features
  (cycle tightness / amount-conservation / multi-scale), not more shape detection;
  (4) sap inconclusive (25 test frauds). Adopted: always report amount-blind probe +
  topology-only (marginal ablation is meaningless when the baseline saturates).
  **Committed as `714cd8e`** ("Add topology engine, modeling harness, and first
  ablation") — Step 2 first increment + Steps 3–4 (smoke test) are all in that commit.
- **2026-06-29** — *Build Step 2 — discriminative cycle features (the verdict on cycles;
  full analysis in A.4c).* Extended `WindowGraph` to track each pair's most-recent
  `(amount, ts)` and replaced `shortest_cycle_len` with `cycle_features` (reconstructs the
  loop path); added 3 leakage-safe features — `cycle_amount_ratio` (amount conservation),
  `cycle_time_span` (tightness), `in_cycle_ge3` (≥3-hop loop). Made the leakage test
  NaN-aware (`equal_nan`); **it passes** on banksim + ibm. Rebuilt topology+features+
  ablation for all cycle-relevant datasets. **Result:** the features ARE now
  discriminative (IBM audit: cycle-frauds conserve amount 1.9× more, 0.279 vs 0.150;
  cycles-only amount-blind PR-AUC 0.093→0.157) but a clean within-run probe (fixed
  split+seed, XGBoost verified deterministic, toggling ONLY the 3 new features) shows they
  are **redundant with density**: +0.0013 marginal amount-blind, −0.0003 full. Refines
  A.4b — cycles aren't dead from being non-discriminative (fixed), they're redundant
  because node-degree/fan-in already captures IBM AML's dense laundering subgraph.
  banksim/sap unchanged (bipartite → no cycles → new cols all-NaN/0, no regression).
  Features kept for Step-5 explainability. **Committed as `805a911`** ("Add discriminative
  cycle features to the topology engine") — source only; docs/data/results stay local per A.3.
- **2026-06-29** — *Build Step 2 — lapping detector + structure-only ablation probe (the
  topology bottom line; full analysis in A.4d).* Built `topology/lap_memory.py` (`LapMemory`,
  per-account count-based rolling memory) + 4 `lap_*` features (recurrence of near-equal
  amounts × distinct-counterparty count, both sides). Hand-verified it separates lapping
  (distinct payers) from recurring billing (one payer); leakage test passes with all 13
  features. **Found lapping is an AMOUNT feature, not topology:** on IBM it looked huge
  (amount-blind 0.31→0.87, full model 1.0000, `lap_out_*` importance 0.54/0.42) but a probe
  showed `no_amount`+lapping (0.838) sits among plain amount features (`+log_amount` 0.989),
  and the realistic full-model marginal is +0.002 IBM / +0.000 banksim. It's an AMLSim
  artifact + re-smuggled amount. **This exposed a flaw in our own amount-blind probe** (it
  assumed topology is amount-free; `cycle_amount_ratio` + `lap_*` aren't). Fix: engine now
  declares `STRUCTURE_COLS` vs `AMOUNT_DERIVED_COLS`, the manifest carries the split, and
  the ablation runs a clean **structure-only** probe (now 7 models). **Definitive verdict
  (structure-only, leakage-free):** banksim structure +0.097 full (+11.7%) / +0.190
  amount-blind (REAL win, all density); IBM +0.008 full (saturated) / +0.090 amount-blind
  (modest, the old +0.774 was ~88% amount-derived illusion); sap inconclusive. **Topology
  investigation closed: plain density is the signal; cycles redundant, lapping is amount.**
  Lapping kept (leak-safe, named typology) tagged amount-derived. **Committed as `bfd0a69`**
  ("Add lapping detector and a structure-only ablation probe") — source only.
- **2026-07-04** — *Progress report (Word).* Generated `docs/Progress_Report.docx` — a
  reviewer-facing ~7-page report (about/why, locked architecture, dataset roster +
  A.4b/A.4d ablation results reported fully transparently, current components + rationale,
  future upgrades incl. the need for more datasets, done-vs-remaining roadmap). Local only
  (docs/ is gitignored per A.3). No code changes.
- **2026-07-10** — *Modernization assessment (report only, no code changes).* Wrote
  `MODERNIZATION_REPORT.md` (repo root): evaluated replacing XGBoost with tabular
  transformers (FT-Transformer / TabNet / SAINT / TabPFN). **Verdict: champion–challenger,
  not replacement** — literature (Grinsztajn 2022, Shwartz-Ziv 2022, McElfresh 2023) says
  transformers are competitive-at-best on this data regime, and only TreeSHAP gives exact
  attributions for the audit alerts. Recommends: (1) **multi-seed ablation (≥3 seeds) FIRST**
  — current single-seed margins (e.g. IBM +0.008) are within seed noise; (2) SHAP-based
  importances instead of gain-based `feature_importances_`; (3) an FT-Transformer challenger
  via a fitter-registry refactor of `modeling/harness.py` (`model=` param, model-agnostic
  bundle with scaler) + `modeling/nn.py` + `ablation.py --model` flag, with a pre-registered
  decision rule. SAINT/TabR rejected (inter-sample attention breaks streaming), TabPFN wrong
  scale, temporal/GNN models deferred to Build Step 6 per locked decision 7. The architecture
  stays FROZEN — adopting a transformer as primary would need a recorded decision. Fits any
  Legion 5 GPU (≥4GB; verify a Py3.14 torch wheel exists first, else side-venv on 3.12).
- **2026-07-13** — *Synthetic ERP dataset built, adversarially reviewed, and shipped
  (`synth_erp` v1).* Recorded decision (user): pull the synthetic generator forward from
  Phase 6. Built `src/synth/` (calibrate → world → normal → fraud → generate → validate)
  + `config/synthetic.yaml`: an agent-based ERP economy over 365 days (seconds
  resolution), 8 benign flows calibrated to measured real-dataset statistics
  (`results/synth_erp/calibration_reference.json`), and 5 fraud typologies written as
  goal+evasion BEHAVIORS (laundering rings w/ per-hop skim, staggered mule collection,
  A/R lapping w/ collapse, under-threshold invoice kickback, escalating larceny/expense
  fraud) — never detector patterns (`synth/` imports nothing from `topology`).
  Shipped build: **1,148,503 txns / 39,393 accounts / 5,609 fraud (0.49%) / 268
  scenarios**, byte-identical regeneration (SHA-256 in `generation_manifest.json`),
  full per-scenario provenance (`scenarios.json`). Integrated as a 5th dataset
  (`datasets.yaml: synth_erp`, IBM-AML-layout raw → standard `transfer` ETL; window
  604800s). **Independent adversarial review (Opus 4.8) upheld the circularity rule but
  found 2 CRITICAL tabular leaks** — (1) all benign money-receivers were pre-existing ⇒
  "`vendor_payment` to a mid-year account" = 100%-precision rule; (2) 76% of fraud rode
  `tx_type=transfer` (18×). Fixed behaviorally (mid-year vendor onboarding + new hires;
  3× benign P2P/intercompany; scam payments ride purchase rails; expense-fraud larceny)
  and added the reviewer's **tabular-leak probe as a permanent gate** in
  `synth.validate` — which then caught a 3rd residual leak (sale→mid-year-account,
  128 rows @ 1.0) → fixed via benign marketplace sales. Final verification ALL GREEN:
  leakage test passed; probe leak_flag FALSE (worst rule 0.093); realism battery —
  fraud rate in real range, Benford MAD 0.0047 (best in roster), repeat-pair 0.859,
  overlap 0.941, **in-band univariate amount ROC 0.49** (fraud amount-camouflaged;
  IBM's artifact class avoided); emergence checks honest (benign in-cycle 5.8%,
  laundering closers 18.5%, collector fan-in ≪ benign retail fan-in). Sanity ablation
  (NOT thesis evidence): baseline 0.163, +structure 0.567. Docs:
  `docs/SYNTHETIC_DATASET.md` (full datasheet: principles, references incl.
  PaySim/BankSim/AMLSim lineage + ACFE typologies + Datasheets-for-Datasets, pipeline,
  calibration mapping, realism comparison, review record, limitations, reproduction
  checklist). **Usage policy: training/augmentation only — DESIGN §9 is only ever
  answered on real data.** Natural next experiment: train-with vs train-without
  synth_erp augmentation, tested on real held-out periods.
- **2026-07-14** — *Augmentation experiment (the synthetic dataset's first measured
  use) — honest NEGATIVE result on pooling, positive on transfer.* Built
  `experiments/augmentation.py`: per real dataset, 3 seeds x 3 arms on the SHARED
  feature space (6 core ordinary + 13 topology; time features unit-normalised to
  days), real chronological split kept, synth rows appended to TRAIN only (val/test
  always real & strictly later), class weights per arm, threshold tuned on real val.
  **Results (paired over seeds): naive pooled augmentation HURTS everywhere** —
  banksim 0.867->0.761 (delta −0.106 ± 0.001), ibm 1.000->0.995 (−0.005 ± 0.001; the
  shared-feature baseline is already amount-saturated), sap 0.137->0.029 (−0.107 ±
  0.042, only 25 test frauds). Cause: domain shift — one tree ensemble fit jointly
  over two economies drags split thresholds toward the synthetic distributions.
  **Positive nugget: zero-shot transfer** — a model trained ONLY on synth_erp scores
  **0.724 PR-AUC on real banksim** (vs 0.867 real-trained; base rate 0.012), i.e. the
  synthetic economy teaches transferable fraud discrimination for structurally
  similar domains; transfer to ibm is nil (0.002 — its fraud signature, tiny amounts
  in day-bursts, is inverted vs ours). **Refined usage policy (recorded in
  SYNTHETIC_DATASET.md §11):** never pool synth rows into tree-model training; the
  dataset's training role is pretrain->fine-tune for the FT-Transformer challenger,
  plus per-typology stress-tests and the Step-5 demo. Also fixed a cp1252
  console-encoding crash in the experiment's pretty-printer (results JSONs were
  unaffected). Outputs: `results/{banksim,ibm_aml,sap_wurzburg}/augmentation.json`.
- **2026-07-15** — *Pushed to GitHub (NodeWatch).* Committed & pushed everything since
  `714cd8e`: `8e7ac59` (MODERNIZATION_REPORT.md), `0d72f74` (src/synth/ generator +
  config/synthetic.yaml + synth_erp registration in datasets.yaml), `0834632`
  (experiments/augmentation.py) — plus the previously-committed `805a911`/`bfd0a69`.
  Source only; docs/, data/, results/ stay local per A.3. Verified: no AI attribution
  anywhere in history (authors, committers, trailers all clean).
- **2026-08-05** — *Modernization step 1: focal loss + multi-seed + TGN challenger.*
  Decisions locked in-session (from the two literature docs in `docs/`): balancing
  stays resampling-free — class weights (default) vs an **alpha-free focal-loss custom
  XGBoost objective** (`modeling/objectives.py`; alpha-free deliberately, since
  alpha-balanced focal = focal + class weights = rule-1 violation); SMOTE/GAN
  resampling formally rejected (non-physical topology vectors; EAC-GAN paper's own
  table shows SMOTE hurting LightGBM precision 94.8→81.2). New-model direction:
  **TGN embeddings → XGBoost head** (two-stage, keeps TreeSHAP), not end-to-end GNN.
  Built: `modeling/objectives.py` (closed-form grad + numeric hessian, γ=0 ≡ logloss
  verified); `harness.py` gains `imbalance=` ("class_weight"|"focal", recorded in
  every result/bundle) and `train_and_evaluate_seeds` (mean ± std over ≥3 seeds —
  the MODERNIZATION_REPORT's #1 fix, landed before any comparison); `modeling/tgn.py`
  — lightweight CPU TGN (32-dim GRU memory per account, Time2Vec-style gap encoding,
  one-batch-truncated BPTT via the fold-previous-batch-in-graph trick), by
  construction **zero-lookahead** (embedding read pre-update), **label-free**
  (self-supervised link prediction, weights fit on train period only, frozen replay
  over val/test) and **amount-blind** (A.4d lesson: messages carry only who↔who +
  time gaps) → `features_tgn.parquet` (65 cols incl. `tgn_edge_expectedness`);
  `experiments/modern.py` — 6 arms × 3 seeds (A/B × cw/focal, C=+TGN, D=both) →
  `results/<ds>/modern.json`. Ablation.py untouched (locked centerpiece).
  **Results (test PR-AUC mean ± std):** banksim — focal fixes baseline seed-variance
  (A_cw 0.787±0.070 → A_focal 0.862±0.0001); B_cw 0.932 stays champion; TGN alone
  0.920 nearly matches hand-crafted topology; D adds nothing (+0.0003) — engineered
  ≈ learned structure there. synth_erp — **TGN beats hand-crafted topology**
  (C 0.697 vs B_cw 0.457) and **D_both 0.742 is the best model** (+0.285 over B_cw;
  TGN importance share 37%): learned temporal structure finds signal the 5 detectors
  miss on behavior-driven fraud. ibm_aml — saturated as known (B=1.000); nothing to
  learn. sap — inconclusive (25 test frauds), though focal > cw on both arms.
  Cross-dataset: focal ≥ cw on every baseline arm (+0.005…+0.169) and never worse
  than −0.006; biggest effect is variance collapse. **Data quirk found:** SAP
  `edges_transactions.csv` has 29 duplicate `transaction_id`s which cartesian-inflate
  `features_model.csv` by 58 rows via the topology merge (pre-existing, affects the
  locked ablation marginally); `modern.py` drops dup-id rows (logged) and merges
  1:1. Env: pyarrow installed (parquet now works; feature tables still CSV until
  next rebuild). Next: FT-Transformer challenger (roadmap in MODERNIZATION_REPORT
  §6, incl. synth_erp pretrain→fine-tune per the 07-14 policy), SHAP-based
  importances, and the paper-facing writeup of the 4-dataset modern table.
- **2026-08-26** — *FINALIZATION SESSION — the project is feature-complete (full
  record in A.4e; plan approved by user in-session).* Locked scope: TGN+XGBoost
  promoted to THE final model; both imbalance mechanisms run with per-dataset
  selection on validation PR-AUC; light HPO; SHAP audit alerts; Neo4j demo layer;
  consolidated writeup. Built: `features/load.py` (shared loader — single source
  of the merged table + SAP partition); harness `xgb_params` overlay +
  **bundle schema v2** (self-describing: model_type, score_fn, focal_gamma,
  feature families, xgb_params, best_iteration, TGN provenance w/ SHA-256,
  metrics, selection); `modeling/hpo.py` (20-config seeded random search,
  config#0=defaults, val-PR-AUC-only selection, **<20-val-frauds guard** — fired
  on SAP's 19); `experiments/final.py` (the champion protocol) +
  `report_final.py` (results/final_table.md); `modeling/score.py` (bundle
  round-trip inference; uniform margin→sigmoid; **iteration_range fix** — a
  reloaded Booster otherwise ignores early stopping, silently changing every
  score; caught by the new test suite); `modeling/explain.py` (exact TreeSHAP via
  native pred_contribs — no shap dep); `modeling/alerts.py` +
  `topology/paths.py` + additive `WindowGraph.cycle_path` (audit alerts: SHAP
  drivers family-tagged incl. `topology-amount-derived` per A.4d + replayed
  as-of graph evidence, cross-checked against stored cycle_length);
  `src/graph/{db,load,queries,demo}.py` (Neo4j demo — edges carry `seq` so
  Cypher "past only" == engine semantics; demo self-verifies each cycle alert;
  graceful no-instance path); `experiments/run_dataset.py` (one-command driver,
  leakage as hard gate); `tests/` (6 pytest tests). Hygiene: torch declared,
  `[explain]`/`[test]` extras, `.agents/` gitignored, module-map docstrings.
  **Results (A.4e):** banksim champion focal(γ=1) 0.9364±0.0015 (p@100 1.0);
  ibm 1.0000 (saturated, caveat); sap 0.1557±0.0717 (inconclusive, HPO guard);
  synth 0.7784±0.0053 (+0.036 over D_both via HPO; `tgn_edge_expectedness` #2
  SHAP feature). **All gates green** (leakage, bit-identical ablation re-run,
  4× bundle round-trips, alert invariants, pytest). Outstanding: commits (user
  gate), live Neo4j run (needs local instance), PaySim, FT-Transformer.
