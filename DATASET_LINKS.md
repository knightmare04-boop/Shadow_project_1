# Dataset Links & Acquisition Guide

This repository (*The Self-Auditing Ledger*) evaluates temporal graph topology for financial fraud detection across multiple enterprise and financial transaction datasets.

Per repository policy, raw and processed dataset files are **excluded from version control** due to their size. Instead, download and configure the benchmark datasets using the links and instructions below.

---

## 1. IBM Transactions for Anti-Money Laundering (IBM AML)

* **Dataset Role:** Primary Tier 1 Graph Benchmark (directed multi-hop cycles, money-mule fan-in/fan-out, temporal layering).
* **Primary Source (Kaggle):** [IBM Transactions for Anti Money Laundering (AML)](https://www.kaggle.com/datasets/ealtman2019/ibm-transactions-for-anti-money-laundering-aml)
* **Official Simulator & Generator (GitHub):** [IBM / AMLSim](https://github.com/IBM/AMLSim)
* **Expected Files:**
  * `transactions.csv` (or `HI-Small_Trans.csv` / `LI-Small_Trans.csv`)
  * `accounts.csv`
  * `alerts.csv`
* **Local Placement:**
  Place the extracted files in:
  ```text
  <raw_root>/erp_fraud_data_4(ibm_aml_sim)/
  ```
  *(Configured in `config/datasets.yaml` under `datasets.ibm_aml`)*

---

## 2. BankSim: Synthetic Financial Fraud Simulator

* **Dataset Role:** Tier 1 Bipartite Control (Customer-to-Merchant directed payments; serves as the control group where topological cycles do not exist).
* **Primary Source (Kaggle):** [BankSim: Synthetic data for fraud detection](https://www.kaggle.com/datasets/ealaxi/banksim1)
* **Citation / Paper:** Lopez-Rojas, E. A., & Axelsson, S. (2014). *"BankSim: A bank payment simulation for fraud detection research."* In *Proceedings of the 26th European Modeling and Simulation Symposium (EMSS)*. [ResearchGate Link](https://www.researchgate.net/publication/265736405_BankSim_A_bank_payment_simulation_for_fraud_detection_research)
* **Expected Files:**
  * `bs140513_032310.csv` (approx. 594,643 transactions across 180 simulated steps)
* **Local Placement:**
  Place the CSV file in:
  ```text
  <raw_root>/erp_fraud_data_3(bankSim)/bs140513_032310.csv
  ```
  *(Configured in `config/datasets.yaml` under `datasets.banksim`)*

---

## 3. PaySim: Synthetic Mobile Money Network

* **Dataset Role:** Tier 2 Transfer Graph (6.36 million peer-to-peer and customer-to-merchant mobile money transactions).
* **Primary Source (Kaggle):** [PaySim: Synthetic Financial Datasets For Fraud Detection](https://www.kaggle.com/datasets/ealaxi/paysim1)
* **Citation / Paper:** Lopez-Rojas, E. A., Elmir, A., & Axelsson, S. (2016). *"PaySim: A financial mobile money simulator for fraud detection."* In *Proceedings of the 28th European Modeling and Simulation Symposium (EMSS)*.
* **Expected Files:**
  * `PS_20174392719_1491204439457_log.csv`
* **Local Placement:**
  Place the file in:
  ```text
  <raw_root>/erp_fraud_data_5(mobile)/PS_20174392719_1491204439457_log.csv
  ```
  *(Configured in `config/datasets.yaml` under `datasets.paysim`)*

---

## 4. SAP ERP Würzburg Dataset (Synthetic ERPsim General Ledger)

* **Dataset Role:** Tier 2 ERP Double-Entry Ledger (SAP ERP general ledger postings joined across `RBKP`, `RSEG`, `BKPF`, and `BSEG` tables; evaluated via a bipartite Document $\leftrightarrow$ Account projection).
* **Primary Repository & Download:** [University of Würzburg Data Science Chair — ERP Fraud Data](https://professor-x.de/erp-fraud-data)
* **Academic Host:** Julius-Maximilians-Universität Würzburg, Chair of Business Informatics and Data Science.
* **Expected Files (under `joint_datasets/`):**
  * `fraud_1.csv`
  * `fraud_2.csv`
  * `fraud_3.csv`
  * `normal_1.csv`
  * `normal_2.csv`
* **Local Placement:**
  Place the 5 CSVs in:
  ```text
  <raw_root>/erp_fraud_data_1(wurzburg)/erp_fraud_data/joint_datasets/
  ```
  *(Configured in `config/datasets.yaml` under `datasets.sap_wurzburg`)*

---

## 5. Synthetic Calibrated ERP Economy (`synth_erp`)

* **Dataset Role:** Agent-based economic simulation calibrated against empirical enterprise ledger parameters. Includes 5 behavioral fraud typologies (laundering cycles, mule fan-ins, lapping cascades, invoice kickbacks, larceny) generated with evasive behavior rather than hardcoded pattern rules.
* **How to Obtain / Generate:**
  This dataset is generated directly within this repository using deterministic random seeds and verified via SHA-256 manifests.
* **Generation Command:**
  ```bash
  python -m synth.generate
  ```
  The generator reads parameters from [`config/synthetic.yaml`](config/synthetic.yaml) and outputs:
  * `transactions.csv` (1,010,000 transactions across 365 simulated days)
  * `accounts.csv` (~39,000 economic agents/accounts)
  * `alerts.csv` (typology ground truth for evaluation)
  * `generation_manifest.json` (SHA-256 checksums verifying reproducibility)
* **Output Placement:**
  Generated in `<raw_root>/synthetic_erp_v1/` or `data/raw/synthetic_erp_v1/`.

---

## 6. Bank Account Fraud (BAF / FIFAR) — Tabular Baseline Reference

* **Dataset Role:** NeurIPS 2022 Tabular Applicant Fraud Benchmark (Evaluated as a non-graph tabular control to test learning-to-defer and tabular-only baselines).
* **Primary Source (Kaggle):** [Bank Account Fraud Dataset Suite (NeurIPS 2022)](https://www.kaggle.com/datasets/sgpjesus/bank-account-fraud-dataset-neurips-2022)
* **Citation / Paper:** Jesus, S. et al. (2022). *"Turning the Tables: Biased, Imbalanced, Dynamic Tabular Datasets for ML Evaluation."* In *Advances in Neural Information Processing Systems (NeurIPS 2022)*.
* **Local Placement:**
  ```text
  <raw_root>/erp_fraud_data_6(fifar)/ICAIF_KAGGLE/
  ```

---

## Quick Setup Guide

1. **Configure the Data Root:**
   Open [`config/datasets.yaml`](config/datasets.yaml) and set `raw_root` to point to the local directory where your downloaded datasets reside:
   ```yaml
   raw_root: "C:/path/to/your/erp_datasets"
   processed_root: "data/processed"
   ```

2. **Run Canonical ETL:**
   Ingest and construct the canonical temporal graph representations:
   ```bash
   python -m etl.build --all
   ```

3. **Extract Temporal Topology Features:**
   ```bash
   python -m features.build --all
   ```

4. **Run Benchmark Experiments:**
   ```bash
   python -m experiments.final --all
   ```
