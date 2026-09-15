"""Second batch of figures — generated after seeing exactly what the
drafted sections reference. Same house style as generate_figures.py.
Run:  python paper/generate_figures2.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
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
BLUE = "#5C8FD6"
PURPLE = "#8B5FBF"


def _load(name):
    return json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))


def fig_dataset_topology_spectrum():
    cal = _load("calibration_reference")
    fig, ax = plt.subplots(figsize=(5.5, 4))
    labels = {"ibm_aml": "IBM AML", "banksim": "BankSim", "sap_wurzburg": "SAP Würzburg", "paysim": "PaySim"}
    colors = {"ibm_aml": ACCENT, "banksim": MUTED, "sap_wurzburg": ALERT, "paysim": BLUE}
    for ds, d in cal.items():
        g = d.get("graph", {})
        x = g.get("namespace_overlap", 0)
        y = g.get("pair_reciprocity", 0)
        n = g.get("n_transactions", 1)
        size = 200 + 1800 * (n / 6_362_620)
        ax.scatter([x], [y], s=size, alpha=0.55, color=colors.get(ds, MUTED),
                   edgecolors="black", linewidths=0.6, label=labels.get(ds, ds))
        ax.annotate(labels.get(ds, ds), (x, y), textcoords="offset points",
                    xytext=(8, 8), fontsize=8)
    # synth_erp (from realism report, different file)
    realism = _load("synth_erp_realism")
    g = realism.get("graph", {})
    if g:
        x = g.get("namespace_overlap", 0.94)
        y = g.get("pair_reciprocity", 0.14)
        ax.scatter([x], [y], s=800, alpha=0.55, color=PURPLE, edgecolors="black",
                   linewidths=0.6, marker="D")
        ax.annotate("Synth ERP", (x, y), textcoords="offset points", xytext=(8, 8), fontsize=8)
    ax.set_xlabel("Sender/receiver namespace overlap")
    ax.set_ylabel("Pairwise reciprocity")
    ax.set_title("Dataset roster on the topology-richness spectrum\n(bubble area $\\propto$ transaction count)", fontsize=9.5)
    fig.tight_layout()
    fig.savefig(OUT / "dataset_topology_spectrum.png")
    plt.close(fig)


def fig_leakage_timeline():
    fig, axes = plt.subplots(2, 1, figsize=(6.5, 3.2), sharex=True)
    xs = [1, 2, 3, 4, 5]

    ax = axes[0]
    ax.set_title("This paper's engine: read-then-insert", fontsize=9.5, loc="left")
    for i, x in enumerate(xs):
        ax.scatter([x], [0], s=70, color=ACCENT, zorder=3)
        ax.annotate(f"$\\tau_{{{i+1}}}$", (x, 0), textcoords="offset points", xytext=(0, 12), ha="center", fontsize=8)
        ax.annotate("read $\\phi$", (x, 0), textcoords="offset points", xytext=(-14, -18), ha="center", fontsize=6.5, color=MUTED)
        ax.annotate("insert", (x, 0), textcoords="offset points", xytext=(14, -18), ha="center", fontsize=6.5, color=MUTED)
        if i > 0:
            ax.annotate("", xy=(x - 0.15, 0), xytext=(xs[i-1] + 0.15, 0),
                        arrowprops=dict(arrowstyle="->", color=MUTED, lw=0.8))
    ax.set_ylim(-0.6, 0.4)
    ax.axis("off")

    ax = axes[1]
    ax.set_title("Predecessor system: whole-graph attribution (leaky)", fontsize=9.5, loc="left", color=ALERT)
    for i, x in enumerate(xs):
        ax.scatter([x], [0], s=70, color=ALERT, zorder=3)
        ax.annotate(f"$\\tau_{{{i+1}}}$", (x, 0), textcoords="offset points", xytext=(0, 12), ha="center", fontsize=8)
    ax.annotate("", xy=(xs[1], 0.15), xytext=(xs[3], 0.15),
                arrowprops=dict(arrowstyle="<-", color=ALERT, lw=1.2,
                                connectionstyle="arc3,rad=-0.3"))
    ax.annotate("future structure credited\nback to an earlier transaction", (3, 0.32),
                ha="center", fontsize=6.5, color=ALERT)
    ax.set_ylim(-0.3, 0.6)
    ax.axis("off")

    fig.tight_layout()
    fig.savefig(OUT / "leakage_timeline.png")
    plt.close(fig)


def fig_pipeline_overview():
    fig, ax = plt.subplots(figsize=(7, 2.2))
    stages = ["Raw ERP\ntransactions", "Canonical\nETL", "Temporal\ntopology\nengine\n(read-then-insert)",
             "Ordinary +\ntopology\nfeature table", "XGBoost\n(class-weight\nor focal)", "TreeSHAP +\nreplay-verified\nevidence"]
    x = np.arange(len(stages))
    for i, s in enumerate(stages):
        box_color = ACCENT if i == 2 else "#E8ECE9"
        text_color = "white" if i == 2 else "black"
        rect = mpatches.FancyBboxPatch((x[i] - 0.42, -0.35), 0.84, 0.7,
                                        boxstyle="round,pad=0.02", facecolor=box_color,
                                        edgecolor=MUTED, linewidth=0.8)
        ax.add_patch(rect)
        ax.text(x[i], 0, s, ha="center", va="center", fontsize=6.8, color=text_color)
        if i < len(stages) - 1:
            ax.annotate("", xy=(x[i] + 0.48, 0), xytext=(x[i] + 0.42, 0),
                        arrowprops=dict(arrowstyle="->", color=MUTED, lw=1))
    ax.set_xlim(-0.6, len(stages) - 0.4)
    ax.set_ylim(-0.6, 0.6)
    ax.axis("off")
    ax.set_title("End-to-end pipeline (offline research configuration includes a TGN stage\nbetween topology and feature table, omitted from the online-serving path)", fontsize=8.5)
    fig.tight_layout()
    fig.savefig(OUT / "pipeline_overview.png")
    plt.close(fig)


def fig_system_architecture():
    fig, ax = plt.subplots(figsize=(6.5, 4))
    boxes = {
        "ERP clients\n(React console)": (0.5, 3.2, "#E8ECE9"),
        "FastAPI app\n(vendors / invoices /\npayments / alerts)": (0.5, 2.2, "#E8ECE9"),
        "PaymentService\n(5-layer duplicate\ndefence)": (2.3, 2.2, ACCENT),
        "FraudScoringService\n(online)": (2.3, 1.2, ACCENT),
        "OnlineTopologyState\n+ OnlineOrdinaryState\n(same classes as\nbatch pipeline)": (2.3, 0.2, "#E8ECE9"),
        "Postgres\n(triggers: balance,\nperiod-close, audit\nimmutability)": (0.5, 1.0, "#E8ECE9"),
        "Redis\n(idempotency, cache)": (0.5, 0.0, "#E8ECE9"),
    }
    for label, (x, y, color) in boxes.items():
        text_color = "white" if color == ACCENT else "black"
        rect = mpatches.FancyBboxPatch((x - 0.75, y - 0.35), 1.5, 0.7,
                                        boxstyle="round,pad=0.03", facecolor=color,
                                        edgecolor=MUTED, linewidth=0.8)
        ax.add_patch(rect)
        ax.text(x, y, label, ha="center", va="center", fontsize=6.3, color=text_color)

    edges = [
        ("ERP clients\n(React console)", "FastAPI app\n(vendors / invoices /\npayments / alerts)"),
        ("FastAPI app\n(vendors / invoices /\npayments / alerts)", "PaymentService\n(5-layer duplicate\ndefence)"),
        ("PaymentService\n(5-layer duplicate\ndefence)", "FraudScoringService\n(online)"),
        ("FraudScoringService\n(online)", "OnlineTopologyState\n+ OnlineOrdinaryState\n(same classes as\nbatch pipeline)"),
        ("FastAPI app\n(vendors / invoices /\npayments / alerts)", "Postgres\n(triggers: balance,\nperiod-close, audit\nimmutability)"),
        ("FastAPI app\n(vendors / invoices /\npayments / alerts)", "Redis\n(idempotency, cache)"),
    ]
    for a, b in edges:
        xa, ya, _ = boxes[a]
        xb, yb, _ = boxes[b]
        ax.annotate("", xy=(xb, yb + 0.35) if yb < ya else (xb, yb - 0.35),
                    xytext=(xa, ya - 0.35) if yb < ya else (xa, ya + 0.35),
                    arrowprops=dict(arrowstyle="->", color=MUTED, lw=0.8,
                                    connectionstyle="arc3,rad=0.15" if xa != xb else "arc3,rad=0"))

    ax.set_xlim(-0.5, 3.5)
    ax.set_ylim(-0.6, 3.8)
    ax.axis("off")
    ax.set_title("Deployed system architecture", fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / "system_architecture.png")
    plt.close(fig)


def fig_alert_evidence_mix():
    alerts = _load("alerts")
    dss = list(alerts.keys())
    if not dss:
        return
    types = sorted({t for ds in dss for t in alerts[ds]["evidence_type_counts"]})
    fig, ax = plt.subplots(figsize=(5.5, 2.8))
    bottom = np.zeros(len(dss))
    colors = {"cycle": ACCENT, "fan_in": BLUE, "none": MUTED}
    for t in types:
        vals = np.array([alerts[ds]["evidence_type_counts"].get(t, 0) for ds in dss])
        ax.bar(range(len(dss)), vals, bottom=bottom, label=t, color=colors.get(t, "#CCCCCC"))
        bottom += vals
    ax.set_xticks(range(len(dss)))
    labels = {"banksim": "BankSim", "ibm_aml": "IBM AML", "sap_wurzburg": "SAP Würzburg", "synth_erp": "Synth ERP"}
    ax.set_xticklabels([labels.get(ds, ds) for ds in dss])
    ax2 = ax.twinx()
    precisions = [alerts[ds]["precision_at_k"] for ds in dss]
    ax2.plot(range(len(dss)), precisions, "D--", color="black", markersize=5, label="precision@k")
    ax2.set_ylim(0, 1.15)
    ax2.set_ylabel("precision@k")
    ax.set_ylabel("# alerts by evidence type")
    ax.set_title("Alert evidence composition and precision@k by dataset", fontsize=9.5)
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, fontsize=6.5, loc="lower left")
    fig.tight_layout()
    fig.savefig(OUT / "alert_evidence_mix.png")
    plt.close(fig)


def fig_modern_tgn_lift():
    d = _load("modern")
    dss = list(d.keys())
    labels = {"banksim": "BankSim", "ibm_aml": "IBM AML", "sap_wurzburg": "SAP Würzburg", "synth_erp": "Synth ERP"}
    tgn_vs_topo = [d[ds].get("tgn_vs_handcrafted_topology", 0) for ds in dss]
    combined_vs_topo = [d[ds].get("combined_vs_topology", 0) for ds in dss]
    x = np.arange(len(dss))
    width = 0.35
    fig, ax = plt.subplots(figsize=(5.5, 2.8))
    ax.bar(x - width / 2, tgn_vs_topo, width, label="TGN vs. hand-crafted topology",
           color=[ALERT if v < 0 else ACCENT for v in tgn_vs_topo])
    ax.bar(x + width / 2, combined_vs_topo, width, label="Topology+TGN vs. topology alone",
           color=[MUTED if abs(v) < 0.01 else PURPLE for v in combined_vs_topo])
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels([labels.get(ds, ds) for ds in dss])
    ax.set_ylabel("$\\Delta$ test PR-AUC")
    ax.set_title("Learned TGN embeddings never beat hand-crafted topology\non any real dataset", fontsize=9)
    ax.legend(fontsize=6.5)
    fig.tight_layout()
    fig.savefig(OUT / "modern_tgn_lift_by_dataset.png")
    plt.close(fig)


if __name__ == "__main__":
    fig_dataset_topology_spectrum()
    fig_leakage_timeline()
    fig_pipeline_overview()
    fig_system_architecture()
    fig_alert_evidence_mix()
    fig_modern_tgn_lift()
    print(f"figures written to {OUT}")
