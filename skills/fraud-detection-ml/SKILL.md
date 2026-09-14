---
name: fraud-detection-ml
description: >-
  Methodology guide for imbalanced machine learning, fraud detection risk modeling,
  time-aware validation, validation threshold tuning, PR-AUC evaluation, and ablation testing.
  Use when designing, training, evaluating, or auditing tabular ML models on rare-event data.
---

# Imbalanced Fraud Detection ML & Leakage-Free Evaluation

This skill defines the methodology, modeling patterns, and evaluation rigor required for financial fraud detection and rare-event machine learning.

---

## 1. The Core Methodology Rules

### Rule 1: Single Imbalance Mechanism (Never Combine)
* When target prevalence is $<1\%$, use **class weights** (e.g., `scale_pos_weight = (N_neg / N_pos)` in XGBoost / LightGBM).
* **Do NOT combine SMOTE and class weights**: Double-counting distortions destroy calibration.
* **Avoid SMOTE for graph/topological features**: Synthetically interpolating between discrete graph topologies (e.g., "half a 3-hop cycle") creates non-physical feature vectors.

### Rule 2: Chronological / Time-Aware Splits (Never Randomly Shuffle)
* Financial transaction data is non-stationary. Models must predict the future using the past.
* Split data strictly on chronological boundaries:
  - **Train**: $t \in [0, T_{\text{train}}]$
  - **Validation**: $t \in (T_{\text{train}}, T_{\text{val}}]$
  - **Test**: $t \in (T_{\text{val}}, T_{\text{test}}]$
* For partitioned runs (e.g. per-enterprise or cross-sectional runs), perform within-partition chronological splits.

### Rule 3: Validation-Tuned & Frozen Decision Cutoff
* Never assume the arbitrary `0.5` probability cutoff.
* Optimize the decision threshold $\tau^*$ on the **Validation Set** to maximize $F_1$ or satisfy operational precision/recall constraints.
* **Freeze $\tau^*$** before evaluating on the Test Set.

### Rule 4: Proper Metrics for Extreme Imbalance
* **Primary Metric**: **PR-AUC** (Average Precision). Reflects precision across recall levels on the rare positive class.
* **Operational Metric**: **Precision@k** and **Recall@k** (where $k$ is the auditor alert review capacity, e.g., top 50, 100, 500 alerts).
* **De-emphasized**: ROC-AUC and standard Accuracy (both look deceptively high on 99.9% negative datasets).

---

## 2. Training & Evaluation Pipeline

```python
import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_curve, auc, f1_score, precision_score, recall_score
import xgboost as xgb

def train_and_evaluate_fraud_model(
    df: pd.DataFrame,
    feature_cols: list[str],
    target_col: str = "is_fraud",
    time_col: str = "timestamp",
    train_frac: float = 0.70,
    val_frac: float = 0.15,
):
    # 1. Chronological Sorting & Splitting
    df_sorted = df.sort_values(time_col).reset_index(drop=True)
    n = len(df_sorted)
    i_train = int(n * train_frac)
    i_val = int(n * (train_frac + val_frac))
    
    df_train = df_sorted.iloc[:i_train]
    df_val = df_sorted.iloc[i_train:i_val]
    df_test = df_sorted.iloc[i_val:]
    
    X_train, y_train = df_train[feature_cols], df_train[target_col].values
    X_val, y_val = df_val[feature_cols], df_val[target_col].values
    X_test, y_test = df_test[feature_cols], df_test[target_col].values
    
    # 2. Imbalance Ratio
    scale_pos = (len(y_train) - y_train.sum()) / max(y_train.sum(), 1)
    
    # 3. Model Fit with Early Stopping on Validation PR-AUC
    model = xgb.XGBClassifier(
        n_estimators=1000,
        learning_rate=0.03,
        max_depth=6,
        scale_pos_weight=scale_pos,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="aucpr",
        early_stopping_rounds=50,
        random_state=42,
    )
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        verbose=False
    )
    
    # 4. Predict Probabilities
    val_probs = model.predict_proba(X_val)[:, 1]
    test_probs = model.predict_proba(X_test)[:, 1]
    
    # 5. Tune Decision Threshold on Validation Only
    precisions, recalls, thresholds = precision_recall_curve(y_val, val_probs)
    f1_scores = 2 * (precisions * recalls) / np.maximum(precisions + recalls, 1e-9)
    best_idx = np.argmax(f1_scores[:-1])
    frozen_threshold = thresholds[best_idx]
    
    # 6. Evaluate on Test Set
    test_preds = (test_probs >= frozen_threshold).astype(int)
    p_curve, r_curve, _ = precision_recall_curve(y_test, test_probs)
    test_pr_auc = auc(r_curve, p_curve)
    
    # Precision@K Metrics
    k_targets = [50, 100, 500]
    pk_metrics = {}
    top_k_indices = np.argsort(test_probs)[::-1]
    for k in k_targets:
        if k <= len(y_test):
            top_k_labels = y_test[top_k_indices[:k]]
            pk_metrics[f"precision@{k}"] = top_k_labels.mean()
            pk_metrics[f"recall@{k}"] = top_k_labels.sum() / max(y_test.sum(), 1)
            
    return {
        "model": model,
        "frozen_threshold": float(frozen_threshold),
        "test_pr_auc": float(test_pr_auc),
        "test_f1": float(f1_score(y_test, test_preds, zero_division=0)),
        "test_precision": float(precision_score(y_test, test_preds, zero_division=0)),
        "test_recall": float(recall_score(y_test, test_preds, zero_division=0)),
        "precision_recall_at_k": pk_metrics,
    }
```

---

## 3. The Scientific Ablation Protocol

To prove whether graph/topological features add genuine signal beyond ordinary tabular features:

| Arm | Feature Set | Description |
| :--- | :--- | :--- |
| **(A) Tabular Baseline** | Amounts, account rolling statistics, frequency | Measures standard tabular predictive capability. |
| **(B) Full Model** | Tabular + All Topology (Structure + Amount-derived) | Standard combined pipeline. |
| **(C) Clean Structure Lift** | Tabular + Pure Structure (`in_cycle`, `fan_in`, `degrees`) | Isolates topology from amount contamination. |
| **(D) Amount-Blind Probe** | Pure Topology Only (No amounts in baseline or topology) | Proves structural signal in amount-evasive fraud. |

### Interpretation Rules
* Report **both positive and negative outcomes** transparently.
* If Arm B beats Arm A with statistical significance across random seeds/splits, topology provides genuine predictive lift.
* If Arm B shows no improvement, report the honest negative finding: domain-specific structural features do not beat amount statistics on that dataset.
