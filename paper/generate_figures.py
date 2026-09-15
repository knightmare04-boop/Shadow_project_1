"""Generates every data-driven figure the paper cites, from paper/data/*.json
only — matches the harvest script's "every number generated, never
retyped" principle extended to figures. Run after paper/harvest.py.

Run:  python paper/generate_figures.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA = REPO_ROOT / "paper" / "data"
OUT = REPO_ROOT / "paper" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9, "axes.titlesize": 10,
    "axes.labelsize": 9, "figure.dpi": 300, "savefig.dpi": 300,
    "axes.spines.top": False, "axes.spines.right": False,
})
ACCENT = "#00805F"
ALERT = "#C2492A"
MUTED = "#5B6674"
DATASETS = ["banksim", "ibm_aml", "sap_wurzburg", "synth_erp"]
DATASET_LABELS = {"banksim": "BankSim", "ibm_aml": "IBM AML", "sap_wurzburg": "SAP Würzburg", "synth_erp": "Synth ERP"}


def _load(name: str) -> dict:
    return json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))


def fig_ablation_lifts():
    d = _load("ablation")
    metrics = ["marginal_topology_lift", "marginal_structure_lift",
              "amount_blind_topology_lift", "amount_blind_structure_lift"]
    metric_labels = ["Topology\n(full model)", "Structure\n(full model)",
                     "Topology\n(amount-blind)", "Structure\n(amount-blind)"]
    x = np.arange(len(DATASETS))
    width = 0.2
    fig, ax = plt.subplots(figsize=(7, 3.2))
    for i, (m, lbl) in enumerate(zip(metrics, metric_labels)):
        vals = [d[ds][m] for ds in DATASETS]
        colors = [ACCENT if v >= 0 else ALERT for v in vals]
        ax.bar(x + (i - 1.5) * width, vals, width, label=lbl, color=colors, alpha=0.55 + 0.15 * i)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels([DATASET_LABELS[ds] for ds in DATASETS])
    ax.set_ylabel("PR-AUC lift vs. no-topology baseline")
    ax.set_title("Topology lift by dataset (single-seed ablation)")
    ax.legend(fontsize=6.5, ncol=2, loc="upper left", framealpha=0.9)
    fig.tight_layout()
    fig.savefig(OUT / "ablation_lift_by_dataset.png")
    plt.close(fig)


def fig_ablation_arms():
    d = _load("ablation")
    arms = ["baseline_full", "structure_full", "topology_full", "topo_only_full"]
    arm_labels = ["Baseline\n(ordinary only)", "+Structure", "+All topology", "Topology only"]
    fig, axes = plt.subplots(1, 4, figsize=(9, 2.6), sharey=False)
    for ax, ds in zip(axes, DATASETS):
        vals = [d[ds]["arms_detail"][a]["test"]["pr_auc"] for a in arms]
        ax.bar(range(len(arms)), vals, color=[MUTED, ACCENT, ACCENT, "#8FBBAE"])
        ax.set_xticks(range(len(arms)))
        ax.set_xticklabels(arm_labels, fontsize=6, rotation=25, ha="right")
        ax.set_title(DATASET_LABELS[ds], fontsize=9)
        ax.set_ylim(0, 1.05)
        if ds == DATASETS[0]:
            ax.set_ylabel("Test PR-AUC")
    fig.suptitle("Ablation arms: test PR-AUC by feature set", fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / "ablation_arms_by_dataset.png")
    plt.close(fig)


def fig_topology_importance_heatmap():
    d = _load("ablation")
    feats = list(d[DATASETS[0]]["topology_importance"].keys())
    mat = np.array([[d[ds]["topology_importance"].get(f, 0.0) for ds in DATASETS] for f in feats])
    fig, ax = plt.subplots(figsize=(5.5, 5))
    im = ax.imshow(mat, cmap="Greens", aspect="auto", vmin=0, vmax=max(0.1, mat.max()))
    ax.set_xticks(range(len(DATASETS)))
    ax.set_xticklabels([DATASET_LABELS[ds] for ds in DATASETS], fontsize=8)
    ax.set_yticks(range(len(feats)))
    ax.set_yticklabels(feats, fontsize=7)
    for i in range(len(feats)):
        for j in range(len(DATASETS)):
            v = mat[i, j]
            ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                    fontsize=6, color="white" if v > mat.max() * 0.5 else "black")
    ax.set_title("Topology feature gain importance", fontsize=10)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(OUT / "topology_importance_heatmap.png")
    plt.close(fig)


def fig_modern_arms():
    d = _load("modern")
    arms = ["A_cw", "A_focal", "B_cw", "B_focal", "C_tgn", "D_both"]
    fig, axes = plt.subplots(1, 4, figsize=(9.5, 2.8), sharey=False)
    for ax, ds in zip(axes, DATASETS):
        means = [d[ds]["test_pr_auc"][a]["mean"] for a in arms]
        stds = [d[ds]["test_pr_auc"][a]["std"] for a in arms]
        colors = [MUTED, MUTED, ACCENT, ACCENT, "#5C8FD6", "#8B5FBF"]
        ax.bar(range(len(arms)), means, yerr=stds, color=colors, capsize=2)
        ax.set_xticks(range(len(arms)))
        ax.set_xticklabels(arms, fontsize=6.5, rotation=40, ha="right")
        ax.set_title(DATASET_LABELS[ds], fontsize=9)
        ax.set_ylim(0, 1.05)
        if ds == DATASETS[0]:
            ax.set_ylabel("Test PR-AUC (mean ± std, 3 seeds)")
    fig.suptitle("Modernization study: class-weight vs focal vs TGN (3-seed)", fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / "modern_arms_by_dataset.png")
    plt.close(fig)


def fig_synth_realism_bands():
    cal = _load("calibration_reference")
    realism = _load("synth_erp_realism")
    if not cal or not realism:
        return
    metrics = [
        ("fraud_rate", "Fraud rate"),
    ]
    real_vals = {k: [] for k, _ in metrics}
    for ds_name, ds in cal.items():
        for k, _ in metrics:
            if k in ds:
                real_vals[k].append(ds[k])

    fig, ax = plt.subplots(figsize=(5.5, 2.2))
    fr = real_vals["fraud_rate"]
    synth_fr = realism.get("fraud_rate") or realism.get("summary", {}).get("fraud_rate")
    ax.scatter(fr, [0] * len(fr), color=MUTED, s=60, label="Real datasets", zorder=3)
    if synth_fr is not None:
        ax.scatter([synth_fr], [0], color=ALERT, s=90, marker="D", label="Synth ERP", zorder=4)
    ax.set_yticks([])
    ax.set_xlabel("Fraud rate")
    ax.set_title("Synthetic economy fraud rate vs. real dataset band", fontsize=10)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / "synth_realism_fraud_rate.png")
    plt.close(fig)


def fig_augmentation_deltas():
    d = _load("augmentation")
    if not d:
        return
    dss = list(d.keys())
    deltas = [d[ds]["augmentation_delta_pr_auc"]["mean"] for ds in dss]
    errs = [d[ds]["augmentation_delta_pr_auc"]["std"] for ds in dss]
    fig, ax = plt.subplots(figsize=(4.5, 2.6))
    colors = [ALERT if v < 0 else ACCENT for v in deltas]
    ax.bar(range(len(dss)), deltas, yerr=errs, color=colors, capsize=3)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xticks(range(len(dss)))
    ax.set_xticklabels([DATASET_LABELS.get(ds, ds) for ds in dss])
    ax.set_ylabel("Δ PR-AUC (real+synth − real-only)")
    ax.set_title("Synthetic augmentation: all real datasets get worse", fontsize=9.5)
    fig.tight_layout()
    fig.savefig(OUT / "augmentation_deltas.png")
    plt.close(fig)


def fig_online_vs_champion():
    online = _load("online_bundles")
    champ = _load("final_champions")
    dss = [ds for ds in DATASETS if ds in online and ds in champ]
    if not dss:
        return
    online_vals = [online[ds]["test_pr_auc_mean"] for ds in dss]
    champ_vals = [champ[ds]["champion"]["test_pr_auc"]["mean"] for ds in dss]
    x = np.arange(len(dss))
    width = 0.32
    fig, ax = plt.subplots(figsize=(5, 2.6))
    ax.bar(x - width / 2, champ_vals, width, label="Research champion (+TGN)", color="#8B5FBF")
    ax.bar(x + width / 2, online_vals, width, label="Deployed online bundle (no TGN)", color=ACCENT)
    ax.set_xticks(x)
    ax.set_xticklabels([DATASET_LABELS[ds] for ds in dss])
    ax.set_ylabel("Test PR-AUC")
    ax.set_title("Serving-latency cost: online bundle vs. research champion", fontsize=9.5)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / "online_vs_champion.png")
    plt.close(fig)


if __name__ == "__main__":
    fig_ablation_lifts()
    fig_ablation_arms()
    fig_topology_importance_heatmap()
    fig_modern_arms()
    fig_synth_realism_bands()
    fig_augmentation_deltas()
    fig_online_vs_champion()
    print(f"figures written to {OUT}")
