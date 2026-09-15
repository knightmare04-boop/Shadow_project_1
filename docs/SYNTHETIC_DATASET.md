# The Synthetic ERP Dataset (`synth_erp` v1) — Design, Provenance & Validation

*The complete, presentable record of how the synthetic dataset was produced:
the principles, the generator architecture, the calibration against our real
datasets, the fraud typologies, the verification battery, and the honest
limitations. Written so a reviewer can audit — and regenerate — every byte.*

**Generator:** `src/synth/` · **Config:** `config/synthetic.yaml` · **Seed:** `20260713`
**Output:** `<raw_root>/synthetic_erp_v1/` → canonical `data/processed/synth_erp/`
**Status:** generated, ETL-verified, leakage-tested, realism-validated (this doc embeds the numbers).

---

## 1. Why this dataset exists (and what it may — and may not — be used for)

Our real datasets give us only ~1.7k–8.2k fraud examples each, and (as our
ablations A.4b–A.4d showed) two of them carry *simulator artifacts* — IBM AML's
fraud amounts are a 15× giveaway. Class weighting re-emphasizes the fraud we
have; it cannot create fraud knowledge we don't have. A synthetic dataset is
the one lever that adds **labeled fraud examples across typologies we can
control** — *if* it is built honestly.

**Usage policy (binding):**
1. **Training / augmentation / stress-testing only.** The project's scientific
   claim (topology adds value) is only ever evaluated on **real** data. We never
   claim victory on data whose structure we authored.
2. Whether synthetic training data helps real-data performance is itself a
   measurable claim — testable in the existing ablation harness (train with vs.
   without, test on real held-out periods), reported either way.
3. Ground-truth columns (`alert_type`, `alert_id`, the `role` account column)
   are **evaluation-only**, exactly like IBM AML's alerts file. The feature
   builder excludes them by construction.

## 2. The one binding design rule — the circularity trap

> If we hide the Easter eggs ourselves, finding them proves nothing.

The locked architecture (PROJECT_OVERVIEW §14.12) requires: **fraud is injected
by *behavior*, never by *detector pattern*.** Concretely, in `src/synth/`:

- Every fraud typology is written as an **agent with a goal and an evasion
  style** ("cover the receivable you stole with the next customer's payment"),
  never as "insert a shape the cycle detector fires on."
- `src/synth/` **imports nothing from `topology/`** and contains no reference
  to detector features. Graph shapes *emerge* from behavior — a launderer
  routing money through a ring happens to create a cycle; a collector paid by
  many mules happens to accumulate fan-in.
- The benign world deliberately contains the same *ingredients* fraud is made
  of (§5): benign fan-in (busy retailers), benign fan-out bursts (payroll
  batches), benign near-equal recurring amounts (subscriptions), benign
  reciprocal pairs (refunds), benign multi-hop circulation
  (company→employee→company). A sterile background where only fraud has
  structure would be the subtle version of the same trap.
- An **independent adversarial review** (a second AI reviewer instructed to
  refute the above claims file-by-file) was run on the generator code; its
  findings and the fixes are recorded in §10.

## 3. Method & references (what this design is based on)

The generator is an **agent-based simulation calibrated on real data** — the
same methodology family that produced two of our real datasets, which is the
strongest argument that the approach is scientifically citable:

1. **PaySim** — E. Lopez-Rojas, A. Elmir, S. Axelsson, *"PaySim: A financial
   mobile money simulator for fraud detection"*, EMSS 2016. Agent-based mobile
   money simulator calibrated on real transaction logs.
2. **BankSim** — E. Lopez-Rojas, S. Axelsson, *"BankSim: A bank payment
   simulation for fraud detection research"*, EMSS 2014. Same lineage.
3. **AMLSim** — T. Suzumura, H. Kanezashi et al., IBM Research (github.com/IBM/AMLSim);
   used in M. Weber et al., *"Scalable Graph Learning for Anti-Money Laundering"*
   (2018). The agent-based AML simulator behind our IBM AML dataset — including
   its known weakness (giveaway fraud amounts), which we measured (§7) and
   explicitly designed against.
4. **SAP Würzburg ERP fraud data** — the University of Würzburg ERP-simulation
   fraud dataset we use as Tier 2; its occupational-fraud typology names
   (Larceny, Invoice Kickback, …) anchor our typology choices in the ERP domain.
5. **ACFE, "Report to the Nations"** (Association of Certified Fraud Examiners,
   occupational fraud taxonomy) — the practitioner taxonomy our five typologies
   map onto (asset misappropriation: larceny, lapping, billing/kickback schemes;
   money laundering).
6. **M. Nigrini, "Benford's Law: Applications for Forensic Accounting…"** — the
   forensic-accounting realism check we apply to amounts (§8): real ledger
   amounts approximately follow Benford's first-digit law; ours do because they
   are mixtures of heavy-tailed flows, not because we target Benford.
7. **T. Gebru et al., "Datasheets for Datasets"**, CACM 2021 — the documentation
   standard this file follows (motivation, composition, collection process,
   recommended uses, limitations).

## 4. The pipeline architecture (verifiable end to end)

```
 (0) CALIBRATE                      python -m synth.calibrate
     measure the 4 REAL datasets -> results/synth_erp/calibration_reference.json
     (amount scales & tails, Benford MAD, degree/repetition/reciprocity,
      fraud rates, activity density)          [the numbers parameters cite]
                     |
 (1) WORLD           v              src/synth/world.py + config/synthetic.yaml
     the economy: 40 companies (ops/treasury/payroll rhythm, approval
     thresholds), 1,200 vendors, ~2.9k employees, ~34k customers arriving
     all year, price scales, supplier pools, favorites
                     |
 (2) NORMAL BEHAVIOR v              src/synth/normal.py     (~99.5% of events)
     sales, refunds, procurement (month-end spike), recurring bills,
     payroll batches, reimbursements, treasury sweeps, intercompany, P2P
                     |
 (3) FRAUD BEHAVIOR  v              src/synth/fraud.py      (268 scenarios)
     5 goal-driven typologies with evasion (jitter, structuring-under-
     threshold, staggering, aged shells, camouflage tx_types)
                     |
 (4) ASSEMBLE        v              src/synth/generate.py
     clip to 365 days -> time-sort -> TX_ID -> raw CSVs + provenance
     (scenarios.json, generation_manifest.json with SHA-256 hashes)
                     |
 (5) CANONICAL ETL   v              python -m etl.build synth_erp
     the SAME `transfer` path as IBM AML (datasets.yaml `synth_erp`)
     -> edges_transactions.csv / nodes_accounts.csv / audit.json
                     |
 (6) VERIFY          v
     topology engine + AUTOMATED LEAKAGE TEST (must pass)
     realism battery: python -m synth.validate -> realism_report.json
     sanity ablation: python -m experiments.ablation synth_erp
```

**Reproducibility contract.** The dataset is a pure function of
*(config/synthetic.yaml, seed, generator code version)*. Re-running
`python -m synth.generate` reproduces the CSVs **byte-identically** — verified
on the shipped build: two runs produced identical SHA-256 hashes
(`transactions.csv` → `52542777…`, recorded with the others in
`generation_manifest.json`; generation takes ~11 s). Every fraud row carries
its scenario id (`ALERT_ID`), and `scenarios.json` records each scenario's
typology, actors, victim, dates and transaction count — full per-row
provenance.

## 5. The world and the normal behaviors (the 99.5%)

One year (365 days, day 0 = a Monday), timestamps in **seconds** — the richest
time axis in our roster (IBM has whole days, PaySim hours). Real calendar
texture: business hours with morning/afternoon peaks, weekend lulls, month-end
procurement spikes, seasonal Nov–Dec lift, payroll batches on fixed pay days.

| Flow (tx_type) | Behavior | Benign count (v1) | Why it exists (realism + honesty) |
|---|---|--:|---|
| `sale` | customers & employees buy from retail companies (zipf-popular retailers); ticket ~ lognormal(median 28·scale, σ0.95); business customers pay invoice-sized sums (median 1,600, σ1.1); plus private **marketplace sales** between people (28,359) | 759,633 | the retail bulk (calibrated to BankSim); **benign fan-in** at busy companies; people who joined this year receive benign sales too |
| `vendor_payment` | procurement from zipf-weighted supplier pools (incl. **vendors onboarded mid-year**), month-end spike; invoice ~ vendor base (median 2,500, σ1.4 — SAP-like) | 207,214 | the ERP payables bulk; benign mass in the *same amount band fraud uses*; new-supplier payments are normal life |
| `payroll` | per-company batches (monthly dom 25–28 or biweekly), salaries lognormal(3,800, σ0.35) ±1%, December bonuses, **new hires join batches once hired** | 49,240 | **benign fan-out bursts** (a mule-network lookalike, honestly benign) |
| `transfer` | treasury sweeps (round sums), intercompany settlements, **P2P** (rent shares, loans; median 600, σ1.0, any hour) | 91,135 | keeps `transfer` majority-benign (fraud share 3.0%) and gives illicit transfers a crowd to hide in |
| `refund` | 2.6% of sales come back (70% full, else 20–90%), days later | 18,396 | **benign reciprocal near-equal pairs** — benign "cycles" exist by design |
| `reimbursement` | employees claim expenses ~4×/yr (median 110, σ0.9) | 12,139 | company→employee traffic beyond payroll; the rail expense fraud hides in |
| `recurring_bill` | 8–14 vendors/company, fixed day-of-month, fee ±2% | 5,137 | **benign amount-recurrence** (single payer — the recurring-billing pattern) |

Money **circulates**: salaries fund employee purchases, which fund companies,
which pay vendors — so benign multi-hop paths and benign loops exist without
being scripted. ~10.2k customers *arrive during the year*, ~15% of vendors are
*onboarded during the year*, and ~10% of employees are *hired during the year* —
so "recently opened account" (on either side of a payment) is normal life, not
a fraud marker (§10, review fix 2a).

## 6. The fraud typologies (behavior + evasion, never patterns)

268 scenarios, 5,609 labeled transactions (0.49% — inside the real range
0.12–1.21%). **Labeling policy** (mirrors IBM AML): a row is labeled 1 iff the
fraudster initiated, rerouted, or misapplied it — a mule's groceries stay 0;
the scam payment into the mule and the forward out of it are both 1.

| Typology (`alert_type`) | The behavior (goal) | Evasion built in | Scenarios / rows (v1) |
|---|---|---|--:|
| `laundering_cycle` | embezzle from a company (placement disguised as a payable), layer through a ring of aged shells + occasional recruited mule; 60% of rings return funds to the entry account, 40% exit — **loops are a consequence, not a target** | skim 1–6% per hop (amounts NOT conserved), lognormal hop gaps (median 9h), occasional split hops, placement structured under the approval threshold | 88 / 1,442 |
| `mule_fanin` | scam private parties; victims pay mules (existing customers who keep living normal lives); mules forward 88–96% to a collector; collector exits in chunks | staggered over 5–30 days (no bursts), forward delays 6h–4d, recruitment only from established accounts, half the scam payments ride the purchase rails (fake marketplace "sales") | 48 / 2,327 |
| `lapping` | an A/R clerk diverts a business customer's invoice payment to their own account, then covers the hole with a near-equal transfer days later; repeat; 40% of schemes collapse uncovered | diversions ride the normal `sale` stream at office hours; covers 97–100% of the hole (not exact); gaps 3–10 days | 34 / 760 |
| `invoice_kickback` | a colluding vendor (40% a planted shell vendor, 60% a corrupted real one) overbills; the insider approves; vendor kicks back 25–50%, sometimes via an intermediary | invoices structured at 70–96% of the approval threshold or 1.3–2.2× vendor history; kickbacks delayed 4–18 days | 44 / 625 |
| `larceny` | an insider drains company funds: 70% to a shell "vendor" at invoice scale, 30% as **expense fraud** — padded claims on the reimbursement rail at claim scale, escalating as confidence grows | amounts below approval threshold, 35% split into 2–4 structured parts, office-hours camouflage, `vendor_payment` / `reimbursement` disguise | 54 / 455 |

Anti-giveaway measures shared by all: fraud reuses the **benign `tx_type`
vocabulary** at benign-dominated shares (fraud is 3.0% of `transfer`, 0.1% of
`sale`, 0.45% of `vendor_payment`, 1.0% of `reimbursement`); fraud amounts are
lognormals that sit **inside the benign B2B band**; shells are opened 5–120
days before first use; insiders are real employees with payroll history;
corrupted vendors keep their legitimate business.

## 7. Calibration: how real numbers set the parameters

Measured by `python -m synth.calibrate` (results/synth_erp/calibration_reference.json):

| Statistic (real, measured) | ibm_aml | banksim | sap_wurzburg | paysim | → generator parameter |
|---|--:|--:|--:|--:|---|
| Fraud rate | 0.13% | 1.21% | 0.12% | 0.13% | target ~0.5% (inside the span) |
| Amount median | 156.7 | 26.9 | 1,975.8 | 74,872 | consumer ticket median 28 (BankSim); vendor invoice median 2,500 (SAP) |
| log1p(amount) std | 2.02 | 0.96 | 1.10 | 1.81 | per-flow σ 0.35–1.4 → wide mixture |
| Benford MAD | **0.076** | 0.032 | 0.039 | 0.014 | no explicit target — mixtures of heavy-tailed flows approximate Benford naturally (§8 verifies) |
| Repeat-pair share of txns | 0.994 | 0.964 | 0.628 | ~0.0 | stable relationships: favorites, supplier pools, payroll, subscriptions |
| Pair reciprocity | 0.045 | 0.0 | 0.0 | 0.0 | refunds + sweeps + covers → small, nonzero |
| Namespace overlap | 0.993 | 0.0 | 0.0 | 0.0002 | an ERP economy is *partly* bipartite (pure consumers exist) → mid-range by design |
| Fraud/benign amount-median ratio | **0.068 (the AMLSim giveaway)** | 11.9 | 0.56 | 5.9 | fraud amounts drawn from the benign B2B band (§8 reports ours) |

The last row is the measured artifact this generator is designed against: in
IBM AML, fraud amounts alone nearly classify fraud (univariate ROC 0.91 — see
A.4b). The real sets span ratios 0.07–11.9; the honest goal is *overlap*, not
identity.

## 8. Realism validation — synthetic vs. real (measured, not asserted)

Produced by `python -m synth.validate` → `results/synth_erp/realism_report.json`.
"Real span" = the min–max across ibm_aml / banksim / sap_wurzburg / paysim
(measured in §7). *In range* means inside that span; out-of-range values are
kept and explained, not hidden.

| Metric | `synth_erp` v1 | Real span | Verdict |
|---|--:|--:|---|
| Transactions | 1,148,503 | 200k – 6.36M | ✔ Tier-1 scale (≈ IBM's 1.32M) |
| Accounts | 39,393 | 4.2k – 9.07M | ✔ mid-range |
| Fraud rate | **0.488%** | 0.12% – 1.21% | ✔ in range |
| Amount median / p99 | 72.2 / 26,818 | 26.9–74,872 / 237–1.6M | ✔ in range (retail+B2B mixture) |
| log1p(amount) std | 2.33 | 0.96 – 2.02 | ✚ slightly wider — the economy spans cents (retail) to 500k (treasury sweeps); a mixture broader than any single-domain real set |
| **Benford MAD** (first-digit law) | **0.0047** | 0.014 – 0.076 | ✔ **closest to Benford of ALL datasets** — emerged from the flow mixture, never targeted |
| Repeat-pair share of txns | 0.859 | 0.0 – 0.994 | ✔ in the ERP cluster (ibm 0.994, banksim 0.964, sap 0.628) — stable business relationships |
| Namespace overlap | 0.941 | 0.0 – 0.993 | ✔ high, IBM-like: most accounts both send and receive (a circulating economy) |
| Pair reciprocity | 0.136 | 0.0 – 0.045 | ✚ above range — salary↔purchase and refund circulation, which interbank/retail-only real sets structurally lack; benign-driven, not a fraud marker |
| Business-hours share / weekend share | 0.79 / 0.17 | (real sets too coarse to compare) | descriptive: realistic office texture, richer time axis than any real set |
| **Tabular leak probe** (§10) | **leak_flag FALSE** — worst single rule precision 0.093 | n/a (our own gate) | ✔ no cheap non-topological rule separates fraud |

**The anti-AMLSim check (fraud amount camouflage), the one we designed for:**

| Univariate log-amount ROC (a "one-column model") | value |
|---|--:|
| IBM AML (real; the measured artifact) | 0.914-equivalent (0.086 flipped) — fraud amounts are *distinctively small* |
| BankSim (real) | 0.949 — fraud amounts are *distinctively large* |
| **synth_erp overall** | **0.808** — lower than both Tier-1 real sets |
| **synth_erp within the 300–20k band** (where 93% of its fraud lives) | **0.491 ≈ chance** |

Reading: globally, fraud is "B2B-sized in a retail-heavy economy" (median ratio
23.8×, a *mixture* effect also present in BankSim at 11.9×) — but **inside its
own amount band, fraud is statistically invisible by amount** (ROC 0.491,
n=5,228 fraud rows in band). Detection there must come from *behavior over time
and structure*, which is precisely the regime this project studies. No real
dataset in our roster achieves that; both Tier-1 sets have a stronger amount
giveaway than our synthetic one.

## 9. Emergence check (ground truth only) + pipeline verification

**Pipeline verification (the same gates every real dataset passes):**
- Canonical ETL audit ✔ (`data/processed/synth_erp/audit.json`: 1,148,503
  edges, 39,393 accounts, fraud rate matches the manifest).
- **Automated leakage test ✔ PASSED** — truncation invariance *and*
  future-corruption invariance on 150k rows (cut at 75k), all 13 topology
  features (`python -m topology.leakage_test synth_erp`).
- Feature table built ✔ — same manifest contract (15 ordinary + 13 topology
  cols, `topology_structure` vs `topology_amount` split); `alert_*`/`role`
  excluded from features by construction.
- **Tabular leak probe ✔ leak_flag FALSE** (§10) — worst rule
  `transfer & dest_created_midyear` at precision 0.093 (enriched 19×, far from
  deterministic; "new account moving money" is a legitimate real-world risk
  factor, not a label).

**Emergence (ground-truth labels + topology output; evaluation-only).** The
generator never targets detector features — so the honest question is whether
the *behaviors* left structural traces at plausible, non-degenerate rates:

| Ground-truth view | Measured (v1) | Reading |
|---|--:|---|
| Benign in-cycle background | **5.8%** | benign loops exist (refunds, salary↔purchase circulation) — vs IBM's 19.5%; a live background, not a sterile one |
| Benign cycle lengths | len-2 pairs + ~44k len-3–6 closures | organic ≥3-hop benign circulation (payroll → purchases → payroll) |
| `laundering_cycle` rows closing a cycle | **18.5%** (all ≥3-hop) | 3.2× enriched over background — loops *emerged* from ring behavior (60% loop-back × timing/window truncation), far from a deterministic marker |
| `mule_fanin` collector fan-in | p90 = **8** distinct senders in-window | sits far *below* benign retail fan-in (benign p99 = **4,197**) — no free lunch for a raw fan-in threshold; discrimination requires combinations, exactly like reality |
| `lapping` amount-recurrence (`lap_in_recur`) | fraud mean 0.06 vs benign 0.31 | recurring bills/payroll dominate benign recurrence — lapping is NOT flagged by recurrence alone (consistent with the A.4d verdict that lap features are weak/amount-derived) |
| `invoice_kickback` / `larceny` structure | near-benign rates | correct: these are amount/threshold frauds, structurally quiet by nature |

**Sanity ablation** (usage policy §1 — a pipeline check, *never* evidence for
DESIGN §9): full results in `results/synth_erp/ablation.json`, same 7-model
protocol as the real datasets (time-aware split, class weights, val-tuned
frozen threshold, 1,093 test frauds):

| feature set | test PR-AUC |
|---|--:|
| baseline (ordinary) | 0.163 |
| baseline + structure | **0.567** (+0.403) |
| baseline + all topology | 0.563 |
| no-amount + structure (the clean amount-blind probe) | 0.269 (**+0.112** over no-amount 0.157) |
| topology only | 0.306 (≈ 63× the 0.49% base rate) |

Reading, carefully bounded. After the adversarial-review fixes removed the
tabular giveaways, the ordinary baseline settled at 0.163 (≈ 33× the base rate
— real signal from amount-band membership, account age and mild type
enrichment, but nothing cheap), and the *structural* features carry most of the
detectable signal, led by plain degree/fan features (`src_out_degree` 0.079 —
consistent with the project's A.4d verdict that *density is the topology
signal*). That hierarchy — weak-ish tabular, strong structural — is the
designed premise of the dataset (its frauds are relational behaviors), so we
state it plainly: **this number validates the pipeline and the training-corpus
design; it says nothing about real-world topology value** (we authored the
behaviors). The clean amount-blind structure lift (+0.112) is the number to
quote if any is quoted at all.

None of these numbers were targeted by the generator; they are read off the
data afterwards, which is the whole point.

## 10. Adversarial review (the independent refutation attempt)

Before shipping, an **independent AI reviewer (Claude Opus 4.8)** was given the
generator code and explicitly instructed to *refute* its claims — hunt for
circularity violations, giveaway artifacts, label leakage, and bugs. This is
the same adversarial ethic as the project's leakage test: claims must survive
an attack, not just an author's assertion.

**What the review confirmed (verbatim verdicts):**
- *Circularity rule UPHELD*: fraud is goal-driven behavior; `src/synth/`
  references no detector; shapes emerge as consequences. The reviewer noted the
  generator even steers the discriminative cycle features **away** from the
  detector's "conserved + fast" suspicious region (per-hop skims, loose hop
  timing) — anti-targeting, the opposite of the trap.
- Fan-in honesty confirmed empirically (benign retail fan-in dwarfs collectors);
  amounts Benford-ish with no roundness tell; reproducibility verified
  independently (the reviewer re-ran the assembly and matched the manifest's
  flow counts exactly).

**What the review refuted — two CRITICAL tabular giveaways (both real, both
fixed, both re-verified):**

| Finding | Draft build (measured by reviewer) | Fix (behavioral, not cosmetic) | Shipped build (re-measured) |
|---|---|---|---|
| **Receiver-side `creation_day` leak**: every benign money-receiver was pre-existing, so "`vendor_payment` to an account created this year" was a **100%-precision fraud rule** (779/779) | precision 1.000 | mid-year **vendor onboarding** (15% of vendors) + **new hires** (10% of employees) — real economies onboard suppliers and hire people continuously; procurement/payroll/reimbursements respect onboarding dates | precision **0.033** (support 25,816) |
| **`tx_type=transfer` concentration**: 76% of fraud rode `transfer` at 9.4% fraud share (18× base) | 18× lift, one dummy = recall 0.76 | 3× benign P2P volume + 3× intercompany (real ledgers are transfer-heavy); scam payments ride purchase rails 50% of the time (fake marketplace "sales"); own-account larceny becomes small-scale **expense fraud** on the reimbursement rail | fraud share of `transfer` **3.0%** (6× — enriched, as in reality, but no longer a classifier); fraud spans 4 tx_types |

**The reviewer's third recommendation became a permanent gate.** `synth.validate`
now runs a **tabular-leakage probe**: it scans every `tx_type` one-hot, the
node-attribute rules (`creation_day` on both sides), and their conjunctions,
and raises `leak_flag` if any single rule reaches precision > 0.5 with
support ≥ 50. On its very first run after the two fixes, **the probe caught a
third, residual leak the fixes had exposed** — `sale` received by a mid-year
account (128 rows, 100% precision: benign sales only ever landed on
pre-existing company accounts). Fixed behaviorally (a slice of P2P traffic is
private *marketplace sales*, so people who joined this year receive benign
sales too) and re-verified: the rule's precision fell to **0.015**, and the
shipped build passes the probe (§8/§9 numbers are from the post-fix build).

Minor findings (all fixed): a version-string typo in the manifest; laundering
rings could re-recruit the same mule as `mule_fanin` (recruitment is now
shared); a scam victim could coincide with its own mule (guarded); an unused
zipf popularity table (now actually applied — retailer popularity is power-law
as intended). One residual, *acknowledged* non-leak: fraud uses off-hours
timing more than office-driven benign flows; no hour-of-day feature exists in
the pipeline, and benign P2P also runs around the clock, but **if anyone adds
an hour-of-day feature to the baseline, re-run the probe first** (recorded here
so it cannot become a silent future leak).

**Why this section matters:** the review changed the dataset. The draft would
have let three cheap tabular rules recover 97.5% of fraud — sabotaging the very
ablation the dataset exists to support. The shipped build's honesty is not
asserted; it is the survivor of a documented attack, with the attack's own
checks now automated in the pipeline.

## 11. Relevance to the project

- **Fills the roster's empty quadrant.** Our real sets are either
  structure-rich but amount-saturated (IBM), or structured-but-bipartite
  (BankSim, SAP), or near-forest (PaySim). `synth_erp` is the first dataset in
  the roster that is simultaneously: account↔account (cycles possible), ERP-
  flavored (payables/payroll/receivables), multi-typology, amount-camouflaged,
  and *large in fraud count* (5,609 labeled rows vs. IBM's 1,719).
- **Training material for Phase-2 models** (including the FT-Transformer
  challenger from MODERNIZATION_REPORT.md, which is data-hungry precisely where
  real data is poorest — fraud examples). **First measured use (2026-07-13,
  `experiments/augmentation.py`, 3 seeds × 3 arms, shared 6+13 feature space,
  real-only val/test):** *naive pooled augmentation of the XGBoost champion is
  a clean NEGATIVE result* — real+synth trails real-only on every real dataset
  (banksim 0.867→0.761, paired Δ −0.106 ± 0.001; ibm 1.000→0.995; sap
  0.137→0.029, 25 test frauds). Domain shift: one tree ensemble fit jointly
  over two economies pulls its splits toward the synthetic distributions. **The
  buried lede is the zero-shot probe:** a model trained *only* on `synth_erp`
  scores **0.724 PR-AUC on real BankSim** (real-trained: 0.867; chance: 0.012)
  — the synthetic economy teaches genuinely *transferable* fraud discrimination
  when the target domain is structurally similar, and none at all when it is
  not (IBM zero-shot 0.002; IBM's fraud signature — distinctively *small*
  amounts in day-bursts — is inverted vs. ours). **Usage policy refined
  accordingly:** do not pool synthetic rows into tree-model training; the
  training role is *pretrain → fine-tune* for the data-hungry neural
  challenger, plus the stress-test/demo roles below. Full numbers:
  `results/<dataset>/augmentation.json`.
- **Per-typology stress testing**: ground-truth scenario provenance lets us
  measure per-typology recall of any model or detector — impossible on BankSim
  (no typology labels at all).
- **Demo material for Step 5**: scenarios are *narratable* ("this alert is
  scenario LAUN-0007: placement on day 141, five hops, returns to entry") with
  full path provenance for the Neo4j audit-alert demo.
- **A honest negative-control lesson baked in**: same canonical contract, same
  leakage test, same ablation harness — nothing downstream special-cases it.

## 12. Known limitations (state these whenever the dataset is cited)

1. **It is still a simulation.** Behaviors are hand-designed from practitioner
   taxonomies (ACFE) — real adversaries adapt; covert typologies we didn't
   script don't exist in it. Absence of evidence in `synth_erp` is not evidence
   of absence in reality.
2. **The thesis is never proven here.** Any topology-vs-baseline result on
   `synth_erp` is a *sanity check* of the pipeline, not evidence for DESIGN §9
   (we authored the structure; see §1 usage policy).
3. **Simplified economy.** 30-day months; no multi-currency, no fees/taxes, no
   intraday liquidity patterns; consumer P2P is uniform-random rather than
   community-structured; goods/invoices are not modeled (amounts only).
4. **Fraud rate (0.49%) is 4× IBM's** — deliberately, for training density; use
   class weights as usual and remember precision@k on real data is the metric
   that matters.
5. **Single seed shipped (v1).** The generator is seed-parametric; multi-seed
   dataset families (for variance estimates or train/test worlds) are one
   config change away.

## 13. How to regenerate / audit (the checklist a reviewer can run)

```bash
python -m synth.calibrate            # 1. re-measure the real datasets
python -m synth.generate             # 2. regenerate raw (byte-identical: check
                                     #    sha256 in generation_manifest.json)
python -m etl.build synth_erp        # 3. canonical files + audit.json
python -m topology.engine synth_erp  # 4. topology features + ground-truth audit
python -m topology.leakage_test synth_erp   # 5. MUST print passed: true
python -m features.build synth_erp   # 6. model table + manifest
python -m synth.validate             # 7. realism battery vs. real reference
python -m experiments.ablation synth_erp    # 8. sanity ablation (usage policy §1!)
```

Artifacts a reviewer inspects: `generation_manifest.json` (seed, config echo,
SHA-256, counts), `scenarios.json` (per-scenario provenance),
`calibration_reference.json` (the real-data anchors),
`realism_report.json` (the comparison), `topology_audit.json` (emergence),
`results/synth_erp/ablation.json` (sanity model runs).
