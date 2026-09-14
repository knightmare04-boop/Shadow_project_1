import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

os.makedirs('artifacts/report_figures', exist_ok=True)

plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['font.size'] = 9

def generate_gantt_chart():
    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=300)
    
    tasks = [
        "Task 8: Review & Final Submission",
        "Task 7: Full Documentation & Project Report",
        "Task 6: Explainable Audit Alert Dispatch & Neo4j",
        "Task 5: Systematic Multi-Seed Ablation Study",
        "Task 4: Hybrid Modeling (Cost-Sensitive XGB+TGN)",
        "Task 3: Streaming Zero-Lookahead Topology Engine",
        "Task 2: Dataset Acquisition & Canonical ETL",
        "Task 1: Literature Survey & Research Gap Study"
    ]
    
    # Start and duration in weeks (Total: 16 weeks)
    starts = [15, 14, 12, 10, 7, 4, 2, 0]
    durations = [1, 2, 3, 2, 4, 4, 3, 3]
    colors = ['#1A365D', '#2B6CB0', '#3182CE', '#2B6CB0', '#2C7A7B', '#319795', '#4FD1C5', '#4A5568']
    
    y_pos = np.arange(len(tasks))
    
    for i, (task, start, dur, col) in enumerate(zip(tasks, starts, durations, colors)):
        ax.barh(y_pos[i], dur, left=start, height=0.55, align='center',
                color=col, edgecolor='#1A202C', linewidth=1.2, zorder=3)
        ax.text(start + dur/2, y_pos[i], f"{dur} Wks", ha='center', va='center',
                color='white', fontweight='bold', fontsize=8, zorder=4)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(tasks, fontweight='bold', fontsize=9, color='#1A202C')
    ax.set_xlabel('Project Timeline (Weeks / Months: June 2026 - September 2026)', fontweight='bold', fontsize=10, labelpad=8)
    ax.set_xlim(-0.5, 16.5)
    ax.set_xticks(range(0, 17, 2))
    ax.set_xticklabels([f"Wk {w}" if w > 0 else "Start" for w in range(0, 17, 2)], fontsize=9)
    
    # Milestone indicators
    milestones = [3, 5, 8, 11, 13, 15, 16]
    milestone_labels = ['M1: Survey', 'M2: ETL', 'M3: Engine', 'M4: Model', 'M5: Ablation', 'M6: Alert', 'M7: Final']
    for m, lbl in zip(milestones, milestone_labels):
        ax.axvline(x=m, color='#CBD5E0', linestyle='--', linewidth=0.9, zorder=1)
        ax.text(m, 7.6, lbl, rotation=45, ha='left', va='bottom', fontsize=7.5, color='#4A5568', fontweight='bold')

    ax.grid(axis='x', linestyle=':', color='#E2E8F0', zorder=0)
    ax.set_title("Fig. 1. BCSE497J Project-I Implementation Gantt Chart", fontweight='bold', fontsize=12, pad=35, color='#1A365D')
    
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#CBD5E0')
    ax.spines['bottom'].set_color('#CBD5E0')
    
    plt.tight_layout()
    plt.savefig('artifacts/report_figures/fig1_gantt_chart.png', dpi=300)
    plt.close()
    print("Saved fig1_gantt_chart.png")

def generate_system_architecture():
    fig, ax = plt.subplots(figsize=(11, 6.5), dpi=300)
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 7)
    ax.axis('off')

    # Draw Stage Containers
    stages = [
        ("STAGE 1: Ingestion & Canonical ETL", 0.5, 0.5, 2.2, 5.8, '#EBF8FF', '#3182CE'),
        ("STAGE 2: Zero-Lookahead Topology", 3.0, 0.5, 2.4, 5.8, '#E6FFFA', '#319795'),
        ("STAGE 3: Hybrid Classifier & TGN", 5.7, 0.5, 2.4, 5.8, '#EDF2F7', '#4A5568'),
        ("STAGE 4: Dual-Layer Explainability", 8.4, 0.5, 2.2, 5.8, '#FEFCBF', '#D69E2E')
    ]

    for title, x, y, w, h, bg, border in stages:
        rect = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.08,rounding_size=0.15",
                                      facecolor=bg, edgecolor=border, linewidth=1.8)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h - 0.35, title, ha='center', va='center',
                fontweight='bold', fontsize=8.5, color='#1A202C')

    # Stage 1 Sub-boxes
    s1_items = [
        ("Raw Financial Sources\n(SAP BKPF/BSEG,\nBankSim, IBM AML)", 0.65, 4.3, 1.9, 1.3),
        ("Canonical Data Normalizer\n(Type check, quote strip,\ntime axis alignment)", 0.65, 2.6, 1.9, 1.3),
        ("Unified Account Graph\n(Resolves sender/receiver\ninto shared Account nodes)", 0.65, 0.9, 1.9, 1.3)
    ]
    for text, ix, iy, iw, ih in s1_items:
        box = patches.FancyBboxPatch((ix, iy), iw, ih, boxstyle="round,pad=0.05,rounding_size=0.1",
                                     facecolor='#FFFFFF', edgecolor='#3182CE', linewidth=1.2)
        ax.add_patch(box)
        ax.text(ix + iw/2, iy + ih/2, text, ha='center', va='center', fontsize=7.5, color='#2D3748', multialignment='center')

    # Stage 2 Sub-boxes
    s2_items = [
        ("Streaming Ingestion Engine\n(Chronological event queue,\nstrict t <= T invariant)", 3.15, 4.3, 2.1, 1.3),
        ("Temporal Sliding Windows\n(1h, 24h, 7d horizons;\nPast-only rolling stats)", 3.15, 2.6, 2.1, 1.3),
        ("Topological Detectors\n- Directed Cycles (2-3 hop)\n- Fan-In/Out Collection Hubs\n- Burst Transfer Velocity", 3.15, 0.9, 2.1, 1.3)
    ]
    for text, ix, iy, iw, ih in s2_items:
        box = patches.FancyBboxPatch((ix, iy), iw, ih, boxstyle="round,pad=0.05,rounding_size=0.1",
                                     facecolor='#FFFFFF', edgecolor='#319795', linewidth=1.2)
        ax.add_patch(box)
        ax.text(ix + iw/2, iy + ih/2, text, ha='center', va='center', fontsize=7.5, color='#2D3748', multialignment='center')

    # Stage 3 Sub-boxes
    s3_items = [
        ("Feature Matrix Assembler\n(Tabular + Graph Topology\n+ TGN Memory Vectors)", 5.85, 4.3, 2.1, 1.3),
        ("Continuous-Time TGN\n(Self-supervised link prediction,\nGRU memory, zero labels)", 5.85, 2.6, 2.1, 1.3),
        ("Cost-Sensitive XGBoost\n(Focal Loss & scale_pos_weight,\nValidation threshold tuning)", 5.85, 0.9, 2.1, 1.3)
    ]
    for text, ix, iy, iw, ih in s3_items:
        box = patches.FancyBboxPatch((ix, iy), iw, ih, boxstyle="round,pad=0.05,rounding_size=0.1",
                                     facecolor='#FFFFFF', edgecolor='#4A5568', linewidth=1.2)
        ax.add_patch(box)
        ax.text(ix + iw/2, iy + ih/2, text, ha='center', va='center', fontsize=7.5, color='#2D3748', multialignment='center')

    # Stage 4 Sub-boxes
    s4_items = [
        ("Threshold Trigger\n(P(fraud) >= Tau_frozen\nPrecision@k evaluation)", 8.55, 4.3, 1.9, 1.3),
        ("Layer 1: TreeSHAP\n(Exact game-theoretic local\nrisk feature attributions)", 8.55, 2.6, 1.9, 1.3),
        ("Layer 2: Neo4j Replay\n(Multi-hop path retrieval,\nInteractive visual audit alert)", 8.55, 0.9, 1.9, 1.3)
    ]
    for text, ix, iy, iw, ih in s4_items:
        box = patches.FancyBboxPatch((ix, iy), iw, ih, boxstyle="round,pad=0.05,rounding_size=0.1",
                                     facecolor='#FFFFFF', edgecolor='#D69E2E', linewidth=1.2)
        ax.add_patch(box)
        ax.text(ix + iw/2, iy + ih/2, text, ha='center', va='center', fontsize=7.5, color='#2D3748', multialignment='center')

    # Horizontal Flow Arrows between Stages
    arrow_props = dict(facecolor='#1A365D', edgecolor='#1A365D', width=2, headwidth=7, headlength=6)
    ax.annotate('', xy=(3.0, 3.25), xytext=(2.7, 3.25), arrowprops=arrow_props)
    ax.annotate('', xy=(5.7, 3.25), xytext=(5.4, 3.25), arrowprops=arrow_props)
    ax.annotate('', xy=(8.4, 3.25), xytext=(8.1, 3.25), arrowprops=arrow_props)

    # Internal Vertical Arrows
    v_arrow = dict(facecolor='#718096', edgecolor='#718096', width=1.2, headwidth=5, headlength=5)
    for cx in [1.6, 4.2, 6.9, 9.5]:
        ax.annotate('', xy=(cx, 3.9), xytext=(cx, 4.3), arrowprops=v_arrow)
        ax.annotate('', xy=(cx, 2.2), xytext=(cx, 2.6), arrowprops=v_arrow)

    ax.set_title("Fig. 2. The Self-Auditing Ledger: End-to-End System Architecture",
                 fontweight='bold', fontsize=12, pad=15, color='#1A365D')

    plt.tight_layout()
    plt.savefig('artifacts/report_figures/fig2_system_architecture.png', dpi=300)
    plt.close()
    print("Saved fig2_system_architecture.png")

def generate_data_flow_diagram():
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 9), dpi=300)
    
    # === DFD Level 0 ===
    ax1.set_xlim(0, 10)
    ax1.set_ylim(0, 4)
    ax1.axis('off')
    ax1.set_title("Fig. 3(a). Data Flow Diagram (DFD) Level 0 — Context Diagram", fontweight='bold', fontsize=11, color='#1A365D', pad=10)

    # Entities & Process
    # External Entity 1: ERP / Banking Source
    e1 = patches.Rectangle((0.5, 1.2), 2.0, 1.5, facecolor='#E2E8F0', edgecolor='#2D3748', linewidth=1.5)
    ax1.add_patch(e1)
    ax1.text(1.5, 1.95, "Enterprise ERP /\nBanking Feeds\n(SAP/BankSim/AML)", ha='center', va='center', fontweight='bold', fontsize=8, color='#1A202C')

    # Main Process: 0.0 The Self-Auditing Ledger
    p0 = patches.Circle((5.0, 1.95), 1.3, facecolor='#EBF8FF', edgecolor='#2B6CB0', linewidth=2)
    ax1.add_patch(p0)
    ax1.text(5.0, 2.1, "0.0\nThe Self-Auditing\nLedger Engine", ha='center', va='center', fontweight='bold', fontsize=8.5, color='#1A365D')

    # External Entity 2: Forensic Auditor
    e2 = patches.Rectangle((7.5, 1.2), 2.0, 1.5, facecolor='#FEFCBF', edgecolor='#D69E2E', linewidth=1.5)
    ax1.add_patch(e2)
    ax1.text(8.5, 1.95, "Forensic Auditor /\nCompliance Team", ha='center', va='center', fontweight='bold', fontsize=8, color='#1A202C')

    # Flow arrows for Level 0
    flow = dict(facecolor='#2B6CB0', edgecolor='#2B6CB0', width=1.5, headwidth=6, headlength=6)
    ax1.annotate('', xy=(3.7, 2.2), xytext=(2.5, 2.2), arrowprops=flow)
    ax1.text(3.1, 2.45, "Raw Txn Stream\n(BKPF/BSEG)", ha='center', fontsize=7.5, color='#2B6CB0', fontweight='bold')

    ax1.annotate('', xy=(7.5, 2.2), xytext=(6.3, 2.2), arrowprops=flow)
    ax1.text(6.9, 2.45, "Dual-Layer Alert\n(SHAP + Graph Path)", ha='center', fontsize=7.5, color='#2B6CB0', fontweight='bold')

    ax1.annotate('', xy=(5.8, 1.0), xytext=(7.5, 1.0), arrowprops=flow)
    ax1.text(6.65, 0.7, "Audit Feedback &\nThreshold Config", ha='center', fontsize=7.5, color='#4A5568')

    # === DFD Level 1 ===
    ax2.set_xlim(0, 10)
    ax2.set_ylim(0, 6)
    ax2.axis('off')
    ax2.set_title("Fig. 3(b). Data Flow Diagram (DFD) Level 1 — Decomposed System Flow", fontweight='bold', fontsize=11, color='#1A365D', pad=10)

    # Processes
    procs = [
        ("1.0 Canonical\nETL & Normalization", 1.2, 4.2),
        ("2.0 Streaming Zero-\nLookahead Topology", 4.0, 4.2),
        ("3.0 Hybrid Risk\nScoring (XGB/TGN)", 6.8, 4.2),
        ("4.0 Explainability\n& Path Traversal", 8.8, 1.8),
        ("5.0 Audit Dispatch\n& Visual Replay", 4.0, 1.8)
    ]
    for ptext, px, py in procs:
        circ = patches.Circle((px, py), 0.75, facecolor='#FFFFFF', edgecolor='#2B6CB0', linewidth=1.5)
        ax2.add_patch(circ)
        ax2.text(px, py, ptext, ha='center', va='center', fontsize=7.5, fontweight='bold', color='#1A365D')

    # Data Stores
    stores = [
        ("D1: Canonical Txn Store", 1.2, 1.8, 1.6, 0.6),
        ("D2: Neo4j Graph DB", 6.8, 1.8, 1.6, 0.6)
    ]
    for stext, sx, sy, sw, sh in stores:
        # Open ended rectangle for DFD store
        ax2.plot([sx, sx+sw, sx+sw], [sy+sh, sy+sh, sy], color='#4A5568', linewidth=1.5)
        ax2.plot([sx, sx+sw], [sy, sy], color='#4A5568', linewidth=1.5)
        ax2.fill([sx, sx+sw, sx+sw, sx], [sy, sy, sy+sh, sy+sh], color='#EDF2F7')
        ax2.text(sx + sw/2, sy + sh/2, stext, ha='center', va='center', fontsize=7.5, fontweight='bold', color='#2D3748')

    # Arrows connecting processes
    arr = dict(facecolor='#3182CE', edgecolor='#3182CE', width=1.2, headwidth=5, headlength=5)
    ax2.annotate('', xy=(3.25, 4.2), xytext=(1.95, 4.2), arrowprops=arr)
    ax2.text(2.6, 4.4, "Standardized\nTxn Edge", ha='center', fontsize=6.5)

    ax2.annotate('', xy=(6.05, 4.2), xytext=(4.75, 4.2), arrowprops=arr)
    ax2.text(5.4, 4.4, "Feature Vector\n(Topology+Stats)", ha='center', fontsize=6.5)

    ax2.annotate('', xy=(8.4, 2.3), xytext=(7.4, 3.6), arrowprops=arr)
    ax2.text(8.2, 3.1, "High Risk\nTxn (P > Tau)", ha='center', fontsize=6.5)

    ax2.annotate('', xy=(4.75, 1.8), xytext=(8.05, 1.8), arrowprops=arr)
    ax2.text(6.4, 2.05, "SHAP Weights + Subgraph Path", ha='center', fontsize=6.5)

    # Store interactions
    ax2.annotate('', xy=(1.2, 2.4), xytext=(1.2, 3.45), arrowprops=arr)
    ax2.annotate('', xy=(3.5, 3.6), xytext=(2.0, 2.1), arrowprops=arr)
    ax2.annotate('', xy=(7.6, 1.8), xytext=(8.05, 1.8), arrowprops=arr)

    plt.tight_layout()
    plt.savefig('artifacts/report_figures/fig3_data_flow_diagram.png', dpi=300)
    plt.close()
    print("Saved fig3_data_flow_diagram.png")

def generate_use_case_diagram():
    fig, ax = plt.subplots(figsize=(10, 6.5), dpi=300)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 7)
    ax.axis('off')
    
    # Boundary box: The Self-Auditing Ledger
    boundary = patches.Rectangle((2.5, 0.4), 5.2, 6.1, facecolor='#F7FAFC', edgecolor='#2B6CB0', linewidth=2)
    ax.add_patch(boundary)
    ax.text(5.1, 6.25, "System Boundary: The Self-Auditing Ledger", ha='center', va='center',
            fontweight='bold', fontsize=10, color='#1A365D')

    # Actors
    # Actor 1: Forensic Auditor (Left)
    ax.plot([1.2, 1.2], [4.5, 4.0], color='#1A202C', lw=2) # body
    ax.add_patch(patches.Circle((1.2, 4.75), 0.25, facecolor='#E2E8F0', edgecolor='#1A202C', lw=2)) # head
    ax.plot([0.8, 1.6], [4.3, 4.3], color='#1A202C', lw=2) # arms
    ax.plot([1.2, 0.9], [4.0, 3.4], color='#1A202C', lw=2) # left leg
    ax.plot([1.2, 1.5], [4.0, 3.4], color='#1A202C', lw=2) # right leg
    ax.text(1.2, 3.1, "Forensic\nAuditor", ha='center', va='top', fontweight='bold', fontsize=8.5, color='#1A202C')

    # Actor 2: System Administrator (Left bottom)
    ax.plot([1.2, 1.2], [1.9, 1.4], color='#1A202C', lw=2)
    ax.add_patch(patches.Circle((1.2, 2.15), 0.25, facecolor='#E2E8F0', edgecolor='#1A202C', lw=2))
    ax.plot([0.8, 1.6], [1.7, 1.7], color='#1A202C', lw=2)
    ax.plot([1.2, 0.9], [1.4, 0.8], color='#1A202C', lw=2)
    ax.plot([1.2, 1.5], [1.4, 0.8], color='#1A202C', lw=2)
    ax.text(1.2, 0.55, "System\nAdministrator", ha='center', va='top', fontweight='bold', fontsize=8.5, color='#1A202C')

    # Actor 3: Enterprise ERP Source (Right)
    ax.plot([8.8, 8.8], [4.5, 4.0], color='#1A202C', lw=2)
    ax.add_patch(patches.Circle((8.8, 4.75), 0.25, facecolor='#E2E8F0', edgecolor='#1A202C', lw=2))
    ax.plot([8.4, 9.2], [4.3, 4.3], color='#1A202C', lw=2)
    ax.plot([8.8, 8.5], [4.0, 3.4], color='#1A202C', lw=2)
    ax.plot([8.8, 9.1], [4.0, 3.4], color='#1A202C', lw=2)
    ax.text(8.8, 3.1, "Enterprise ERP\nSource (SAP/DB)", ha='center', va='top', fontweight='bold', fontsize=8.5, color='#1A202C')

    # Use cases (ellipses)
    ucs = [
        ("UC1: Ingest & Canonicalize ERP Feed", 5.1, 5.6),
        ("UC2: Extract Zero-Lookahead Topology", 5.1, 4.8),
        ("UC3: Real-Time Fraud Scoring & Calibrated Risk", 5.1, 4.0),
        ("UC4: Inspect High-Risk Audit Alerts", 5.1, 3.2),
        ("UC5: Analyze TreeSHAP Quantitative Drivers", 5.1, 2.4),
        ("UC6: Replay Multi-Hop Neo4j Money Paths", 5.1, 1.6),
        ("UC7: Validate Invariance & Export SOX Trail", 5.1, 0.8)
    ]
    for uctext, ucx, ucy in ucs:
        el = patches.Ellipse((ucx, ucy), 3.8, 0.62, facecolor='#FFFFFF', edgecolor='#2B6CB0', lw=1.4)
        ax.add_patch(el)
        ax.text(ucx, ucy, uctext, ha='center', va='center', fontsize=7.8, fontweight='bold', color='#1A365D')

    # Connections
    line_kw = dict(color='#718096', lw=1.2)
    # Auditor connections
    ax.plot([1.6, 3.2], [4.2, 3.2], **line_kw)
    ax.plot([1.6, 3.2], [4.2, 2.4], **line_kw)
    ax.plot([1.6, 3.2], [4.2, 1.6], **line_kw)
    ax.plot([1.6, 3.2], [4.2, 0.8], **line_kw)

    # Admin connections
    ax.plot([1.6, 3.2], [1.6, 4.8], **line_kw)
    ax.plot([1.6, 3.2], [1.6, 0.8], **line_kw)

    # ERP Source connections
    ax.plot([8.4, 7.0], [4.2, 5.6], **line_kw)
    ax.plot([8.4, 7.0], [4.2, 4.0], **line_kw)

    ax.set_title("Fig. 4. Use Case Diagram for The Self-Auditing Ledger",
                 fontweight='bold', fontsize=12, pad=15, color='#1A365D')

    plt.tight_layout()
    plt.savefig('artifacts/report_figures/fig4_use_case_diagram.png', dpi=300)
    plt.close()
    print("Saved fig4_use_case_diagram.png")

def generate_class_diagram():
    fig, ax = plt.subplots(figsize=(11, 7), dpi=300)
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 7)
    ax.axis('off')

    def draw_uml_class(x, y, w, h, name, attrs, methods, bg='#FFFFFF', border='#2B6CB0'):
        rect = patches.Rectangle((x, y), w, h, facecolor=bg, edgecolor=border, lw=1.4)
        ax.add_patch(rect)
        # Header box
        header_h = 0.55
        h_rect = patches.Rectangle((x, y + h - header_h), w, header_h, facecolor='#EBF8FF', edgecolor=border, lw=1.4)
        ax.add_patch(h_rect)
        ax.text(x + w/2, y + h - header_h/2, name, ha='center', va='center', fontweight='bold', fontsize=8, color='#1A365D')
        
        # Attributes
        curr_y = y + h - header_h - 0.2
        for attr in attrs:
            ax.text(x + 0.1, curr_y, attr, ha='left', va='center', fontsize=6.8, color='#2D3748', family='monospace')
            curr_y -= 0.22
            
        # Divider
        ax.plot([x, x+w], [curr_y + 0.1, curr_y + 0.1], color=border, lw=1.0)
        curr_y -= 0.15
        
        # Methods
        for method in methods:
            ax.text(x + 0.1, curr_y, method, ha='left', va='center', fontsize=6.8, color='#2D3748', family='monospace')
            curr_y -= 0.22

    # Draw classes
    # 1. ERPTransaction
    draw_uml_class(0.5, 4.2, 2.8, 2.5, "ERPTransaction",
                   ["+ txn_id: str", "+ sender_id: str", "+ receiver_id: str", "+ amount: float", "+ timestamp: int", "+ label: int"],
                   ["+ validate_schema(): bool", "+ to_canonical(): dict"])

    # 2. TemporalShadowGraph
    draw_uml_class(4.0, 4.2, 3.2, 2.5, "TemporalShadowGraph",
                   ["- graph: MultiDiGraph", "+ sliding_window: int", "- edge_index: dict"],
                   ["+ insert_tx(tx: ERPTransaction)", "+ get_as_of(T: int): Graph", "+ get_predecessors(node): list"])

    # 3. TopologyEngine
    draw_uml_class(7.7, 4.2, 2.8, 2.5, "TopologyEngine",
                   ["+ detectors: list", "+ window_hours: list"],
                   ["+ detect_cycles(g, tx): float", "+ compute_density(g, tx): dict", "+ extract_features(tx): DataFrame"])

    # 4. HybridFraudClassifier
    draw_uml_class(0.5, 0.6, 3.0, 2.8, "HybridFraudClassifier",
                   ["+ xgb_model: XGBClassifier", "+ tgn_embedder: TGN", "+ threshold: float", "+ loss_fn: str"],
                   ["+ fit(X_train, y_train)", "+ predict_risk(X): float[]", "+ calibrate_threshold(val_df)", "+ evaluate_pr_auc(): float"])

    # 5. DualLayerAlertDispatcher
    draw_uml_class(4.1, 0.6, 3.2, 2.8, "DualLayerAlertDispatcher",
                   ["+ shap_explainer: TreeSHAP", "+ neo4j_driver: GraphDatabase", "+ top_k: int"],
                   ["+ compute_shap(tx_features)", "+ query_subgraph(tx_id): dict", "+ dispatch_alert(tx): AuditAlert", "+ verify_evidence(): bool"])

    # 6. AuditAlert
    draw_uml_class(7.8, 0.6, 2.7, 2.8, "AuditAlert",
                   ["+ alert_id: str", "+ risk_probability: float", "+ shap_attributions: dict", "+ graph_path: list", "+ auditor_status: str"],
                   ["+ export_json(): str", "+ render_subgraph()", "+ approve_investigation()"])

    # Relationship lines
    # Txn -> ShadowGraph (1 to *)
    ax.plot([3.3, 4.0], [5.5, 5.5], color='#4A5568', lw=1.5)
    ax.text(3.65, 5.7, "1..*", ha='center', fontsize=7, color='#4A5568')
    
    # ShadowGraph -> TopologyEngine
    ax.plot([7.2, 7.7], [5.5, 5.5], color='#4A5568', lw=1.5)
    
    # Classifier -> AlertDispatcher
    ax.plot([3.5, 4.1], [2.0, 2.0], color='#4A5568', lw=1.5)
    ax.text(3.8, 2.2, "triggers", ha='center', fontsize=7, color='#4A5568')

    # AlertDispatcher -> AuditAlert (generates)
    ax.plot([7.3, 7.8], [2.0, 2.0], color='#4A5568', lw=1.5)
    ax.text(7.55, 2.2, "1..k", ha='center', fontsize=7, color='#4A5568')

    # TopologyEngine down to Classifier
    ax.plot([8.5, 8.5, 2.0, 2.0], [4.2, 3.8, 3.8, 3.4], color='#4A5568', lw=1.5)
    ax.text(5.5, 3.95, "assembles feature matrix", ha='center', fontsize=7, color='#4A5568')

    ax.set_title("Fig. 5. Class Diagram for The Self-Auditing Ledger Architecture",
                 fontweight='bold', fontsize=12, pad=15, color='#1A365D')

    plt.tight_layout()
    plt.savefig('artifacts/report_figures/fig5_class_diagram.png', dpi=300)
    plt.close()
    print("Saved fig5_class_diagram.png")

def generate_sequence_diagram():
    fig, ax = plt.subplots(figsize=(10.5, 7.2), dpi=300)
    ax.set_xlim(0, 10.5)
    ax.set_ylim(0, 7.5)
    ax.axis('off')

    # Lifelines
    actors = [
        ("ERP Feed", 1.0),
        ("ETL Engine", 2.6),
        ("Topology Engine", 4.3),
        ("Hybrid Model", 6.1),
        ("SHAP & Neo4j", 7.9),
        ("Forensic Auditor", 9.6)
    ]

    for name, x in actors:
        # Box
        rect = patches.FancyBboxPatch((x-0.7, 6.7), 1.4, 0.5, boxstyle="round,pad=0.04,rounding_size=0.08",
                                      facecolor='#EBF8FF', edgecolor='#2B6CB0', lw=1.4)
        ax.add_patch(rect)
        ax.text(x, 6.95, name, ha='center', va='center', fontweight='bold', fontsize=8, color='#1A365D')
        # Vertical lifeline
        ax.plot([x, x], [0.8, 6.7], color='#CBD5E0', linestyle='--', lw=1.2)

    # Sequence Messages
    steps = [
        (1.0, 2.6, 6.2, "1. push_transaction(raw_tx)", True),
        (2.6, 4.3, 5.5, "2. query_state_as_of(timestamp <= T)", True),
        (4.3, 4.3, 4.9, "3. compute_topology_features()", False),
        (4.3, 2.6, 4.4, "4. return structural_vector", True),
        (2.6, 6.1, 3.8, "5. score_risk(ordinary + topology + TGN)", True),
        (6.1, 6.1, 3.3, "6. evaluate P(fraud) >= frozen_threshold", False),
        (6.1, 7.9, 2.7, "7. trigger_explanation(tx_id, risk_score)", True),
        (7.9, 7.9, 2.1, "8. compute_TreeSHAP() & Cypher path traversal", False),
        (7.9, 9.6, 1.5, "9. dispatch_audit_alert(SHAP + Neo4j Subgraph)", True),
        (9.6, 7.9, 0.9, "10. forensic_confirmation_feedback()", True)
    ]

    arr_kw = dict(facecolor='#2B6CB0', edgecolor='#2B6CB0', width=1.0, headwidth=5, headlength=5)
    for x1, x2, y, msg, is_arrow in steps:
        if is_arrow:
            if x1 < x2:
                ax.annotate('', xy=(x2, y), xytext=(x1, y), arrowprops=arr_kw)
                ax.text((x1+x2)/2, y + 0.15, msg, ha='center', va='bottom', fontsize=7.2, color='#1A202C', fontweight='bold')
            else:
                ax.annotate('', xy=(x2, y), xytext=(x1, y), arrowprops=arr_kw)
                ax.text((x1+x2)/2, y + 0.15, msg, ha='center', va='bottom', fontsize=7.2, color='#2C7A7B', fontweight='bold')
        else:
            # Self call loop
            ax.plot([x1, x1+0.4, x1+0.4, x1], [y+0.1, y+0.1, y-0.15, y-0.15], color='#D69E2E', lw=1.2)
            ax.annotate('', xy=(x1, y-0.15), xytext=(x1+0.05, y-0.15),
                        arrowprops=dict(facecolor='#D69E2E', edgecolor='#D69E2E', width=0.8, headwidth=4, headlength=4))
            ax.text(x1 + 0.45, y, msg, ha='left', va='center', fontsize=7.0, color='#B7791F', fontweight='bold')

    ax.set_title("Fig. 6. Sequence Diagram: Real-Time Transaction Ingestion, Scoring, and Audit Dispatch",
                 fontweight='bold', fontsize=11, pad=15, color='#1A365D')

    plt.tight_layout()
    plt.savefig('artifacts/report_figures/fig6_sequence_diagram.png', dpi=300)
    plt.close()
    print("Saved fig6_sequence_diagram.png")

if __name__ == '__main__':
    generate_gantt_chart()
    generate_system_architecture()
    generate_data_flow_diagram()
    generate_use_case_diagram()
    generate_class_diagram()
    generate_sequence_diagram()
    print("All 6 figures generated successfully!")
