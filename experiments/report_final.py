"""Consolidated final results table — reads recorded JSONs, re-runs nothing.

Baseline / +topology / +TGN rows come verbatim from results/<ds>/modern.json
(the recorded modernization aggregates); the champion row from
results/<ds>/final.json. Writes results/final_table.md and prints an ASCII table.

Run:  python -m experiments.report_final [datasets ...]
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_DATASETS = ("banksim", "ibm_aml", "sap_wurzburg", "synth_erp")
ROWS = (  # (label, modern.json arm key)  — champion row is added from final.json
    ("baseline (ordinary, class-weight)", "A_cw"),
    ("+ topology (hand-crafted)", "B_cw"),
    ("+ TGN embeddings (learned)", "C_tgn"),
)


def _load(name: str) -> tuple[dict | None, dict | None]:
    out = []
    for fname in ("modern.json", "final.json"):
        p = REPO_ROOT / "results" / name / fname
        out.append(json.loads(p.read_text(encoding="utf-8")) if p.exists() else None)
    return tuple(out)


def _fmt(mean: float, std: float) -> str:
    return f"{mean:.4f} +- {std:.4f}"


def build_report(datasets=DEFAULT_DATASETS) -> str:
    lines = ["# Final consolidated results", "",
             "Test-period metrics, mean +- std over seeds. Baseline/+topology/+TGN "
             "rows are the recorded modernization aggregates (modern.json); the "
             "final row is the promoted champion (final.json).", ""]
    console = []
    for name in datasets:
        modern, final = _load(name)
        if modern is None:
            log.warning("[%s] no modern.json - skipped", name)
            continue
        arms = modern["arms"]
        frauds = modern["summary"]["split_frauds"]["test"]
        lines += [f"## {name}  (test frauds: {frauds})", "",
                  "| model | test PR-AUC | precision@100 |", "|---|---|---|"]
        console.append(f"\n{name}  (test frauds: {frauds})")
        for label, key in ROWS:
            a = arms[key]
            pr = _fmt(a["test_pr_auc_mean"], a["test_pr_auc_std"])
            p100 = _fmt(a["test_precision@100_mean"], a["test_precision@100_std"])
            lines.append(f"| {label} | {pr} | {p100} |")
            console.append(f"  {label:<44} PR-AUC {pr}   p@100 {p100}")
        if final is not None:
            ch = final["champion"]
            label = (f"**final champion** (topology + TGN, {ch['imbalance']}"
                     f"{', HPO' if not final['hpo'][final['selection']['winner']]['hpo_skipped'] else ''})")
            pr = _fmt(ch["test_pr_auc"]["mean"], ch["test_pr_auc"]["std"])
            p100 = _fmt(ch["test_precision@100"]["mean"], ch["test_precision@100"]["std"])
            lines.append(f"| {label} | {pr} | {p100} |")
            console.append(f"  {'FINAL champion (' + ch['imbalance'] + ')':<44} "
                           f"PR-AUC {pr}   p@100 {p100}")
            for c in final.get("caveats", []):
                lines.append(f"\n> Caveat: {c}")
                console.append(f"  CAVEAT: {c}")
        else:
            lines.append("\n> final.json not yet produced for this dataset.")
            console.append("  (final.json missing - run experiments.final)")
        lines.append("")
    report = "\n".join(lines)
    out = REPO_ROOT / "results" / "final_table.md"
    out.write_text(report, encoding="utf-8")
    print("\n".join(console))
    print(f"\nwrote {out}")
    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("datasets", nargs="*", default=list(DEFAULT_DATASETS))
    a = ap.parse_args()
    build_report(tuple(a.datasets))
