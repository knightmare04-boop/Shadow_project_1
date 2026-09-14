"""One-command pipeline driver: etl -> topology -> leakage -> features -> tgn -> final.

Idempotent: each stage is skipped when its output already exists (pass --force to
rebuild). The leakage stage is a hard gate — a failing leakage test aborts the
run (CLAUDE.md rule 4).

Run:  python -m experiments.run_dataset banksim
      python -m experiments.run_dataset banksim --steps features tgn final
      python -m experiments.run_dataset banksim --force --leakage-sample 150000
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

from common.config import get_dataset

log = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[1]

STEPS = ("etl", "topology", "leakage", "features", "tgn", "final")


def main(name: str, steps=STEPS, *, force: bool = False,
         leakage_sample: int | None = 150_000, n_configs: int = 20,
         seeds=(42, 43, 44)) -> None:
    proc = Path(get_dataset(name)["processed_dir"])

    def _skip(step: str, output: Path) -> bool:
        if not force and output.exists():
            log.info("[%s] %s: output exists (%s) - skipped (use --force)",
                     name, step, output.name)
            return True
        return False

    if "etl" in steps and not _skip("etl", proc / "edges_transactions.csv"):
        from etl.build import build_dataset
        build_dataset(name)

    if "topology" in steps and not _skip("topology", proc / "features_topology.csv"):
        from topology.engine import build_topology
        build_topology(name)

    if "leakage" in steps:  # always re-run when requested: it is the gate
        from topology.leakage_test import run_leakage_test
        report = run_leakage_test(name, sample=leakage_sample)
        if not report.get("passed"):
            raise SystemExit(f"[{name}] LEAKAGE TEST FAILED - aborting: {report}")
        log.info("[%s] leakage test passed", name)

    if "features" in steps and not _skip("features", proc / "features_manifest.json"):
        from features.build import build_features
        build_features(name)

    if "tgn" in steps:      # build_embeddings has its own cache (returns early)
        from modeling.tgn import build_embeddings
        build_embeddings(name, force=force)

    if "final" in steps and not _skip(
            "final", REPO_ROOT / "results" / name / "final.json"):
        from experiments.final import run_final
        run_final(name, seeds=tuple(seeds), n_configs=n_configs)

    log.info("[%s] pipeline complete", name)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--steps", nargs="+", default=list(STEPS), choices=STEPS)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--leakage-sample", type=int, default=150_000)
    ap.add_argument("--n-configs", type=int, default=20)
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44])
    a = ap.parse_args()
    main(a.dataset, steps=tuple(a.steps), force=a.force,
         leakage_sample=a.leakage_sample, n_configs=a.n_configs,
         seeds=tuple(a.seeds))
