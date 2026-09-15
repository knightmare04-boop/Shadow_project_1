---
name: erp-ledger-accounting
description: >-
  Expert guide for double-entry bookkeeping, SAP general ledger (G/L) structures,
  bipartite document-account graph projections, Segregation of Duties (SoD), and accounting anomaly detection.
  Use when analyzing accounting data, SAP ERP tables, or internal financial controls.
---

# ERP Accounting & General Ledger Audit Analytics

This skill provides domain knowledge, structural modeling patterns, and internal control rules for analyzing **Enterprise Resource Planning (ERP)** financial data, SAP double-entry accounting ledgers, and forensic audit anomalies.

---

## 1. Accounting Foundations: Double-Entry Bookkeeping

### The Accounting Equation & Invariants
$$\text{Assets} = \text{Liabilities} + \text{Equity}$$
$$\sum \text{Debits} = \sum \text{Credits} \quad (\text{per transaction document})$$

* **Debit ($Dr$)**: Increases Assets and Expenses; Decreases Liabilities, Equity, and Revenue.
* **Credit ($Cr$)**: Increases Liabilities, Equity, and Revenue; Decreases Assets and Expenses.
* **Invariant Check**: In any legitimate accounting entry, the sum of debits across all posting lines for a document MUST equal the sum of credits. Unbalanced postings represent corrupted data or illicit ledger manipulation.

---

## 2. SAP Ledger Table Architecture

In enterprise SAP systems (e.g., S/4HANA or SAP ECC), financial postings are recorded across document headers and line items:

| Table | Name | Key Columns | Purpose |
| :--- | :--- | :--- | :--- |
| **`BKPF`** | Accounting Document Header | `BUKRS` (Company Code), `BELNR` (Doc No), `GJAHR` (Fiscal Year), `BLDAT` (Doc Date), `USNAM` (User) | Captures who posted the entry, when, and document type. |
| **`BSEG`** | Accounting Document Segment (Lines) | `BELNR`, `BUZEI` (Line No), `HKONT` (G/L Account), `SHKZG` (Debit/Credit indicator), `DMBTR` (Amount), `LIFNR` (Vendor), `KUNNR` (Customer) | Captures individual financial movements across General Ledger accounts. |

---

## 3. Bipartite Document-Account Graph Modeling

Because double-entry ledgers do not have direct "sender-to-receiver" columns, we model transactions as a **bipartite graph**:

```
      [ Document Doc_1001 ]
        /              \
       / (Debit $50k)   \ (Credit $50k)
      ▼                  ▼
[ G/L: 160000 Inventory ]   [ G/L: 200000 Accounts Payable ]
```

* **Document Nodes**: Each distinct transaction document `BELNR`.
* **Account Nodes**: General Ledger (G/L) accounts `HKONT` (e.g., Cash, Accounts Receivable, Inventory, Expense, Payable).
* **Edges**: Posting lines connecting Document $\leftrightarrow$ Account with direction dictated by $Dr/Cr$ and carrying the line amount.

---

## 4. Forensic Accounting Anomaly Patterns

### 4.1 Segregation of Duties (SoD) Violations
An internal control violation occurs when a single user identifier controls conflicting lifecycle steps:
* Same user creates vendor master record and approves invoice.
* Same user creates purchase order (`PO`), issues goods receipt (`GR`), and enters invoice receipt (`IR`) (violating the 3-Way Match rule).
* Same user enters journal entry and executes payment run.

### 4.2 Larceny & Skimming
* **Skimming**: Theft of cash before it is entered into the accounting system (off-book).
* **Larceny**: Theft of cash after it has been recorded on the company's books. Often accompanied by fraudulent credit adjustments to write off missing balances.

### 4.3 Fictitious Vendor / Invoice Kickbacks
* Sequential invoice numbers from a single vendor with no prior history.
* Invoices just below internal approval thresholds (e.g., \$9,900 vs \$10,000 threshold).
* Vendor address matches employee residential address or bank details match employee routing numbers.

---

## 5. Ledger Extraction & Graph Processing (Python)

```python
import pandas as pd
import numpy as np

def process_sap_bipartite_ledger(df_bseg: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Convert SAP ledger line items into canonical bipartite graph edges and accounts."""
    # Ensure Debit/Credit amounts
    df = df_bseg.copy()
    df["signed_amount"] = np.where(df["SHKZG"] == "S", df["DMBTR"], -df["DMBTR"])
    
    # 1. Document Balance Verification (Debits == Credits)
    doc_balances = df.groupby("BELNR")["signed_amount"].sum()
    unbalanced_docs = doc_balances[doc_balances.abs() > 0.01]
    if not unbalanced_docs.empty:
        print(f"Warning: Found {len(unbalanced_docs)} unbalanced accounting documents.")

    # 2. Canonical Edge Table: Document <-> G/L Account
    edges = pd.DataFrame({
        "transaction_id": df["BELNR"].astype(str) + "_" + df["BUZEI"].astype(str),
        "source": np.where(df["SHKZG"] == "S", "DOC_" + df["BELNR"].astype(str), "GL_" + df["HKONT"].astype(str)),
        "destination": np.where(df["SHKZG"] == "S", "GL_" + df["HKONT"].astype(str), "DOC_" + df["BELNR"].astype(str)),
        "amount": df["DMBTR"].astype(float),
        "timestamp": df["BLDAT_TIMESTAMP"],
        "document_type": df.get("BLART", "SA"),
        "is_fraud": df.get("LABEL", 0)
    })
    
    # 3. Canonical Nodes Table
    doc_nodes = pd.DataFrame({"id": "DOC_" + df["BELNR"].unique(), "node_type": "DOCUMENT"})
    gl_nodes = pd.DataFrame({"id": "GL_" + df["HKONT"].unique(), "node_type": "GL_ACCOUNT"})
    nodes = pd.concat([doc_nodes, gl_nodes], ignore_index=True)
    
    return edges, nodes
```
