"""generate — orchestrate the synthetic ERP economy and write the raw dataset.

Output layout (under ``<raw_root>/<out_subdir>/``, mirroring IBM AML's raw
layout so the standard `transfer` ETL path ingests it unchanged):

    transactions.csv          TX_ID, TIMESTAMP, SOURCE_ACCOUNT, DEST_ACCOUNT,
                              AMOUNT, TX_TYPE, IS_FRAUD, ALERT_ID
    accounts.csv              ACCOUNT_ID, role, creation_day
    alerts.csv                TX_ID, ALERT_TYPE       (fraud typology, eval-only)
    scenarios.json            one provenance record per fraud scenario
    generation_manifest.json  version, seed, full config echo, per-flow counts,
                              SHA-256 of every CSV -> full reproducibility

Reproducibility contract: the dataset is a pure function of
(config/synthetic.yaml, seed, this package's code). Rerunning with the same
three produces byte-identical CSVs (hashes in the manifest prove it).

Run:  python -m synth.generate            # uses config/synthetic.yaml
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from common.config import load_config
from synth.base import DAY, EventBuffer, load_synth_config
from synth.fraud import generate_fraud
from synth.normal import generate_normal
from synth.world import World

log = logging.getLogger(__name__)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def generate(config_path: str | None = None) -> dict:
    t0 = time.time()
    cfg = load_synth_config(config_path)
    rng = np.random.default_rng(cfg["seed"])
    horizon = int(cfg["days"]) * DAY

    out_dir = Path(load_config()["raw_root"]) / cfg["out_subdir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    log.info("building world (seed=%s)", cfg["seed"])
    world = World(cfg, rng)

    buf = EventBuffer()
    log.info("generating normal behaviors")
    normal_counts = generate_normal(world, buf, rng)
    log.info("normal flows: %s", normal_counts)

    log.info("generating fraud scenarios")
    scenarios = generate_fraud(world, buf, rng)

    # ---- assemble, clip to the year, sort by time, assign ids ----------------
    cols = buf.arrays()
    df = pd.DataFrame(cols)
    df = df[(df["TIMESTAMP"] >= 0) & (df["TIMESTAMP"] < horizon)]
    df = df.sort_values("TIMESTAMP", kind="stable").reset_index(drop=True)
    df.insert(0, "TX_ID", np.arange(len(df), dtype=np.int64))
    df["IS_FRAUD"] = (df["ALERT_TYPE"] != "").astype(np.int8)

    # ---- write ----------------------------------------------------------------
    tx_path = out_dir / "transactions.csv"
    df.drop(columns=["ALERT_TYPE"]).to_csv(tx_path, index=False)

    alerts = df.loc[df["IS_FRAUD"] == 1, ["TX_ID", "ALERT_TYPE"]]
    alerts_path = out_dir / "alerts.csv"
    alerts.to_csv(alerts_path, index=False)

    acc = pd.DataFrame(
        [{"ACCOUNT_ID": k, "role": v["role"], "creation_day": v["creation_day"]}
         for k, v in world.accounts.items()]
    )
    acc_path = out_dir / "accounts.csv"
    acc.to_csv(acc_path, index=False)

    with open(out_dir / "scenarios.json", "w", encoding="utf-8") as f:
        json.dump(scenarios, f, indent=2)

    typology_counts = alerts["ALERT_TYPE"].value_counts().to_dict()
    manifest = {
        "generator": "synth " + str(cfg["version"]),
        "generated_on": str(date.today()),
        "seed": cfg["seed"],
        "days": cfg["days"],
        "n_transactions": int(len(df)),
        "n_accounts": int(len(acc)),
        "n_fraud": int(df["IS_FRAUD"].sum()),
        "fraud_rate": round(float(df["IS_FRAUD"].mean()), 6),
        "normal_flow_counts": normal_counts,
        "fraud_typology_counts": {k: int(v) for k, v in typology_counts.items()},
        "n_scenarios": len(scenarios),
        "runtime_sec": round(time.time() - t0, 1),
        "sha256": {p.name: _sha256(p) for p in (tx_path, alerts_path, acc_path)},
        "config": cfg,   # full echo: (config, seed, code) => byte-identical rerun
    }
    with open(out_dir / "generation_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    log.info("wrote %d txns (%d fraud, rate %.4f%%), %d accounts -> %s  [%.1fs]",
             len(df), manifest["n_fraud"], 100 * manifest["fraud_rate"],
             len(acc), out_dir, manifest["runtime_sec"])
    return manifest


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    m = generate(sys.argv[1] if len(sys.argv) > 1 else None)
    print(json.dumps({k: v for k, v in m.items() if k != "config"}, indent=2))
