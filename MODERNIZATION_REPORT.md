# MODERNIZATION_REPORT — Tabular Transformers vs. XGBoost for Phase 2

*Prepared as a Principal-AI-Architect review of the Self-Auditing Ledger's modeling
layer (Phase 2). Scope: `src/modeling/`, `src/features/`, `experiments/ablation.py`,
with the topology layer (`src/topology/`) reviewed for interface constraints only.
The `reference/` directory was excluded entirely, as required.*

**Date:** 2026-07-10
**Verdict up front (TL;DR):** Adopt a **champion–challenger** design. Keep the
class-weighted XGBoost pipeline as the champion (it is well-built and is the
correct tool for this data regime), and integrate an **FT-Transformer** as a
rigorously-evaluated challenger inside the *existing* ablation harness. Do **not**
rip out XGBoost: on ~1M-row, 0.1%-fraud tabular data, the peer-reviewed evidence
says tabular transformers are *competitive at best*, not strictly superior — and
your explainability requirement (exact TreeSHAP) plus your streaming-latency story
both favor trees. The honest scientific move — fully in the spirit of this project —
is to measure the challenger under the identical leakage-free protocol and report
the result either way.

> **Architecture-lock note.** Locked decision #7 in `PROJECT_OVERVIEW.md` names
> gradient-boosted trees as the workhorse, with neural models as *optional future
> comparison only*. Everything in this report is designed to fit inside that
> decision: the transformer is added as a comparison arm of the ablation, not as a
> replacement. Promoting it to primary model would be an architecture change and
> needs a recorded decision first.

---

## 1. Codebase Assessment — critique of the current modeling pipeline

### 1.1 What is genuinely good (and should not be touched)

The modeling layer is small, honest, and unusually disciplined for a research
codebase. Specifically:

- **`src/modeling/harness.py`** implements the five non-negotiable rules
  correctly: chronological `time_split` (with the partition-aware variant for
  SAP's synthetic time axis), a *single* imbalance mechanism
  (`scale_pos_weight = neg/pos`), early stopping driven by validation PR-AUC
  (`eval_metric="aucpr"`), a threshold tuned on validation and frozen for test,
  and artifact persistence. This is the part most projects get wrong; here it is
  right.
- **`src/modeling/metrics.py`** reports PR-AUC as primary plus precision@k /
  recall@k — the operationally honest metrics for a 0.1%-fraud problem. The
  stable-sort `argsort` in `precision_recall_at_k` avoids tie-order flakiness.
- **`experiments/ablation.py`** is the scientific centerpiece and it is well
  designed: 7 feature-set arms sharing one split, one seed, one imbalance
  mechanism, with the structure-only / amount-blind distinction (A.4d) that caught
  your own lapping-detector mirage. That self-correction is exactly what a
  credible pipeline looks like.
- **`src/features/build.py`** builds a leakage-safe baseline (expanding,
  past-only account statistics; `time_since_prev`, never `time_to_next`) and
  cleanly separates `ordinary` / `topology_structure` / `topology_amount` columns
  in the manifest — which is precisely the interface a second model type needs.

### 1.2 Efficiency and rigor gaps (ranked by importance)

These are the findings from the code review. None invalidate existing results,
but #1 and #2 matter *directly* for the transformer question.

1. **Single-seed results are too noisy for the margins being interpreted.**
   `run_ablation` runs one seed (42). The verdicts in A.4b–A.4d hinge on
   differences as small as +0.008 PR-AUC (IBM full-model marginal) and +0.0013
   (cycle features). XGBoost with `subsample=0.8` / `colsample_bytree=0.8` is
   stochastic, so seed-to-seed variance can be the same order of magnitude as
   those margins. Neural networks are *far* worse on this axis (initialization +
   minibatch order), so any transformer comparison at one seed would be
   meaningless. **Fix: multi-seed repetition (≥3, report mean ± std) must land
   before any champion–challenger comparison.** This is the single highest-value
   change in this report, and it benefits the existing XGBoost results too.

2. **No hyperparameter tuning on either side.** `_fit_xgb` uses one fixed,
   sensible config (500 trees, depth 6, lr 0.05). That's fine for an ablation
   where both arms share the config, but a *model-class comparison* is only fair
   if both classes get a comparable (small, validation-only) tuning budget.
   An untuned transformer will lose to anything; an untuned XGBoost understates
   the champion. A modest random search (~20–30 trials, selected on validation
   PR-AUC — never test) is enough.

3. **Feature importance uses XGBoost's gain-based `feature_importances_`**
   (`harness.py:111`), which is known to be biased toward high-cardinality and
   continuous features and inconsistent across correlated features. Since Step 5
   (explainability) is next and SHAP is already a locked decision, switch the
   *reported* importances to mean |SHAP| on the validation set. Cheap (TreeSHAP is
   fast) and it makes the ablation's `topology_importance` block trustworthy.

4. **Validation set does double duty** — early stopping *and* threshold tuning
   both consume `val`. Test metrics stay honest (nothing touches test), but
   validation metrics are mildly optimistic and the threshold inherits a little
   selection noise. Acceptable at 1.3M rows; worth a sentence in the write-up,
   and worth remembering that a NN adds a *third* consumer of `val` (epoch
   selection).

5. **Persistence assumes trees.** `bundle.json` hardcodes
   `"note": "trees need no scaler"` (`harness.py:133`). True for XGBoost, but
   rule 6 says *model + scaler + threshold*, and any neural path **requires** a
   train-fit scaler. The refactor in §6 makes the bundle model-agnostic.

6. **Minor performance / hygiene items.**
   - Intermediates are CSV (`features_topology.csv` at 6.36M rows for PaySim);
     Parquet would cut load times several-fold. The model table already prefers
     Parquet — extend that to the topology table.
   - The 7 ablation arms run serially and each re-derives the identical split;
     harmless at current scale, but computing the split once and passing masks in
     would make the "same split" guarantee structural rather than incidental.
   - `pd.get_dummies` in `features/build.py` derives the category *vocabulary*
     from the full dataset. This is a technically-look-ahead but practically
     harmless leak (it reveals only that a category value exists somewhere in
     time, not any label information). Fine to keep; worth a code comment.
   - The streaming engine (`topology/engine.py`) is a pure-Python row loop —
     entirely appropriate for the research phase; if PaySim-scale reruns become
     frequent, numba on the hot loop is the escape hatch. Not needed now.

**Overall grade: A− for rigor, B for statistical power.** The pipeline's honesty
machinery is excellent; its weakness is that it currently can't distinguish small
real effects from seed noise — which is exactly the regime a transformer
comparison lives in.

---

## 2. The Tabular Transformer Problem — what the evidence actually says

### 2.1 Why "LLMs" are the wrong tool, in plain terms

A large language model is trained to predict *tokens in sequences of text*. Your
Phase-1 output is a fixed-width numeric row: `fan_in=3, dest_in_degree=17,
amount_zscore_src=4.2, …`. Serializing that row into a sentence and asking an LLM
to score it throws away the thing that matters (precise numeric magnitudes and
their interactions) and adds the things that hurt (token-level noise, huge
latency, no calibrated probability output, no leakage guarantees). So the correct
neural candidates are **tabular deep-learning architectures**: networks designed
to consume a numeric feature vector directly. "Tabular transformers" are the
subfamily that treats *each feature as a token* and lets self-attention learn
feature-feature interactions — the same mechanism as an LLM, but over ~30 feature
tokens per transaction instead of thousands of word tokens.

### 2.2 The literature reality check (this determines the recommendation)

The peer-reviewed record on "deep learning vs. gradient-boosted trees on tabular
data" is unusually consistent:

- **Grinsztajn, Oyallon & Varoquaux (NeurIPS 2022, Datasets & Benchmarks)** —
  *"Why do tree-based models still outperform deep learning on tabular data?"*
  On medium-sized tabular benchmarks, tuned trees beat tuned deep models. The
  diagnosed reasons — target functions with sharp/irregular decision boundaries,
  and robustness to *uninformative features* — describe fraud data precisely
  (think of a hard rule like "fan_in > 40 AND amount round" — trees represent
  that natively; smooth attention functions must approximate it).
- **Gorishniy, Rubachev, Khrulkov & Babenko (NeurIPS 2021)** — *"Revisiting Deep
  Learning Models for Tabular Data."* Introduced **FT-Transformer** and showed it
  is the strongest *neural* tabular model across benchmarks — while also showing
  no neural model universally beats tuned GBDTs.
- **Shwartz-Ziv & Armon (Information Fusion 2022)** — *"Tabular data: Deep
  learning is not all you need."* The published tabular-DL wins largely evaporate
  outside each paper's own benchmark suite; XGBoost + light tuning remains the
  strongest single default.
- **McElfresh et al. (NeurIPS 2023)** — *"When Do Neural Nets Outperform Boosted
  Trees on Tabular Data?"* Across 176 datasets: for most, the choice barely
  matters; trees win more often as datasets get larger and more "irregular."
- **Extreme-imbalance regime specifically:** with 0.12–1.2% positives, the
  effective sample size is the *fraud count* (1.7k–8.2k positives here), not the
  row count. Deep models are data-hungry precisely where you are data-poor, and
  their minibatch training sees ~5 positives per 4,096-row batch — gradient
  signal for the minority class is sparse and high-variance. Trees with a global
  class weight simply do not have this problem.

**Honest conclusion:** the request was for architectures "strictly superior or
highly competitive." **Strictly superior does not exist in the published record
for this data regime.** Highly competitive does — and there is a defensible
scientific reason to test it here anyway: your datasets have *structured,
low-dimensional* feature spaces (the A.4d verdict says density features carry the
signal), and attention-based models occasionally win where a few feature
interactions dominate. The cost of finding out is low (§5), and the
champion–challenger result strengthens the write-up either way — the same
"report it either way" ethic as the topology ablation itself.

---

## 3. SOTA Model Recommendations

Three candidates, ranked. #1 is the one to actually build.

### 3.1 ✅ FT-Transformer (Feature-Tokenizer Transformer) — the challenger of choice

**What it is, simply:** each of your ~30–45 features gets embedded into a small
vector (a "token"), a learned `[CLS]` token is prepended (exactly like BERT's
summary token), and 2–4 transformer blocks let every feature attend to every
other feature. The `[CLS]` output feeds a small head that produces the fraud
logit. It is the transformer idea, shrunk to feature-space.

**Why it's the right challenger here:**
- Consistently the **strongest neural tabular model** in independent benchmarks
  (Gorishniy 2021; McElfresh 2023) — if any neural model beats your XGBoost, it
  is this family. Testing the best challenger makes a negative result meaningful.
- **Trains with plain class weights** (`pos_weight` in `BCEWithLogitsLoss`) — so
  it slots into rule 1 (one imbalance mechanism, class weights) without any
  protocol change. No SMOTE, no sampler tricks needed.
- **Per-row scoring at inference** — no dependence on other rows in the batch —
  so it fits the streaming "auditor at a desk" story (unlike SAINT/TabR, see 3.3).
- Tiny at your feature count: d_token=192, 3 blocks, ~45 tokens ≈ **~1M
  parameters, ~4MB**. Trivially inside any Legion 5 GPU (§5.2).
- Reference implementation exists (`rtdl_revisiting_models` on PyPI, by the
  paper's authors), or ~150 lines of custom PyTorch — well within your stated
  comfort zone from YOLOv8 work.

**Known weaknesses (state them in the write-up):** needs feature scaling
(quantile transform, fit on train only) and explicit NaN handling (§6.2);
high seed variance (hence §1.2 item 1); attribution is approximate, not exact
(§4).

### 3.2 ⚠️ TabNet (Arik & Pfister, AAAI 2021) — worth one experiment for its explainability angle, not as the primary challenger

**What it is, simply:** a network that makes decisions in sequential steps, and
at each step uses a learned **sparse mask** to pick *which few features it is
allowed to look at*. The masks are readable afterwards: "for this transaction,
step 1 looked at `fan_in` and `dest_in_degree`, step 2 at `amount_zscore_src`" —
a built-in, per-transaction attribution map.

**Why it's tempting for this project:** the mask story sounds tailor-made for
audit alerts (§4). It also natively tolerates less preprocessing than
FT-Transformer.

**Why it's ranked second:**
- In independent benchmarks (Gorishniy 2021; Shwartz-Ziv 2022; McElfresh 2023)
  TabNet reliably **underperforms both FT-Transformer and XGBoost**, and is
  notoriously finicky to tune (its own hyperparameters — n_d, n_a, n_steps,
  sparsity λ — interact badly).
- The interpretability claim needs a caveat: attention/masks are *where the model
  looked*, which is not proven to be *why it decided* (the "attention is not
  explanation" literature). SHAP values answer the "why" question with a game-
  theoretic guarantee; masks do not. So TabNet's headline advantage is weaker
  than it looks (§4.2).

**Recommendation:** run it once through the same harness (the §6 refactor makes
that ~10 lines via `pytorch-tabnet`), report it as a secondary line, and use its
masks only as a *qualitative sidebar* in the demo if it happens to perform.

### 3.3 ❌ Assessed and rejected (with reasons you can quote)

- **SAINT (Somepalli et al., 2021)** — adds *inter-sample* attention: each row
  attends to **other rows in the batch**. That means a transaction's score
  depends on which reference rows accompany it at inference — architecturally
  wrong for a streaming auditor (score one event as it arrives), and a leakage
  audit nightmare (which rows are in the reference batch? are they all past?).
  Its benchmark gains over FT-Transformer are marginal; the added risk is not.
- **TabPFN v2 (Hollmann et al., Nature 2025)** — a prior-fitted network that
  "learns to learn" small tables in one forward pass. Genuinely SOTA — but for
  **small data** (≈≤10k training rows natively). Your training splits are
  360k–3.8M rows; TabPFN would have to subsample away >99% of the data, and its
  in-context design is untested at 0.1% positive rates. Wrong scale, wrong
  regime. (Keep an eye on it for the SAP dataset specifically — 200k rows, 248
  frauds — where *nothing* works well; a context-based model on a stratified
  subsample is a plausible future footnote.)
- **TabR / retrieval-augmented models (2023)** — retrieve nearest training rows
  at inference. Same streaming/leakage objection as SAINT (the retrieval index
  must be as-of-time), plus an index-maintenance burden.
- **Temporal deep sequence models (TabBERT-style per-account transaction
  sequences; Temporal Graph Networks, Rossi et al. 2020)** — the genuinely novel
  direction: instead of consuming your engineered features, they consume the raw
  *event sequence* and learn their own temporal representations. Two reasons to
  defer, not reject: (a) they compete with *Phase 1 itself*, not with XGBoost —
  adopting them dissolves the project's central ablation (engineered topology
  vs. learned representation becomes unmeasurable); (b) TGN is a GNN, which
  locked decision #7 explicitly defers. **Right home: the already-planned Build
  Step 6 "GNN comparison" slot**, where a TGN-vs-(tabular+topology) experiment
  would be a strong follow-up paper section.

---

## 4. Explainability — the non-negotiable, examined honestly

Your audit alert = SHAP attribution + the concrete graph path (Neo4j). The graph
path is model-independent (it comes from the topology engine), so only the SHAP
half is at risk. Here is the exact state of play:

| | XGBoost (champion) | FT-Transformer | TabNet |
|---|---|---|---|
| **Exact SHAP** | ✅ **TreeSHAP** — polynomial-time, *exact* Shapley values, milliseconds per row (`shap.TreeExplainer`) | ❌ not available | ❌ not available |
| **Approximate SHAP** | (not needed) | ✅ GradientSHAP / DeepSHAP / Integrated Gradients via `captum` or `shap` — differentiable model, so gradient-based attribution is fast (~ms) but *approximate*; KernelSHAP is model-agnostic and unbiased-ish but ~seconds/row | ✅ same as FT-T |
| **Built-in mechanism** | gain/split stats (biased — see §1.2.3) | attention maps of the `[CLS]` token over feature tokens (Gorishniy shows they correlate with importance; no faithfulness guarantee) | sparse step masks — readable per-row, but "where it looked," not "why it decided" |
| **Auditor-defensibility** | **High** — exact, axiomatic, standard in industry model-risk review | Medium — must document the approximation | Medium-low — masks are attractive but the faithfulness caveat must be disclosed |

**Three concrete rulings:**

1. **The audit-alert path (Step 5) should be built on TreeSHAP + XGBoost
   regardless of the challenger outcome.** Exactness matters when a human
   investigator is confronting a flagged vendor; "approximately, the model
   thinks…" is a weaker sentence in an audit report.
2. **If the FT-Transformer wins the accuracy comparison**, the right production
   pattern is **dual-scorer**: transformer produces the risk score, XGBoost (or
   TreeSHAP on a distilled tree surrogate of the transformer) produces the
   attribution — plus an **attribution-parity check** in the harness: rank-
   correlate mean |SHAP| (champion) against mean |GradientSHAP| (challenger) on
   validation. High correlation ⇒ the explanation layer is telling the same
   story as the scorer; low correlation ⇒ surface it as a finding, don't hide it.
3. **TabNet's masks are a demo garnish, not the compliance mechanism.** Use them
   in the Neo4j demo *alongside* SHAP if TabNet is ever shown; never instead.

---

## 5. Feasibility & Trade-offs — latency, compute, accuracy

### 5.1 Latency (the real-time streaming story)

Order-of-magnitude estimates for a single transaction score; the roadmap (§6.5)
includes a benchmark step so the write-up uses *your* measured numbers, not mine.

| Model | Single-row, CPU | Batched throughput (GPU) | Streaming-safe? |
|---|---|---|---|
| XGBoost (500 trees, depth 6) | **~0.1–1 ms** (dominated by Python call overhead; the tree walk itself is µs) | >10⁶ rows/s | ✅ per-row, stateless |
| FT-Transformer (~1M params) | ~1–5 ms (CPU); sub-ms amortized on GPU | ~10⁵–10⁶ rows/s with fp16 | ✅ per-row, stateless |
| TabNet | ~1–5 ms | ~10⁵ rows/s | ✅ per-row |
| SAINT / TabR | n/a | n/a | ❌ needs reference rows at inference |

**Perspective:** your latency budget is set by Phase 1, not Phase 2 — the
bounded-BFS cycle search + feature assembly per event costs far more than either
model's forward pass (the IBM topology run was ≈5.5 min for 1.32M rows ⇒ ~250 µs
*per event* for topology alone). Both champion and challenger are comfortably
real-time for the replay demo. **Latency does not discriminate between XGBoost
and FT-Transformer at this scale; it only rules out inter-sample models.**

### 5.2 Compute — the Lenovo Legion 5 budget

Legion 5 configurations span roughly an RTX 3050 (4GB) to an RTX 4070 (8GB)
laptop GPU. The plan below fits the **worst** case (4GB) with headroom; on 6–8GB
you'll never think about VRAM at all. Check yours with `nvidia-smi`.

**VRAM math (IBM AML, the biggest Tier-1 set):**
- Whole feature matrix resident on GPU: 1.32M rows × ~45 features × 4 bytes
  ≈ **240 MB**. Load it once as a tensor; **no DataLoader workers, no disk I/O
  during training** — index minibatches straight off the GPU tensor. (This is
  the single biggest laptop-training speedup and it's free at your scale.)
- Model: ~1M params ⇒ 4MB weights + ~12MB Adam states. Negligible.
- Activations at batch 4,096: 4,096 × 46 tokens × 192 dims × 3 blocks × ~4
  tensors × 2 bytes (fp16) ≈ **0.9 GB** peak. Fits 4GB; on 8GB you can double
  the batch.
- Attention cost is trivial: sequences are 46 tokens, so the 46×46 attention
  matrix is ~2k entries — this is the *opposite* of the LLM regime.

**Wall-clock estimates:** 1.32M rows / 4,096 ≈ 320 steps/epoch ⇒ ~10–25 s/epoch
with AMP on a laptop 4060; 60–100 epochs with early stopping ⇒ **~15–35 min per
model per seed**. The 7-arm ablation × 3 seeds ≈ 5–12 h ⇒ **an overnight run**,
vs. ~minutes for the whole XGBoost ablation. PaySim (6.36M rows, ~1.1 GB on-GPU)
still fits but quadruples epoch time — do it last, if at all.

**CUDA optimization checklist (all standard, all apply):** mixed precision via
`torch.autocast("cuda", dtype=torch.float16)` + `GradScaler` (bf16 if on a 40-
series); `torch.compile(model)` (PyTorch ≥2.x, ~1.3–1.8× on small models);
fused AdamW (`fused=True`); no `DataLoader` (see above); watch laptop thermal
throttling on multi-hour runs (performance mode, plugged in).

**One environment flag:** Appendix A.2 records **Python 3.14**. PyTorch wheels
typically trail new CPython releases — before committing to the roadmap, verify
`pip install torch --index-url https://download.pytorch.org/whl/cu121` (or
current CUDA channel) has a 3.14/win-amd64 wheel. If not, run the NN work in a
side venv on Python 3.12 pointing at the same `data/processed/` outputs; nothing
in the feature layer needs to move.

### 5.3 Accuracy — handling 99.9% non-fraud (the honest expectations table)

| Concern | XGBoost (current) | FT-Transformer (proposed) |
|---|---|---|
| Imbalance mechanism | `scale_pos_weight` — global, exact, one line | `pos_weight` in `BCEWithLogitsLoss` — same semantics, rule-1 compliant |
| Minority gradient signal | Not an issue (full-data splits per tree) | ~5 positives per 4,096 batch ⇒ noisy; mitigate with large batches + patience-based early stopping on val PR-AUC |
| NaN features (`amount_zscore_src`, `cycle_amount_ratio`…) | **Native** (learned default split direction) — a real, underappreciated XGBoost advantage on your data | Must impute **and add missing-indicator columns** (the missingness itself is signal: "no prior history" correlates with fraud) |
| Sharp thresholds ("fan_in > 40") | Native step functions | Approximated by attention/MLP — the Grinsztajn failure mode |
| Seed variance | Low-moderate | High — 3+ seeds mandatory |
| Calibration of probabilities | Decent post class-weighting | Often poor — but your protocol already tunes the operating threshold on val, which absorbs most of this |
| Expected outcome (my professional prior) | — | **Ties or slightly trails XGBoost on ibm/banksim; unstable on SAP (25 test frauds — too few for any NN; expect INCONCLUSIVE and say so)** |

**Decision rule to commit to *before* running (pre-registration, in this
project's spirit):** the challenger is declared *competitive* if its mean test
PR-AUC over ≥3 seeds is within 1 std of the champion's, and *superior* only if it
beats the champion by more than 2× the pooled seed-std on at least one Tier-1
dataset. Anything else is a negative result — reported, per project ethic.

---

## 6. Implementation Roadmap — the exact refactor

Design principle: **the harness stays the single honesty gatekeeper.** The model
becomes a plug-in; the split, imbalance rule, threshold protocol, metrics, and
persistence contract stay in one place. Nothing in `src/topology/` or
`src/features/` changes, so the leakage test remains untouched and green.

### Step 0 — Environment (½ h)
```
pip install torch --index-url https://download.pytorch.org/whl/cu121   # verify Py3.14 wheel first — see §5.2
pip install rtdl_revisiting_models   # authors' FT-Transformer; or write custom (§6.2)
```
Add both to `pyproject.toml` as an optional extra (`[project.optional-dependencies] nn = [...]`)
so the core pipeline keeps working without torch.

### Step 1 — Make `harness.py` model-agnostic (~1 h)

Replace the hardwired `_fit_xgb` call with a fitter registry. Minimal diff:

```python
# harness.py
def train_and_evaluate(df, feature_cols, *, label="label", ts_col="timestamp",
                       seed=42, persist_as=None, partition=None,
                       model="xgb"):                      # <— new, default unchanged
    train, val, test = time_split(df[ts_col], partition=partition)
    X = df[feature_cols]; y = df[label].astype(int).to_numpy()
    fitter = _FITTERS[model]                              # {"xgb": _fit_xgb, "ft": fit_ft, "tabnet": fit_tabnet}
    fitted = fitter(X[train], y[train], X[val], y[val], seed)
    p_val, p_test = fitted.predict_proba(X[val]), fitted.predict_proba(X[test])
    # ... threshold tuning / evaluate / result dict: UNCHANGED ...
```

Define the plug-in contract as a tiny protocol every fitter returns:

```python
class FittedModel(Protocol):
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray: ...   # P(fraud), shape (n,)
    def save(self, art_dir: Path) -> None: ...                    # model + scaler + anything needed to reload
    imbalance_note: str        # e.g. "scale_pos_weight=778.2" — recorded per rule 1
    importance: dict[str, float] | None
```

Wrap the existing XGBoost path in this shape (10 lines). Persistence: `bundle.json`
gains `"model_type"` and drops the trees-only wording; the NN save writes
`model.pt` + `scaler.joblib` + `imputer.json` — **rule 6 finally exercised in
full** (scaler included).

### Step 2 — New module `src/modeling/nn.py` (~½ day, the main work)

Three pieces:

**(a) `TabularPreprocessor` — fit on TRAIN ONLY.** This is where NN-vs-tree
fairness and leakage discipline live, so make it explicit and boring:
```python
class TabularPreprocessor:
    """fit() on the train split only (the split-local cousin of the
    no-whole-dataset-normalisation rule); transform() everywhere."""
    def fit(self, X):    # 1) record NaN columns -> add <col>__missing indicators
                         # 2) median-impute (medians from train only)
                         # 3) QuantileTransformer(output_distribution="normal",
                         #        subsample=10**9, random_state=seed) — fit on train
    def transform(self, X) -> np.ndarray: ...
```
The quantile transform matters: FT-Transformer results in the literature depend
on it (heavy-tailed inputs like `dest_in_degree` otherwise dominate). The
missing-indicator columns preserve the "no history yet" signal XGBoost gets for
free from native NaN routing.

**(b) The model.** Either `rtdl_revisiting_models.FTTransformer.make_default(...)`
or a custom ~150-line implementation (per-feature linear tokenizer + learned
`[CLS]` + `nn.TransformerEncoder` with pre-norm + linear head). Start defaults:
`d_token=192, n_blocks=3, heads=8, dropout≈0.15, ffn_factor=4/3`.

**(c) `fit_ft(Xtr, ytr, Xval, yval, seed)` — the training loop.** Honesty
requirements mapped one-to-one from the XGBoost path:
- `torch.manual_seed(seed)`; data on GPU once (§5.2); batch 4,096 (halve on 4GB).
- `BCEWithLogitsLoss(pos_weight=neg/pos)` — **the one imbalance mechanism**; no
  sampler, no SMOTE, no focal loss (focal would be a *different* single
  mechanism — allowed only as a deliberate, logged comparison, per rule 1).
- AdamW (lr 1e-4, wd 1e-5, `fused=True`), AMP autocast + GradScaler.
- After each epoch: `average_precision_score(yval, p_val)` — early stop with
  patience ~16 epochs, **restore best-val-PR-AUC weights** (the exact analogue of
  `early_stopping_rounds=40` + `eval_metric="aucpr"`).
- Return a `FittedModel` whose `predict_proba` applies the stored preprocessor
  then a no-grad fp16 forward; `importance` = mean |GradientSHAP| on a val
  sample (captum), or `None` in v1.

### Step 3 — Thread it through `experiments/ablation.py` (~1 h)

- `run_ablation(name, seed=42, partition_aware=None, model="xgb")` — pass
  `model=` through the seven `train_and_evaluate` calls; write results to
  `results/<name>/ablation_{model}.json` (keep plain `ablation.json` for xgb so
  nothing existing breaks); CLI: `python -m experiments.ablation banksim --model ft`.
- Add `experiments/compare_models.py` (glorified table printer): loads
  `ablation_xgb.json` / `ablation_ft.json` per dataset, prints champion vs.
  challenger PR-AUC (mean ± std once Step 4 lands), the four lift numbers, and
  the §5.3 decision-rule verdict.

### Step 4 — Multi-seed support (~1 h, do this BEFORE any comparison)

`run_ablation(..., seeds=(42, 43, 44))` → run the arm set per seed, aggregate
`mean`/`std` per metric into the summary JSON. Run it for **xgb first** — this
retroactively puts error bars on A.4b–A.4d, which the write-up needs anyway.

### Step 5 — Benchmark + explainability parity (~½ day)

- `experiments/bench_latency.py`: measure single-row (CPU) and batched (GPU)
  scoring for both models on a 10k-row test slice → feeds the §5.1 table with
  real numbers for the paper/demo.
- Attribution-parity check (§4 ruling 2): Spearman rank-correlation between
  champion mean-|TreeSHAP| and challenger mean-|GradientSHAP| on validation;
  print it in `compare_models.py`.

### Step 6 — Run order and what to expect

1. **banksim** (595k rows, 7.2k frauds — most positives, and the one dataset
   where structure genuinely helps): the transformer's best shot. ~10 min/seed.
2. **ibm_aml**: baseline is amount-saturated at PR-AUC 0.99 — expect a tie at the
   ceiling; the interesting number is the *no-amount* arm, where attention gets
   its one theoretical opening (interaction-heavy density features).
3. **sap_wurzburg**: run it, expect INCONCLUSIVE (25 test frauds cannot train or
   evaluate a NN meaningfully), and pre-commit to saying so.
4. **paysim**: only if the challenger survives 1–2; overnight job.

Total effort: **~2–3 focused days** including the overnight training runs.

---

## 7. Final recommendation, in plain words

Your XGBoost pipeline is not a legacy liability to modernize away — it is the
correct, evidence-backed choice for million-row, 0.1%-fraud, feature-engineered
tabular data, and it is the only option with *exact* SHAP for the audit alerts
that are this project's selling point. The modernization that actually raises
the project's quality is (1) **multi-seed error bars** and SHAP-based
importances on what you already have, and (2) an **FT-Transformer challenger**
run through the same seven-arm, leakage-free ablation — pre-registered decision
rule, result reported either way. That gives you a modern deep-learning
comparison worth putting in the write-up, at ~2–3 days of work and zero risk to
the honesty guarantees, while keeping the door open for the genuinely novel
neural step (temporal graph networks over the raw event stream) in Build Step 6
where the locked architecture already reserves a seat for it.
