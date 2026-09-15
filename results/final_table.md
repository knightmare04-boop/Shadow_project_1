# Final consolidated results

Test-period metrics, mean +- std over seeds. Baseline/+topology/+TGN rows are the recorded modernization aggregates (modern.json); the final row is the promoted champion (final.json).

## banksim  (test frauds: 1320)

| model | test PR-AUC | precision@100 |
|---|---|---|
| baseline (ordinary, class-weight) | 0.7870 +- 0.0700 | 0.9633 +- 0.0519 |
| + topology (hand-crafted) | 0.9319 +- 0.0017 | 1.0000 +- 0.0000 |
| + TGN embeddings (learned) | 0.9196 +- 0.0012 | 1.0000 +- 0.0000 |
| **final champion** (topology + TGN, focal(gamma=1.0), HPO) | 0.9364 +- 0.0015 | 1.0000 +- 0.0000 |

## ibm_aml  (test frauds: 377)

| model | test PR-AUC | precision@100 |
|---|---|---|
| baseline (ordinary, class-weight) | 0.9920 +- 0.0026 | 1.0000 +- 0.0000 |
| + topology (hand-crafted) | 1.0000 +- 0.0000 | 1.0000 +- 0.0000 |
| + TGN embeddings (learned) | 0.9872 +- 0.0101 | 1.0000 +- 0.0000 |
| **final champion** (topology + TGN, class_weight, HPO) | 1.0000 +- 0.0000 | 1.0000 +- 0.0000 |

> Caveat: baseline is amount-saturated (PR-AUC ~1.0): margins here are uninformative; see ablation.json amount-blind probes

## sap_wurzburg  (test frauds: 25)

| model | test PR-AUC | precision@100 |
|---|---|---|
| baseline (ordinary, class-weight) | 0.1581 +- 0.0129 | 0.0733 +- 0.0047 |
| + topology (hand-crafted) | 0.0717 +- 0.0095 | 0.0700 +- 0.0216 |
| + TGN embeddings (learned) | 0.0594 +- 0.0241 | 0.0567 +- 0.0287 |
| **final champion** (topology + TGN, focal(gamma=2.0)) | 0.1557 +- 0.0717 | 0.1033 +- 0.0262 |

> Caveat: only 25 test frauds - metrics are high-variance, treat as inconclusive

> Caveat: HPO skipped (validation frauds below guard) - locked default hyperparameters used

## synth_erp  (test frauds: 1093)

| model | test PR-AUC | precision@100 |
|---|---|---|
| baseline (ordinary, class-weight) | 0.2483 +- 0.0602 | 0.8033 +- 0.0801 |
| + topology (hand-crafted) | 0.4569 +- 0.1547 | 0.8933 +- 0.1367 |
| + TGN embeddings (learned) | 0.6972 +- 0.0004 | 0.9933 +- 0.0047 |
| **final champion** (topology + TGN, focal(gamma=1.0), HPO) | 0.7784 +- 0.0053 | 0.9900 +- 0.0000 |

> Caveat: synthetic dataset - sanity/demo only, NEVER thesis evidence (see docs/SYNTHETIC_DATASET.md section 11)
