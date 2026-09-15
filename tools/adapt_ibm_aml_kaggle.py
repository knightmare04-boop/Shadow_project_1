"""Adapter: Kaggle's IBM AML export (``ealtman2019/...``, e.g. ``HI-Small_Trans.csv``)
-> the canonical raw schema this repo's ETL expects for a ``transfer``-kind dataset.

This is NOT the same simulator instance that produced the committed results in
``results/ibm_aml/`` (that was AMLSim's own ``transactions.csv`` with columns
TX_ID/SENDER_ACCOUNT_ID/RECEIVER_ACCOUNT_ID/TX_AMOUNT/TIMESTAMP/TX_TYPE/IS_FRAUD/
ALERT_ID and an integer 0..199 day counter). The Kaggle export has a different
row count, a different column layout, no alert-typology file, and a plain
datetime string per row. Everything built from this file is registered under
the SEPARATE dataset key ``ibm_aml_kaggle`` (see config/datasets.yaml) and is
reported in the paper as a reproduction check — never merged into the
headline ibm_aml numbers.

Column mapping:
    Timestamp                       -> continuous integer seconds since the
                                        dataset's first transaction (NOT
                                        day-bucketed: at 5M+ rows, collapsing to
                                        day granularity would create massive
                                        false ties and destroy the topology
                                        engine's within-day ordering guarantees)
    From Bank + Account (1st)       -> SENDER_ACCOUNT_ID   ("<bank>_<account>",
                                        since the raw account code alone is not
                                        guaranteed unique across banks)
    To Bank   + Account (2nd, ".1") -> RECEIVER_ACCOUNT_ID  (same scheme)
    Amount Paid                     -> TX_AMOUNT (sender-side amount, matching
                                        AMLSim's TX_AMOUNT convention)
    Payment Format                  -> TX_TYPE (categorical; ~6-8 distinct
                                        values, one-hot-eligible)
    Is Laundering                   -> IS_FRAUD

No ALERT_ID / accounts.csv / alerts.csv: the Kaggle export carries no fraud
typology or account-attribute file. Both are optional in src/etl/build.py.

Run:  python tools/adapt_ibm_aml_kaggle.py
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "data" / "raw" / "erp_fraud_data_4(ibm_aml_sim)_kaggle_raw" / "HI-Small_Trans.csv"
DST_DIR = REPO_ROOT / "data" / "raw" / "erp_fraud_data_4(ibm_aml_sim)_kaggle"
DST_FILE = DST_DIR / "transactions.csv"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def adapt() -> dict:
    t0 = time.time()
    if not SRC.exists():
        raise FileNotFoundError(f"expected Kaggle export at {SRC} — run the download first")

    log.info("reading %s", SRC)
    raw = pd.read_csv(
        SRC,
        dtype={
            "From Bank": "string", "To Bank": "string",
            "Amount Received": "float64", "Amount Paid": "float64",
            "Receiving Currency": "category", "Payment Currency": "category",
            "Payment Format": "category", "Is Laundering": "int8",
        },
        parse_dates=["Timestamp"],
    )
    log.info("read %d rows, columns: %s", len(raw), list(raw.columns))

    # pandas mangles the duplicate "Account" header to "Account" + "Account.1"
    # (first = sender-side under "From Bank", second = receiver-side under "To Bank").
    cols = list(raw.columns)
    acct_cols = [c for c in cols if c == "Account" or c.startswith("Account.")]
    if len(acct_cols) != 2:
        raise ValueError(f"expected exactly 2 'Account' columns after mangling, got {acct_cols}")
    src_acct_col, dst_acct_col = acct_cols[0], acct_cols[1]

    out = pd.DataFrame()
    out["TX_ID"] = range(len(raw))
    out["SENDER_ACCOUNT_ID"] = raw["From Bank"].astype(str) + "_" + raw[src_acct_col].astype(str)
    out["RECEIVER_ACCOUNT_ID"] = raw["To Bank"].astype(str) + "_" + raw[dst_acct_col].astype(str)
    out["TX_AMOUNT"] = raw["Amount Paid"]

    ts = raw["Timestamp"]
    t_min = ts.min()
    out["TIMESTAMP"] = (ts - t_min).dt.total_seconds().astype("int64")

    out["TX_TYPE"] = raw["Payment Format"].astype(str)
    out["IS_FRAUD"] = raw["Is Laundering"].astype("int8")

    # Chronological order matches the streaming engine's assumption (stable
    # sort in etl/build.py re-sorts anyway, but writing it sorted keeps the
    # intermediate file itself inspectable in time order).
    out = out.sort_values("TIMESTAMP", kind="stable").reset_index(drop=True)

    DST_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(DST_FILE, index=False)

    n_fraud = int(out["IS_FRAUD"].sum())
    n = len(out)
    s = set(out["SENDER_ACCOUNT_ID"])
    r = set(out["RECEIVER_ACCOUNT_ID"])
    manifest = {
        "source_file": str(SRC),
        "source_sha256": _sha256(SRC),
        "output_file": str(DST_FILE),
        "n_transactions": n,
        "n_fraud": n_fraud,
        "fraud_rate": round(n_fraud / n, 6) if n else 0.0,
        "n_unique_senders": len(s),
        "n_unique_receivers": len(r),
        "n_unique_accounts": len(s | r),
        "namespace_overlap": round(len(s & r) / max(len(s | r), 1), 4),
        "timestamp_span_seconds": int(out["TIMESTAMP"].max()),
        "first_timestamp_utc": str(t_min),
        "tx_type_distribution": raw["Payment Format"].value_counts().to_dict(),
        "elapsed_seconds": round(time.time() - t0, 1),
        "note": (
            "Reproduction dataset from Kaggle ealtman2019 HI-Small_Trans.csv — "
            "NOT the same simulator instance behind the committed results/ibm_aml/ "
            "metrics. Registered as the separate 'ibm_aml_kaggle' dataset."
        ),
    }
    with open(DST_DIR / "adaptation_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, default=str)

    log.info("wrote %d rows (%d fraud, rate=%.6f) -> %s in %.1fs",
              n, n_fraud, manifest["fraud_rate"], DST_FILE, manifest["elapsed_seconds"])
    return manifest


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    m = adapt()
    print(json.dumps(m, indent=2, default=str))
