"""modeling — time-aware training, threshold tuning, evaluation, persistence.

Module map:
    harness     time_split (chronological / partition-aware), the honest
                train-and-evaluate loop (ONE imbalance mechanism, val-tuned
                frozen threshold, PR-AUC-first), multi-seed aggregation,
                artifact persistence (bundle schema v2).
    metrics     evaluate() (PR-AUC primary, precision@k/recall@k),
                tune_threshold() (max-F1 on validation).
    objectives  alpha-free focal-loss custom XGBoost objective (rule-1-safe:
                never combined with class weights).
    tgn         CPU temporal-graph-network embedder — label-free, amount-blind,
                zero-lookahead embeddings consumed by the final model.
    hpo         light seeded random search over XGBoost params, selected on
                validation PR-AUC only.
    score       load a persisted bundle and score rows (inference entry point).
    explain     TreeSHAP attributions via xgboost's native pred_contribs.
    alerts      human-readable audit-alert generation (SHAP + graph evidence).

See CLAUDE.md for the non-negotiable methodology rules this package enforces.
"""
