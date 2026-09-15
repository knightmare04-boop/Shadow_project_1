---
name: synthetic-erp-generator
description: >-
  Guide for agent-based enterprise economic simulation, behavioral fraud injection,
  statistical calibration against real financial datasets, and empirical realism validation.
  Use when designing synthetic data generators, evaluating simulation realism, or augmenting training sets.
---

# Synthetic ERP Generator & Agent-Based Economic Simulation

This skill details how to design, simulate, calibrate, and validate **synthetic enterprise transaction networks** with realistic benign behavior and goal-oriented fraud injection.

---

## 1. Core Principles: Avoiding the Circularity Trap

### The Circularity Trap
* **Anti-Pattern**: Designing synthetic fraud by writing code that creates the exact mathematical structures your detector looks for (e.g. generating a hardcoded 3-node cycle because you have a 3-node cycle detector).
* **The Solution — Behavioral Simulation**:
  - Model fraud as **agents with goals and evasion tactics** (e.g., an embezzler attempting to siphon $50k while staying below the $10k reporting limit and obscuring vendor relationships).
  - Let graph structures (cycles, chains, fan-ins) emerge naturally from the agent's behavioral logic.
  - The generator code must **never import or reference** the topology feature extractor modules.

---

## 2. Architecture of an Agent-Based Economic Simulator

### 2.1 World Model Entities
1. **Enterprises**: Companies with revenue tiers, departments, cost centers, and payroll cycles.
2. **Vendors**: External suppliers with invoice schedules, payment terms (Net-30/60), and category tags.
3. **Employees**: Staff with approval limits, expense habits, and authorized roles.
4. **Customers**: Consumers or B2B clients with purchase frequency and payment methods.

### 2.2 Benign Transaction Streams
* **Payroll**: Periodic (bi-weekly/monthly), deterministic amounts with low variance.
* **Recurring Vendor Invoices**: Periodic payments with contractual amounts.
* **Operational Expenses**: Poisson process arrivals with log-normal amount distributions.
* **Customer Sales**: High-frequency, day-of-week / hour-of-day seasonal patterns.

### 2.3 Goal-Oriented Fraud Typologies
1. **Invoice Kickback Scheme**:
   - Collusion between an insider employee and an external shell vendor.
   - Flow: Enterprise $\to$ Shell Vendor $\to$ Mule Account $\to$ Employee Personal Account.
2. **Lapping Embezzlement**:
   - Cash received from Customer B is used to credit Customer A's delinquent account.
   - Ongoing rolling chain of compensating entries.
3. **Structuring / Smurfing**:
   - Splitting large illicit funds into amounts below compliance thresholds ($<\$10,000$) across multiple accounts within tight time windows.
4. **Ghost Employee Payroll**:
   - Fictitious employee added to payroll; funds diverted to employee proxy account.
5. **Rapid Dispersion (Layering)**:
   - Account receives high-value deposit, immediately dispersed across 5–10 mule accounts.

---

## 3. Realism Calibration & Validation Battery

### Statistical Realism Verification
Before using synthetic data for model augmentation or pre-training, validate it against real reference datasets (e.g., IBM AML, BankSim, PaySim):

```python
import numpy as np
import pandas as pd
from scipy.stats import ks_2samp

def validate_synthetic_realism(df_real: pd.DataFrame, df_synth: pd.DataFrame) -> dict:
    """Run empirical distribution comparisons between real and synthetic data."""
    results = {}
    
    # 1. Log-Amount Distribution KS-Test
    ks_stat_amt, p_val_amt = ks_2samp(
        np.log1p(df_real["amount"].dropna()),
        np.log1p(df_synth["amount"].dropna())
    )
    results["amount_ks_statistic"] = float(ks_stat_amt)
    results["amount_ks_pvalue"] = float(p_val_amt)
    
    # 2. Inter-arrival Time Distribution
    real_deltas = df_real.sort_values("timestamp").groupby("source")["timestamp"].diff().dropna()
    synth_deltas = df_synth.sort_values("timestamp").groupby("source")["timestamp"].diff().dropna()
    
    ks_stat_time, p_val_time = ks_2samp(real_deltas, synth_deltas)
    results["interarrival_ks_statistic"] = float(ks_stat_time)
    results["interarrival_ks_pvalue"] = float(p_val_time)
    
    # 3. Graph Degree Distribution (In/Out degrees)
    real_in_deg = df_real["destination"].value_counts().values
    synth_in_deg = df_synth["destination"].value_counts().values
    ks_stat_deg, p_val_deg = ks_2samp(real_in_deg, synth_in_deg)
    results["in_degree_ks_statistic"] = float(ks_stat_deg)
    
    # Pass if KS statistics are within acceptable bounds
    results["passed_realism_battery"] = bool(ks_stat_amt < 0.15 and ks_stat_deg < 0.20)
    return results
```

---

## 4. Usage Policy: Augmentation vs. Proof

* **The Proof Rule**: Scientific claims and benchmark results must be proven on **real-world benchmark datasets**.
* **Synthetic Role**:
  - Pre-training neural architectures before fine-tuning on real data.
  - Stress-testing pipeline throughput and scale (millions of edges).
  - Creating reproducible scenario demonstrations where ground truth fraud mechanics are fully auditable.
