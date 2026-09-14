# build_full_report.py
# Generates the official BCSE497J Project-I Report as both .docx and .md

import os
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

def generate_all():
    print("Starting generation of BCSE497J Project-I Report...")
    doc = docx.Document()

    # Set page margins to standard 1 inch
    for s in doc.sections:
        s.top_margin = Inches(1.0)
        s.bottom_margin = Inches(1.0)
        s.left_margin = Inches(1.0)
        s.right_margin = Inches(1.0)
        s.page_width = Inches(8.5)
        s.page_height = Inches(11.0)

    # Base style
    style_normal = doc.styles['Normal']
    font = style_normal.font
    font.name = 'Times New Roman'
    font.size = Pt(12)
    font.color.rgb = RGBColor(0, 0, 0)

    def set_cell_background(cell, fill_hex):
        tcPr = cell._tc.get_or_add_tcPr()
        shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
        tcPr.append(shd)

    def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
        tcPr = cell._tc.get_or_add_tcPr()
        tcMar = parse_xml(f'<w:tcMar {nsdecls("w")}><w:top w:w="{top}" w:type="dxa"/><w:bottom w:w="{bottom}" w:type="dxa"/><w:left w:w="{left}" w:type="dxa"/><w:right w:w="{right}" w:type="dxa"/></w:tcMar>')
        tcPr.append(tcMar)

    def set_table_borders_none(table):
        tblPr = table._tbl.tblPr
        borders = parse_xml(f'<w:tblBorders {nsdecls("w")}><w:top w:val="none"/><w:left w:val="none"/><w:bottom w:val="none"/><w:right w:val="none"/><w:insideH w:val="none"/><w:insideV w:val="none"/></w:tblBorders>')
        tblPr.append(borders)

    def set_table_borders_grid(table, color="B0B0B0"):
        tblPr = table._tbl.tblPr
        borders = parse_xml(f'<w:tblBorders {nsdecls("w")}><w:top w:val="single" w:sz="4" w:space="0" w:color="{color}"/><w:left w:val="single" w:sz="4" w:space="0" w:color="{color}"/><w:bottom w:val="single" w:sz="4" w:space="0" w:color="{color}"/><w:right w:val="single" w:sz="4" w:space="0" w:color="{color}"/><w:insideH w:val="single" w:sz="4" w:space="0" w:color="{color}"/><w:insideV w:val="single" w:sz="4" w:space="0" w:color="{color}"/></w:tblBorders>')
        tblPr.append(borders)

    def add_p(text="", align=WD_ALIGN_PARAGRAPH.JUSTIFY, line_spacing=1.15, space_before=0, space_after=6, bold=False, italic=False, size=12):
        p = doc.add_paragraph()
        p.alignment = align
        p.paragraph_format.line_spacing = line_spacing
        p.paragraph_format.space_before = Pt(space_before)
        p.paragraph_format.space_after = Pt(space_after)
        if text:
            run = p.add_run(text)
            run.font.name = 'Times New Roman'
            run.font.size = Pt(size)
            run.font.bold = bold
            run.font.italic = italic
            run.font.color.rgb = RGBColor(0, 0, 0)
        return p

    def add_h1(title):
        p = doc.add_paragraph()
        p.paragraph_format.line_spacing = 1.5
        p.paragraph_format.space_before = Pt(16)
        p.paragraph_format.space_after = Pt(8)
        run = p.add_run(title.upper())
        run.font.name = 'Times New Roman'
        run.font.size = Pt(14)
        run.font.bold = True
        run.font.color.rgb = RGBColor(0, 0, 0)
        return p

    def add_h2(title):
        p = doc.add_paragraph()
        p.paragraph_format.line_spacing = 1.5
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(6)
        run = p.add_run(title)
        run.font.name = 'Times New Roman'
        run.font.size = Pt(13)
        run.font.bold = True
        run.font.color.rgb = RGBColor(0, 0, 0)
        return p

    def add_h3(title):
        p = doc.add_paragraph()
        p.paragraph_format.line_spacing = 1.5
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(4)
        run = p.add_run(title)
        run.font.name = 'Times New Roman'
        run.font.size = Pt(12)
        run.font.bold = True
        run.font.italic = True
        run.font.color.rgb = RGBColor(0, 0, 0)
        return p

    def add_bullet(bold_prefix, text, size=12):
        p = doc.add_paragraph(style='List Bullet')
        p.paragraph_format.line_spacing = 1.15
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(4)
        if bold_prefix:
            r1 = p.add_run(bold_prefix + ": ")
            r1.font.name = 'Times New Roman'
            r1.font.size = Pt(size)
            r1.font.bold = True
            r1.font.color.rgb = RGBColor(0, 0, 0)
        r2 = p.add_run(text)
        r2.font.name = 'Times New Roman'
        r2.font.size = Pt(size)
        r2.font.bold = False
        r2.font.color.rgb = RGBColor(0, 0, 0)
        return p

    def add_fig(img_path, caption, width=Inches(6.0)):
        if os.path.exists(img_path):
            p_img = doc.add_paragraph()
            p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_img.paragraph_format.space_before = Pt(10)
            p_img.paragraph_format.space_after = Pt(4)
            p_img.add_run().add_picture(img_path, width=width)
        
        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_cap.paragraph_format.space_before = Pt(2)
        p_cap.paragraph_format.space_after = Pt(12)
        run = p_cap.add_run(caption)
        run.font.name = 'Times New Roman'
        run.font.size = Pt(11)
        run.font.bold = True
        run.font.italic = True
        run.font.color.rgb = RGBColor(0, 0, 0)

    # ==========================================
    # COVER PAGE
    # ==========================================
    add_p("BCSE497J - Project-I", align=WD_ALIGN_PARAGRAPH.CENTER, line_spacing=1.5, space_before=20, space_after=24, bold=True, size=14)
    
    add_p("THE SELF-AUDITING LEDGER: FRAUD DETECTION IN ERP SYSTEMS USING TEMPORAL GRAPH TOPOLOGY", 
          align=WD_ALIGN_PARAGRAPH.CENTER, line_spacing=1.5, space_before=10, space_after=35, bold=True, size=16)

    add_p("23BCE2329        AARIN BHATTA", align=WD_ALIGN_PARAGRAPH.CENTER, line_spacing=1.5, space_before=0, space_after=4, bold=True, size=13)
    add_p("23BCE2335        HIMANSHU RAY", align=WD_ALIGN_PARAGRAPH.CENTER, line_spacing=1.5, space_before=0, space_after=4, bold=True, size=13)
    add_p("23BCE2349        MOHAMMED AKIF", align=WD_ALIGN_PARAGRAPH.CENTER, line_spacing=1.5, space_before=0, space_after=35, bold=True, size=13)

    add_p("Under the Supervision of", align=WD_ALIGN_PARAGRAPH.CENTER, line_spacing=1.5, space_before=0, space_after=4, bold=False, size=12)
    add_p("Prof. Dhivya C.R.", align=WD_ALIGN_PARAGRAPH.CENTER, line_spacing=1.5, space_before=0, space_after=2, bold=True, size=13)
    add_p("Assistant Professor Senior Grade 1", align=WD_ALIGN_PARAGRAPH.CENTER, line_spacing=1.5, space_before=0, space_after=2, bold=False, size=12)
    add_p("School of Computer Science and Engineering (SCOPE)", align=WD_ALIGN_PARAGRAPH.CENTER, line_spacing=1.5, space_before=0, space_after=35, bold=False, size=12)

    add_p("B.Tech.", align=WD_ALIGN_PARAGRAPH.CENTER, line_spacing=1.5, space_before=0, space_after=2, bold=True, size=13)
    add_p("in", align=WD_ALIGN_PARAGRAPH.CENTER, line_spacing=1.5, space_before=0, space_after=2, bold=False, size=12)
    add_p("Computer Science and Engineering", align=WD_ALIGN_PARAGRAPH.CENTER, line_spacing=1.5, space_before=0, space_after=25, bold=True, size=13)

    add_p("School of Computer Science and Engineering", align=WD_ALIGN_PARAGRAPH.CENTER, line_spacing=1.5, space_before=0, space_after=15, bold=True, size=13)

    logo_path = "artifacts/report_figures/image1.png"
    if os.path.exists(logo_path):
        p_logo = doc.add_paragraph()
        p_logo.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_logo.paragraph_format.space_before = Pt(5)
        p_logo.paragraph_format.space_after = Pt(15)
        p_logo.add_run().add_picture(logo_path, width=Inches(3.2))

    add_p("September 2026", align=WD_ALIGN_PARAGRAPH.CENTER, line_spacing=1.5, space_before=0, space_after=0, bold=True, size=12)
    doc.add_page_break()

    # ==========================================
    # ABSTRACT PAGE (Page i)
    # ==========================================
    add_p("ABSTRACT", align=WD_ALIGN_PARAGRAPH.CENTER, line_spacing=1.5, space_before=15, space_after=18, bold=True, size=14)

    abstract_text = (
        "Enterprise Resource Planning (ERP) systems process high-volume, multi-party financial transactions where conventional "
        "row-level auditing fails to detect coordinated collusion, money-mule collection funnels, and circular round-tripping. "
        "While Graph Neural Networks (GNNs) and machine learning models offer potential solutions, existing financial graph systems "
        "suffer from lookahead data leakage, unrealistic random train-test splits, and uninterpretable black-box predictions.\n\n"
        "This project presents The Self-Auditing Ledger, a leakage-free-by-construction framework that transforms ERP transaction logs "
        "into continuous-time temporal graphs. An incremental, streaming topology engine extracts structural fraud features—including "
        "directed payment cycles, fan-in collection ratios, burst density, and temporal degree velocity—using strictly past-only "
        "graph snapshots (t <= T). These topological metrics are combined with tabular transaction attributes and self-supervised "
        "Temporal Graph Network (TGN) embeddings to train cost-sensitive gradient boosted decision trees (XGBoost) optimized with focal loss.\n\n"
        "Evaluated across diverse transaction network density regimes (BankSim, IBM AML, SAP Würzburg, and an agent-based synthetic "
        "ERP economy) under strict chronological splits over three random seeds, our results demonstrate that temporal graph topology "
        "delivers a statistically validated +11.7% PR-AUC lift on relational transaction networks (reaching 0.9364 PR-AUC and 1.00 "
        "Precision@100 on BankSim). The system pairs every high-risk alert with dual-layer explainability: exact TreeSHAP feature "
        "attributions and visual Neo4j subgraph reconstructions of the suspicious transaction chain for forensic verification, "
        "bridging the gap between automated artificial intelligence and internal audit compliance."
    )
    add_p(abstract_text, align=WD_ALIGN_PARAGRAPH.JUSTIFY, line_spacing=1.15, space_before=0, space_after=18, size=12)

    add_p("Keywords — ERP Fraud Detection, Temporal Graph Topology, Zero-Lookahead Leakage, Cost-Sensitive XGBoost, Temporal Graph Networks, TreeSHAP, Neo4j Visual Audit.",
          align=WD_ALIGN_PARAGRAPH.LEFT, line_spacing=1.15, space_before=12, space_after=0, italic=True, size=11)
    doc.add_page_break()

    # ==========================================
    # TABLE OF CONTENTS PAGE (Page ii)
    # ==========================================
    add_p("TABLE OF CONTENTS", align=WD_ALIGN_PARAGRAPH.CENTER, line_spacing=1.5, space_before=15, space_after=15, bold=True, size=14)

    toc_table = doc.add_table(rows=1, cols=3)
    toc_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    toc_table.autofit = False
    set_table_borders_none(toc_table)

    # Set column widths: Sl.No (0.8 in), Contents (5.4 in), Page No (1.0 in)
    widths = [Inches(0.8), Inches(5.4), Inches(1.0)]
    
    hdr_cells = toc_table.rows[0].cells
    hdr_cells[0].text = "Sl.No"
    hdr_cells[1].text = "Contents"
    hdr_cells[2].text = "Page No."
    for idx, c in enumerate(hdr_cells):
        c.width = widths[idx]
        set_cell_margins(c, top=80, bottom=80, left=100, right=100)
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT if idx < 2 else WD_ALIGN_PARAGRAPH.RIGHT
        p.paragraph_format.line_spacing = 1.5
        for run in p.runs:
            run.font.name = 'Times New Roman'
            run.font.size = Pt(12)
            run.font.bold = True

    toc_items = [
        ("", "Abstract", "i", True, False),
        ("1.", "INTRODUCTION", "1", True, False),
        ("", "1.1 Background", "1", False, False),
        ("", "1.2 Motivation", "2", False, False),
        ("", "1.3 Scope of the Project", "3", False, False),
        ("2.", "PROJECT DESCRIPTION AND GOALS", "4", True, False),
        ("", "2.1 Literature Review", "4", False, False),
        ("", "2.2 Research Gap", "8", False, False),
        ("", "2.3 Objectives", "9", False, False),
        ("", "2.4 Problem Statement", "10", False, False),
        ("", "2.5 Project Plan", "11", False, False),
        ("3.", "TECHNICAL SPECIFICATION", "13", True, False),
        ("", "3.1 Requirements", "13", False, False),
        ("", "    3.1.1 Functional", "13", False, False),
        ("", "    3.1.2 Non-Functional", "14", False, False),
        ("", "3.2 Feasibility Study", "15", False, False),
        ("", "    3.2.1 Technical Feasibility", "15", False, False),
        ("", "    3.2.2 Economic Feasibility", "16", False, False),
        ("", "    3.2.3 Social Feasibility", "16", False, False),
        ("", "3.3 System Specification", "17", False, False),
        ("", "    3.3.1 Hardware Specification", "17", False, False),
        ("", "    3.3.2 Software Specification", "18", False, False),
        ("4.", "DESIGN APPROACH AND DETAILS", "19", True, False),
        ("", "4.1 System Architecture", "19", False, False),
        ("", "4.2 Design", "22", False, False),
        ("", "    4.2.1 Data Flow Diagram", "22", False, False),
        ("", "    4.2.2 Use Case Diagram", "24", False, False),
        ("", "    4.2.3 Class Diagram", "26", False, False),
        ("", "    4.2.4 Sequence Diagram", "28", False, False),
        ("5.", "REFERENCES", "30", True, False)
    ]

    for sl, item, page, is_bold, is_italic in toc_items:
        row = toc_table.add_row()
        cells = row.cells
        cells[0].text = sl
        cells[1].text = item
        cells[2].text = page
        for idx, c in enumerate(cells):
            c.width = widths[idx]
            set_cell_margins(c, top=40, bottom=40, left=80, right=80)
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT if idx < 2 else WD_ALIGN_PARAGRAPH.RIGHT
            p.paragraph_format.line_spacing = 1.3
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(2)
            for run in p.runs:
                run.font.name = 'Times New Roman'
                run.font.size = Pt(11)
                run.font.bold = is_bold
                run.font.italic = is_italic

    doc.add_page_break()

    # ==========================================
    # 1. INTRODUCTION
    # ==========================================
    add_h1("1. INTRODUCTION")

    add_h2("1.1 Background")
    bg_text = (
        "Modern enterprise accounting systems, such as SAP S/4HANA and Oracle Financials, process millions of daily journal "
        "entries governing billions of dollars in capital flow. Traditional fraud detection and statutory auditing rely on "
        "rule-based thresholds, manual sampling, and isolated debit-credit reconciliation. However, contemporary financial "
        "crimes—including invoice fraud, authorized push payment scams, money-mule funnels, and circular payment round-tripping—operate "
        "across distributed networks of seemingly independent corporate accounts and intermediary entities.\n\n"
        "When transactions are analyzed as independent tabular rows, the structural relationships between counterparties remain "
        "completely invisible. Although graph data modeling provides a natural paradigm for representing financial networks, existing "
        "machine learning pipelines suffer from severe methodology failures: lookahead data leakage across temporal boundaries, "
        "identity-splitting between senders and receivers, and post-event information contamination.\n\n"
        "The Self-Auditing Ledger bridges this gap by representing ERP transaction journals as dynamic, directed temporal graphs. "
        "By tracking evolving financial interactions chronologically, the system enables automated, continuous auditing that discovers "
        "complex multi-entity fraud structures while strictly preserving temporal causality."
    )
    add_p(bg_text, align=WD_ALIGN_PARAGRAPH.JUSTIFY, line_spacing=1.15, space_before=0, space_after=12)

    add_h2("1.2 Motivation")
    mot_text = (
        "Financial fraud inflicts hundreds of billions of dollars in global enterprise losses annually, jeopardizing organizational "
        "solvency, corporate governance, and regulatory compliance under Sarbanes-Oxley (SOX) and Basel III standards. Conventional "
        "internal audit procedures sample less than five percent of annual transaction ledgers, frequently identifying irregularities "
        "months after capital dissipation occurs.\n\n"
        "Recent academic interest in Graph Neural Networks (GNNs) for fraud detection has produced inflated performance claims "
        "(exceeding 99% accuracy) that collapse during enterprise deployment due to lookahead leakage, shuffled cross-validation, and "
        "metric distortion on heavily imbalanced datasets (<1% fraud). Furthermore, complex neural architectures function as inscrutable "
        "black boxes, generating raw risk scores that internal auditors cannot legally justify or substantiate in forensic proceedings.\n\n"
        "This project is motivated by the urgent necessity for a scientifically rigorous, leakage-free continuous audit framework. "
        "By uniting streaming temporal graph feature extraction, cost-sensitive machine learning, and dual-layer explainability "
        "(exact TreeSHAP game-theoretic attributions coupled with interactive Neo4j visual path reconstruction), we empower forensic "
        "auditors to detect sophisticated relational fraud in real time while providing verifiable, audit-grade visual evidence."
    )
    add_p(mot_text, align=WD_ALIGN_PARAGRAPH.JUSTIFY, line_spacing=1.15, space_before=0, space_after=12)

    add_h2("1.3 Scope of the Project")
    scope_text = (
        "The scope of this project encompasses the design, implementation, and empirical validation of an end-to-end continuous "
        "auditing framework for enterprise transaction ledgers. The research covers four diverse benchmark financial datasets spanning "
        "distinct structural graph densities: IBM AML (multi-hop cycle and fan-in flows), BankSim (bipartite customer-merchant network), "
        "SAP Würzburg (genuine ERP general ledger entries), and an agent-based synthetic ERP simulation.\n\n"
        "Key technical deliverables include:\n"
        "1. Canonical ETL pipeline unifying disparate account namespaces into directed temporal multi-graphs.\n"
        "2. Streaming, zero-lookahead topology engine extracting sliding-window structural metrics (directed cycles, fan-in hubs, transfer velocity).\n"
        "3. Continuous-time Temporal Graph Network (TGN) self-supervised node memory embedder.\n"
        "4. Cost-sensitive XGBoost classification engine with focal loss optimization and time-aware threshold calibration.\n"
        "5. Automated invariance testing framework verifying zero future-to-past data leakage.\n"
        "6. Dual-layer explainability dashboard integrating exact TreeSHAP feature breakdowns with visual Neo4j subgraph traversal and interactive replay.\n\n"
        "The project explicitly excludes production deployment inside proprietary SAP ABAP application servers and real-time bank "
        "settlement gateways, focusing on post-posting continuous ledger auditing and forensic investigation."
    )
    add_p(scope_text, align=WD_ALIGN_PARAGRAPH.JUSTIFY, line_spacing=1.15, space_before=0, space_after=15)
    doc.add_page_break()

    # ==========================================
    # 2. PROJECT DESCRIPTION AND GOALS
    # ==========================================
    add_h1("2. PROJECT DESCRIPTION AND GOALS")

    add_h2("2.1 Literature Review")
    lit_intro = (
        "Financial fraud detection in enterprise networks represents a convergence of three mature disciplines: graph representation "
        "learning, extreme class imbalance modeling, and continuous accounting audit automation. A systematic review of current "
        "literature reveals critical methodological paradigms, breakthroughs, and architectural limitations across these pillars."
    )
    add_p(lit_intro, align=WD_ALIGN_PARAGRAPH.JUSTIFY, line_spacing=1.15, space_before=0, space_after=8)

    add_h3("2.1.1 Graph Neural Networks and Graph-Based Fraud Detection")
    lit_p1 = (
        "Graph Neural Networks (GNNs) have emerged as the primary research vehicle for network anomaly detection. Motie and Raahemi [1] "
        "conducted a comprehensive systematic survey of GNN architectures for financial fraud, identifying that while Relational Graph "
        "Convolutional Networks (R-GCN) and Graph Attention Networks (GAT) effectively propagate structural neighbor representations, "
        "they suffer from three systemic shortcomings: severe susceptibility to neighbor camouflage, heavy computational complexity during "
        "multi-hop aggregation, and complete opacity regarding forensic explainability. Innan et al. [2] and Grossi et al. [3] explored "
        "quantum graph neural networks and hybrid quantum-classical feature selection for credit card fraud, demonstrating theoretical "
        "acceleration in subgraph pattern matching but remaining restricted to small-scale synthetic simulations due to current physical "
        "qubit hardware constraints.\n\n"
        "Addressing temporal dynamics, Devi et al. [4] investigated reinforcement learning coupled with GNN fusion for real-time transaction "
        "scoring, highlighting the necessity of capturing transaction velocity. Yuan et al. [6] provided an extensive taxonomy of graph "
        "anomaly detection, demonstrating that static graph projections fail when transaction semantics depend on precise temporal sequence "
        "and latency between counterparty hops. Shi et al. [7] formulated uncertainty-aware spatio-temporal contrastive GNNs to handle "
        "evolving fraud typologies, validating that fraud patterns shift dynamically across operational time windows."
    )
    add_p(lit_p1, align=WD_ALIGN_PARAGRAPH.JUSTIFY, line_spacing=1.15, space_before=0, space_after=8)

    add_h3("2.1.2 Class Imbalance Learning and Loss Function Formulations")
    lit_p2 = (
        "Financial transaction ledgers exhibit extreme class imbalance, where fraudulent entries comprise between 0.1% and 1.2% of total volume. "
        "Tong et al. [9] and Boyapati et al. [10] demonstrated that standard cross-entropy objectives collapse toward predicting the majority "
        "legitimate class. A prevalent mitigation strategy in literature is synthetic minority oversampling (SMOTE). However, as proven by "
        "Zhi et al. [8], linear interpolation between graph node feature vectors creates non-physical pseudo-nodes that violate graph topological "
        "invariants—such as creating an artificial vector that represents 'half a directed cycle.'\n\n"
        "In contrast, loss function reweighting and cost-sensitive learning avoid dataset corruption. Lin et al. and recent advancements in "
        "Boundary Focal Loss introduce dynamic modulating factors (1 - p_t)^gamma that down-weight trivial, well-classified negative instances, "
        "concentrating gradient updates on ambiguous decision boundary instances. Furthermore, comparative evaluations by Chen et al. "
        "demonstrate that on structured tabular data, gradient boosted decision trees (XGBoost, LightGBM) consistently match or exceed deep "
        "neural networks in classification accuracy while maintaining orders-of-magnitude faster CPU training times and superior numerical stability."
    )
    add_p(lit_p2, align=WD_ALIGN_PARAGRAPH.JUSTIFY, line_spacing=1.15, space_before=0, space_after=8)

    add_h3("2.1.3 Continuous Auditing in ERP Systems and Explainable AI (XAI)")
    lit_p3 = (
        "In enterprise accounting, Vasarhelyi et al. [12] established the foundational theory of Continuous Auditing (CA), proving that "
        "periodic retrospective audits fail to safeguard corporate assets in high-throughput enterprise resource planning systems. Mamakou "
        "et al. [11] evaluated post-implementation internal control failures in ERP environments, finding that over 80% of corporate "
        "accounting frauds involve authorized users circumventing Segregation of Duties (SoD) through collusive multi-step journal postings.\n\n"
        "Jawad et al. [5] surveyed machine learning optimization in enterprise systems, emphasizing that internal auditors cannot adopt "
        "predictive models unless predictions are fully explainable and legally defensible under corporate governance mandates. While post-hoc "
        "explainers like LIME or permutation importance provide coarse approximations, Lundberg et al.'s TreeSHAP algorithm guarantees exact, "
        "game-theoretically optimal local feature attributions for tree ensembles. Complementing feature attributions, Wang et al. [21] "
        "introduced causal graph explainers, establishing that forensic auditability requires extracting connected, causally faithful subgraphs "
        "that visually substantiate how collusive funds propagated across accounts."
    )
    add_p(lit_p3, align=WD_ALIGN_PARAGRAPH.JUSTIFY, line_spacing=1.15, space_before=0, space_after=12)

    # Comparative Literature Synthesis Table
    add_p("Table 2.1. Comparative Synthesis of Key Peer-Reviewed Research and Alignment with The Self-Auditing Ledger",
          align=WD_ALIGN_PARAGRAPH.LEFT, line_spacing=1.15, space_before=6, space_after=6, bold=True, size=10.5)

    lit_table = doc.add_table(rows=1, cols=4)
    lit_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    lit_table.autofit = False
    set_table_borders_grid(lit_table)

    t_widths = [Inches(1.8), Inches(1.5), Inches(2.2), Inches(2.0)]
    t_hdrs = ["Author & Year", "Proposed Methodology", "Key Findings & Contribution", "Project Alignment & Differentiation"]
    for idx, c in enumerate(lit_table.rows[0].cells):
        c.width = t_widths[idx]
        set_cell_background(c, "1A365D")
        set_cell_margins(c, top=80, bottom=80, left=100, right=100)
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(t_hdrs[idx])
        run.font.name = 'Times New Roman'
        run.font.size = Pt(9.5)
        run.font.bold = True
        run.font.color.rgb = RGBColor(255, 255, 255)

    lit_rows = [
        ("Motie & Raahemi (2024) [1]", "Systematic review of GNNs in financial fraud", "Identified R-GCN and GAT effectiveness; highlighted neighbor camouflage and explainability bottlenecks", "Validates graph modeling; our system extracts explicit interpretable topology instead of black-box embeddings"),
        ("Devi, Raja, & Chin (2025) [4]", "RL-GNN fusion for real-time transaction fraud", "Proved real-time transaction scoring requires dynamic velocity and sequential relationship modeling", "Adopted temporal sliding windows; replaced complex RL with deterministic zero-lookahead feature extractors"),
        ("Jawad et al. (2024) [5]", "ML optimization review in ERP architectures", "Emphasized continuous internal audit integration and strict explainability requirements for auditors", "Directly targets ERP accounting ledgers; satisfies audit compliance via dual-layer TreeSHAP + Neo4j alert dispatch"),
        ("Yuan et al. (2025) [6]", "Comprehensive survey on GNN anomaly detection", "Static graph models fail when temporal intervals and sequence ordering govern malicious activity", "Enforces continuous-time temporal shadow graph where edges are strictly timestamped and traversed chronologically"),
        ("Shi et al. (2026) [7]", "Spatio-temporal contrastive GNNs (AAAI)", "Showed uncertainty-aware representations mitigate evolving fraud typologies over time horizons", "Incorporates self-supervised TGN memory vectors alongside explicit sliding-window structural features"),
        ("Zhi et al. (2025) [8]", "Conditional GAN for imbalanced fraud graphs", "Proved SMOTE oversampling distorts network topology and creates non-physical graph structures", "Enforces locked decision: zero synthetic oversampling for graph features; uses focal loss and scale_pos_weight exclusively"),
        ("Boyapati et al. (2025) [10]", "BalancerGNN for extreme imbalance", "Demonstrated standard cross-entropy fails on rare events without adaptive gradient re-weighting", "Implements alpha-free custom focal loss objective in XGBoost, collapsing run-to-run seed variance"),
        ("Mamakou et al. (2024) [11]", "Post-implementation audit review of ERPs", "Found manual sampling catches <5% of fraud; internal collusion bypasses static ERP controls", "Provides continuous automated screening across 100% of transaction entries, eliminating audit sampling blindspots"),
        ("Vasarhelyi et al. (2012) [12]", "Foundational continuous auditing framework", "Established theoretical necessity of real-time monitoring over retrospective periodic audits", "Operationalizes continuous auditing theory into an automated, streaming Python/Neo4j software prototype"),
        ("Lundberg et al. (2020) [17]", "TreeSHAP exact local explanation algorithm", "Guarantees exact, game-theoretically optimal feature attributions in polynomial time for tree models", "Selected XGBoost champion specifically to leverage exact TreeSHAP attribution for every flagged transaction"),
        ("Wang et al. (2023) [21]", "Reinforced Causal Explainer (RC-Explainer)", "Proved valid graph explanations require connected, causally faithful subgraphs rather than isolated weights", "Pioneered dual-layer audit alert: combines quantitative TreeSHAP waterfall values with visual multi-hop Neo4j paths")
    ]

    for r_idx, (auth, meth, find, align) in enumerate(lit_rows):
        row = lit_table.add_row()
        bg_col = "F7FAFC" if r_idx % 2 == 0 else "FFFFFF"
        for idx, text in enumerate([auth, meth, find, align]):
            c = row.cells[idx]
            c.width = t_widths[idx]
            set_cell_background(c, bg_col)
            set_cell_margins(c, top=60, bottom=60, left=80, right=80)
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.line_spacing = 1.15
            run = p.add_run(text)
            run.font.name = 'Times New Roman'
            run.font.size = Pt(8.5)
            run.font.bold = (idx == 0)

    doc.add_page_break()

    # 2.2 Research Gap
    add_h2("2.2 Research Gap")
    gap_intro = (
        "Despite extensive literature in machine learning for financial fraud, an in-depth audit of existing frameworks—including "
        "predecessor research systems—identifies four fundamental research and engineering gaps that have prevented the adoption of "
        "graph-based methods in enterprise audit environments:"
    )
    add_p(gap_intro, align=WD_ALIGN_PARAGRAPH.JUSTIFY, line_spacing=1.15, space_before=0, space_after=8)

    add_bullet("1. Absence of Explicit Fraud Topology Extraction in Deep Graph Learning",
               "Current GNN approaches project graph nodes into high-dimensional latent embedding spaces. While effective for raw classification, "
               "these embeddings completely obscure whether a transaction participated in a circular round-trip, a mule collection fan-in hub, "
               "or a rapid layering transfer chain. Forensic auditors cannot present latent mathematical vectors as evidence in legal or regulatory "
               "proceedings. There is a lack of systems that explicitly detect and extract named topological fraud shapes as first-class feature vectors.")

    add_bullet("2. Pervasive Lookahead Data Leakage in Published Graph Fraud Models",
               "Published research papers routinely report near-perfect detection metrics (>0.99 ROC-AUC) on financial datasets. However, our "
               "methodological audit proves that these results are overwhelmingly artifacts of data leakage. Feature extractors compute centrality "
               "and community metrics over the full static graph (all timestamps simultaneously), crediting structure signals back to early members "
               "using future information. Similarly, train-test splits are performed via randomly shuffled cross-validation, allowing models to "
               "learn patterns from future transactions to predict past events. No prior system implements a provably zero-lookahead temporal engine "
               "guaranteed by automated invariance testing.")

    add_bullet("3. Confounded Evaluations, Flawed Imbalance Combinations, and Missing Ablations",
               "A critical flaw in rare-event modeling literature is the simultaneous application of synthetic oversampling (SMOTE) and cost-sensitive "
               "class weighting, resulting in uncontrolled gradient distortion. Furthermore, models are evaluated using ROC-AUC (which is flattered "
               "by millions of trivial negative transactions) or fixed 0.5 decision thresholds. Most critically, literature lacks clean, within-dataset "
               "ablation studies that isolate whether graph topology adds statistically validated predictive lift over a strong tabular baseline "
               "when measured via Precision-Recall AUC (PR-AUC) and operational Precision@k.")

    add_bullet("4. Domain Disconnect Between Academic Graph Benchmarks and Enterprise ERP Ledgers",
               "The vast majority of graph fraud research focuses on consumer credit cards (BankSim) or social networks (Reddit, Yelp). Enterprise "
               "Resource Planning (ERP) systems (e.g., SAP general ledgers BKPF/BSEG) operate under strict double-entry bookkeeping rules, bipartite "
               "document-account linkages, and internal control frameworks (Segregation of Duties). Prior graph systems fail to bridge this domain "
               "gap, suffering from identity-splitting bugs where sender and receiver accounts are placed into disjoint namespaces, rendering cycles invisible.")

    # 2.3 Objectives
    add_h2("2.3 Objectives")
    obj_intro = "To resolve the identified research gaps, the primary goals of this project are formulated using the SMART framework:"
    add_p(obj_intro, align=WD_ALIGN_PARAGRAPH.JUSTIFY, line_spacing=1.15, space_before=0, space_after=6)

    add_bullet("Specific (S)",
               "Construct a continuous-time Temporal Shadow Graph directly from ERP transaction logs with a unified account namespace, "
               "and engineer a streaming zero-lookahead topology engine that extracts explicit fraud shapes (directed payment cycles, fan-in hubs, "
               "transfer velocity, and connection density) using strictly past-only graph snapshots (t <= T).")

    add_bullet("Measurable (M)",
               "Demonstrate statistically significant predictive improvement over a strong tabular baseline via PR-AUC and operational Precision@100 "
               "across three random seeds, targeting >10% relative PR-AUC lift on structurally rich transaction networks while maintaining an automated "
               "leakage test suite that guarantees zero future-to-past information leakage.")

    add_bullet("Achievable (A)",
               "Decouple the heavy graph computation path (executed deterministically in Python using Pandas and NetworkX) from the visual audit "
               "explanation path (rendered in Neo4j), preventing graph database out-of-memory crashes and ensuring sub-second inference latency on commodity CPU hardware.")

    add_bullet("Relevant (R)",
               "Provide enterprise-grade, dual-layer forensic explainability by coupling exact TreeSHAP quantitative feature attributions with "
               "interactive Neo4j visual subgraph path reconstructions, satisfying statutory audit compliance under SOX Section 404 and Basel III.")

    add_bullet("Time-bound (T)",
               "Execute the project across eight structured work packages over a 16-week timeline, culminating in fully validated benchmark ablations, "
               "a working interactive demonstration tool, and complete technical documentation by September 2026.")

    # 2.4 Problem Statement
    add_h2("2.4 Problem Statement")
    prob_text = (
        "Enterprise Resource Planning (ERP) accounting databases record high-velocity, multi-party financial transactions where fraudulent "
        "activities (e.g., round-trip money laundering, supplier impersonation, and collusive mule networks) manifest as complex structural patterns "
        "distributed across time and multiple entities. Existing fraud detection methodologies fail because:\n"
        "1. Row-level tabular auditing models evaluate individual ledger postings in isolation, ignoring topological network dependencies;\n"
        "2. Deep graph neural networks produce black-box risk scores devoid of human-interpretable topological evidence, preventing statutory audit substantiation;\n"
        "3. Published graph anomaly pipelines suffer from lookahead data leakage and flawed cross-validation, inflating offline metrics while failing catastrophically in production streaming environments;\n"
        "4. Severe class imbalance (<1% fraud) is mishandled through destructive oversampling that distorts network structures.\n\n"
        "The core scientific challenge addressed by this project is: Can we engineer a continuous-time temporal graph auditing system that "
        "extracts explicit, interpretable topological fraud shapes strictly from historical graph state (t <= T) without lookahead leakage, "
        "and prove that these structural features deliver statistically significant, defensible predictive lift over a strong tabular baseline "
        "under rigorous rare-event metrics?"
    )
    add_p(prob_text, align=WD_ALIGN_PARAGRAPH.JUSTIFY, line_spacing=1.15, space_before=0, space_after=12)

    # 2.5 Project Plan
    add_h2("2.5 Project Plan")
    plan_text = (
        "The project was executed following an agile research and engineering methodology spanning 16 weeks (June 2026 to September 2026). "
        "The implementation lifecycle was partitioned into eight distinct, sequential tasks with seven critical milestone verification gates. "
        "Figure 1 illustrates the project Gantt chart, tracking task scheduling, concurrent workflows, and milestone reviews."
    )
    add_p(plan_text, align=WD_ALIGN_PARAGRAPH.JUSTIFY, line_spacing=1.15, space_before=0, space_after=8)

    add_fig("artifacts/report_figures/fig1_gantt_chart.png", "Fig. 1. Implementation Gantt Chart for The Self-Auditing Ledger (Weeks 1 to 16)", width=Inches(6.2))

    # Project Plan Milestone Table
    add_p("Table 2.2. Project Task Breakdown, Work Packages, and Milestone Deliverables",
          align=WD_ALIGN_PARAGRAPH.LEFT, line_spacing=1.15, space_before=6, space_after=6, bold=True, size=10.5)

    plan_table = doc.add_table(rows=1, cols=5)
    plan_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    plan_table.autofit = False
    set_table_borders_grid(plan_table)

    p_widths = [Inches(0.9), Inches(2.2), Inches(1.1), Inches(1.1), Inches(2.2)]
    p_hdrs = ["Task ID", "Task Description", "Timeline", "Milestone", "Deliverables & Artifacts"]
    for idx, c in enumerate(plan_table.rows[0].cells):
        c.width = p_widths[idx]
        set_cell_background(c, "1A365D")
        set_cell_margins(c, top=80, bottom=80, left=80, right=80)
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(p_hdrs[idx])
        run.font.name = 'Times New Roman'
        run.font.size = Pt(9.5)
        run.font.bold = True
        run.font.color.rgb = RGBColor(255, 255, 255)

    plan_rows = [
        ("Task 1", "Literature Survey & Research Gap Study", "Wks 1 - 3", "M1: Survey", "Review of 12 peer-reviewed papers; formulated research gaps and thesis"),
        ("Task 2", "Dataset Acquisition & Canonical ETL Engine", "Wks 3 - 5", "M2: ETL", "Ingested IBM AML, BankSim, SAP Würzburg; unified account namespace"),
        ("Task 3", "Streaming Zero-Lookahead Topology Engine", "Wks 5 - 8", "M3: Engine", "Implemented sliding-window cycle/density detectors; automated leakage test"),
        ("Task 4", "Hybrid Modeling Harness (XGBoost + TGN)", "Wks 8 - 11", "M4: Model", "Trained cost-sensitive XGBoost with focal loss; built continuous-time TGN"),
        ("Task 5", "Systematic Multi-Seed Ablation Benchmarking", "Wks 11 - 13", "M5: Ablation", "Multi-seed baseline vs +topology runs; proven +11.7% PR-AUC lift on BankSim"),
        ("Task 6", "Explainable Audit Alert Dispatch & Neo4j", "Wks 13 - 15", "M6: Alert", "Exact TreeSHAP integration; automated Cypher graph path visualizer"),
        ("Task 7", "Full Documentation & Project Report", "Wks 14 - 16", "M7: Review", "Comprehensive technical specification, UML diagrams, report generation"),
        ("Task 8", "Review & Final Project Submission", "Wks 15 - 16", "Final Signoff", "Oral presentation defense, verified code repository, documentation signoff")
    ]

    for r_idx, (tid, tdesc, ttime, tmile, tdeliv) in enumerate(plan_rows):
        row = plan_table.add_row()
        bg_col = "F7FAFC" if r_idx % 2 == 0 else "FFFFFF"
        for idx, text in enumerate([tid, tdesc, ttime, tmile, tdeliv]):
            c = row.cells[idx]
            c.width = p_widths[idx]
            set_cell_background(c, bg_col)
            set_cell_margins(c, top=50, bottom=50, left=60, right=60)
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if idx in [0, 2, 3] else WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.line_spacing = 1.15
            run = p.add_run(text)
            run.font.name = 'Times New Roman'
            run.font.size = Pt(8.5)
            run.font.bold = (idx == 0)

    doc.add_page_break()

    # ==========================================
    # 3. TECHNICAL SPECIFICATION
    # ==========================================
    add_h1("3. TECHNICAL SPECIFICATION")

    add_h2("3.1 Requirements")

    add_h3("3.1.1 Functional Requirements")
    add_bullet("FR1: Multi-Source ERP & Banking Ingestion",
               "The system shall ingest structured transaction ledgers from diverse enterprise formats, including SAP relational tables (BKPF/BSEG), "
               "IBM AML transfer streams, BankSim payment logs, and synthetic ERP records, parsing amounts, timestamps, and entity keys.")

    add_bullet("FR2: Entity Namespace Normalization & Bipartite Projection",
               "The system shall resolve disparate account, vendor, and customer identifiers into a single unified Account node namespace, "
               "constructing directed multigraph edges (TRANSFERS_TO) to enable structural traversal across multi-hop counterparty paths.")

    add_bullet("FR3: Streaming Zero-Lookahead Topology Extraction",
               "The system shall compute topological features (directed cycle length, cycle amount conservation, fan-in/fan-out ratios, "
               "connection density, and transfer velocity) strictly against the graph state as of transaction timestamp T, preventing future data contamination.")

    add_bullet("FR4: Continuous-Time TGN Self-Supervised Memory",
               "The system shall maintain a continuous-time Temporal Graph Network (TGN) with per-node GRU memory cells, trained via label-free "
               "self-supervised link prediction, producing dynamic 32-dimensional behavioral node embeddings without label leakage.")

    add_bullet("FR5: Cost-Sensitive Hybrid Classification & Calibrated Scoring",
               "The system shall train gradient boosted decision tree ensembles (XGBoost) using cost-sensitive scale_pos_weight or custom focal loss, "
               "calibrating optimal decision thresholds on validation splits to maximize rare-event PR-AUC and operational Precision@100.")

    add_bullet("FR6: Automated Anti-Leakage Testing Suite",
               "The system shall include an automated invariance testing harness that permutes future transactions (t > T) and asserts that past "
               "feature representations remain strictly invariant, failing the build if any backward information flow is detected.")

    add_bullet("FR7: Quantitative TreeSHAP Local Risk Attribution",
               "For every transaction flagged above the calibrated decision threshold, the system shall compute exact game-theoretic Shapley values "
               "via TreeSHAP, decomposing the risk score into ordinary tabular, pure structural topology, and TGN embedding contributions.")

    add_bullet("FR8: Visual Neo4j Subgraph Reconstruction & Interactive Replay",
               "The system shall automatically generate parameterized Cypher queries to extract the exact multi-hop path (cycles, fan-in hubs) "
               "from the graph store, rendering interactive visual audit alerts in the forensic dashboard with node-edge inspection.")

    add_h3("3.1.2 Non-Functional Requirements")
    add_bullet("Performance & Latency",
               "The feature extraction engine shall achieve sub-second processing latency (<50ms per transaction), and full end-to-end scoring "
               "(topology extraction + TGN embedding + XGBoost inference + SHAP attribution) shall execute within 200ms per transaction.")

    add_bullet("Scalability & Memory Efficiency",
               "The compute path shall support streaming datasets exceeding 6 million transactions (e.g., PaySim) without exhausting RAM by "
               "utilizing chunked sliding windows in Python, decoupling analytical compute from the Neo4j visualization store.")

    add_bullet("Reliability & Reproducibility",
               "Model training and feature generation shall be mathematically deterministic across random seeds. All trained model weights, "
               "scalers, frozen decision thresholds, and feature columns shall be persisted as self-describing versioned artifacts.")

    add_bullet("Security & Data Confidentiality",
               "The system shall enforce role-based access control (RBAC), ensuring that financial ledgers are protected via AES-256 encryption "
               "at rest and TLS 1.3 in transit, with immutable logging of all forensic auditor queries to satisfy statutory audit standards.")

    add_bullet("Usability & Human-Centered Design",
               "The auditor dashboard shall present intuitive, color-coded risk categorizations, waterfall SHAP attribution charts, and interactive "
               "D3/SVG network graphs, enabling non-technical internal auditors to interpret evidence without machine learning expertise.")

    add_bullet("Maintainability & Modularity",
               "The codebase shall follow a clean six-package modular architecture (common, etl, graph, topology, features, modeling) with "
               "strict typing, comprehensive unit tests, and standardized pip editable package installation.")

    add_bullet("Compliance & Regulatory Standards",
               "The system's audit trails and explanation outputs shall comply with Sarbanes-Oxley (SOX) Section 404 internal control verification, "
               "Basel III operational risk management mandates, and ISAE 3402 service organization reporting guidelines.")

    # 3.2 Feasibility Study
    add_h2("3.2 Feasibility Study")

    add_h3("3.2.1 Technical Feasibility")
    tech_text = (
        "The project demonstrates high technical feasibility by building upon mature, industrially proven open-source technologies. "
        "Python 3.14 provides high-performance data processing libraries (Pandas, NumPy, NetworkX) capable of executing streaming sliding-window "
        "graph algorithms in memory. XGBoost offers state-of-the-art tree-boosting capabilities with native multi-threaded CPU execution and "
        "exact TreeSHAP explainability. PyTorch provides a flexible environment for training small, parameter-efficient TGN memory networks "
        "directly on CPU without requiring expensive GPU compute clusters.\n\n"
        "Critically, technical feasibility was validated by resolving the architectural bottleneck of the predecessor system: by decoupling "
        "the compute engine (executed in Python) from the visualization layer (Neo4j), the system eliminates the Out-Of-Memory (OOM) crashes "
        "that plagued prior in-database Cypher graph algorithm implementations at scale. Automated unit and regression test suites achieve "
        "100% pass rates on zero-lookahead invariance gates."
    )
    add_p(tech_text, align=WD_ALIGN_PARAGRAPH.JUSTIFY, line_spacing=1.15, space_before=0, space_after=8)

    add_h3("3.2.2 Economic Feasibility")
    econ_text = (
        "The economic feasibility of The Self-Auditing Ledger is compelling for enterprise organizations. Corporate fraud imposes devastating "
        "financial losses; according to the Association of Certified Fraud Examiners (ACFE), organizations lose an average of 5% of annual "
        "revenue to occupational fraud, with an average loss per enterprise case exceeding $1.7 million. External financial audits require "
        "hundreds of thousands of dollars in manual sampling fees yet inspect less than 5% of transactions.\n\n"
        "The proposed system was developed entirely using open-source software (Python, Neo4j Community Edition, Scikit-Learn, PyTorch), "
        "requiring zero proprietary software licensing fees. It runs efficiently on standard enterprise commodity workstations or existing "
        "cloud virtual machines. By transitioning enterprises from periodic manual sampling to 100% continuous ledger screening, the system "
        "delivers an immediate Return on Investment (ROI) by catching collusive laundering before capital is irrevocably dispersed."
    )
    add_p(econ_text, align=WD_ALIGN_PARAGRAPH.JUSTIFY, line_spacing=1.15, space_before=0, space_after=8)

    add_h3("3.2.3 Social Feasibility")
    soc_text = (
        "The social feasibility of the system centers on auditor acceptance, ethical artificial intelligence, and corporate governance. "
        "A major impediment to AI adoption in corporate finance is the fear that automated algorithms will replace human auditors or generate "
        "arbitrary, unchallengeable decisions. The Self-Auditing Ledger is explicitly designed as a Human-in-the-Loop decision support tool: "
        "it never takes unilateral punitive action; instead, it delivers a transparent, evidentiary dossier (TreeSHAP drivers + Neo4j visual paths) "
        "that empowers human auditors to substantiate investigations.\n\n"
        "Furthermore, the project adheres strictly to ethical AI principles: features are restricted to operational transaction mechanics "
        "(amounts, timestamps, network connectivity), explicitly omitting sensitive personal or demographic attributes to prevent algorithmic bias. "
        "The project directly advances the United Nations Sustainable Development Goals (SDGs): SDG 8 (Decent Work and Economic Growth) through "
        "financial integrity, SDG 9 (Industry, Innovation, and Infrastructure) through advanced enterprise AI, and SDG 16 (Peace, Justice, and Strong "
        "Institutions) by combating corruption and illicit financial flows."
    )
    add_p(soc_text, align=WD_ALIGN_PARAGRAPH.JUSTIFY, line_spacing=1.15, space_before=0, space_after=12)

    # 3.3 System Specification
    add_h2("3.3 System Specification")

    add_h3("3.3.1 Hardware Specification")
    add_p("The system was engineered and benchmarked under the following hardware environments:", line_spacing=1.15, space_before=0, space_after=4)
    add_bullet("Processor (CPU)", "Intel Core i7-12700H / AMD Ryzen 7 5800H (8 Cores / 16 Threads, 3.2 GHz base, 4.7 GHz boost) or higher.")
    add_bullet("System Memory (RAM)", "16 GB DDR4/DDR5 (Minimum); 32 GB RAM recommended for multi-million transaction streaming graphs.")
    add_bullet("Storage", "512 GB NVMe Solid State Drive (M.2 PCIe Gen 4, minimum 3,500 MB/s read speed for fast Parquet/CSV ingestion).")
    add_bullet("Graphics Processing Unit (GPU)", "NVIDIA GeForce RTX 3060 (6 GB VRAM) / RTX 4070 (Optional; CPU execution fully supported for PyTorch/XGBoost).")
    add_bullet("Display", "Full HD (1920 x 1080) LED Backlit Display (Optimal for multi-window Neo4j graph visualization and dashboard analysis).")

    add_h3("3.3.2 Software Specification")
    add_p("The software stack comprises modern, stable, open-source programming frameworks:", line_spacing=1.15, space_before=0, space_after=4)
    add_bullet("Operating System", "Microsoft Windows 11 Pro (64-bit) / Ubuntu Linux 22.04 LTS.")
    add_bullet("Programming Language", "Python 3.14.0 (64-bit runtime) with native type annotations and asyncio support.")
    add_bullet("Development Environment", "Visual Studio Code / Antigravity IDE with Git version control.")
    add_bullet("Machine Learning Libraries", "XGBoost 2.1.0, Scikit-Learn 1.5.0, PyTorch 2.4.0 (CPU/CUDA), SHAP 0.45.0.")
    add_bullet("Graph Analysis Engines", "NetworkX 3.3, iGraph 0.11.5, Neo4j Python Driver 5.20.0.")
    add_bullet("Database Management System", "Neo4j Community Edition 5.18.0 (Graph Database, APOC library, Cypher query engine).")
    add_bullet("Data Processing & Serialization", "Pandas 2.2.2, NumPy 2.0.0, PyArrow 16.1.0, Joblib 1.4.2.")
    add_bullet("Visualization & Testing Tools", "Matplotlib 3.9.0, Seaborn 0.13.2, Plotly 5.22.0, D3.js, Pytest 8.2.0.")
    doc.add_page_break()

    # ==========================================
    # 4. DESIGN APPROACH AND DETAILS
    # ==========================================
    add_h1("4. DESIGN APPROACH AND DETAILS")

    add_h2("4.1 System Architecture")
    arch_intro = (
        "The Self-Auditing Ledger is designed as a decoupled, multi-stage pipeline where data flows strictly in chronological order. "
        "The architecture is organized into four discrete operational stages, illustrated in Figure 2."
    )
    add_p(arch_intro, align=WD_ALIGN_PARAGRAPH.JUSTIFY, line_spacing=1.15, space_before=0, space_after=8)

    add_fig("artifacts/report_figures/fig2_system_architecture.png", "Fig. 2. End-to-End System Architecture of The Self-Auditing Ledger", width=Inches(6.2))

    arch_details = (
        "Stage 1: Ingestion and Canonical ETL (src/etl/)\n"
        "The data layer continuously receives raw financial ledgers from enterprise ERP tables (SAP BKPF header and BSEG segment tables) "
        "and benchmark datasets. Disparate accounts, vendors, and customers are normalized into a unified Account node space with directed "
        "TRANSFERS_TO edges, eliminating the predecessor's identity-splitting flaw. Temporal fields are coerced into consistent chronological "
        "counters without fabricating artificial intra-tick sequence.\n\n"
        "Stage 2: Streaming Zero-Lookahead Topology Engine (src/topology/)\n"
        "As transactions arrive, the topology engine computes structural metrics against historical graph state strictly as of timestamp T "
        "(t <= T). It maintains sliding temporal windows (1h, 24h, 7d) and executes five specialized detectors: directed cycles (2-hop and 3-hop "
        "loops with amount conservation), fan-in collection hubs, transfer burst velocity, connection density, and temporal in-degree velocity. "
        "Only after features are extracted is the current transaction committed to the active graph, mathematically guaranteeing zero lookahead leakage.\n\n"
        "Stage 3: Hybrid Modeling and Continuous-Time Representation (src/modeling/)\n"
        "A composite feature matrix is assembled combining tabular transaction variables, handcrafted graph topology metrics, and continuous-time "
        "Temporal Graph Network (TGN) 32-dimensional node memory embeddings. The model workhorse is a cost-sensitive XGBoost classifier optimized "
        "via a custom alpha-free focal loss. Optimal decision thresholds are tuned exclusively on validation periods and frozen before evaluating test sets.\n\n"
        "Stage 4: Dual-Layer Explainability and Audit Alert Dispatch (src/graph/, demo/)\n"
        "When an incoming transaction exceeds the calibrated decision threshold, an audit alert is dispatched containing two evidentiary layers: "
        "(1) Quantitative TreeSHAP waterfall values decomposing the score into exact feature contributions; and (2) Visual Neo4j subgraph "
        "reconstructions rendering the concrete multi-hop flow of funds in an interactive forensic dashboard."
    )
    add_p(arch_details, align=WD_ALIGN_PARAGRAPH.JUSTIFY, line_spacing=1.15, space_before=0, space_after=12)

    # 4.2 Design
    add_h2("4.2 Design")

    # 4.2.1 Data Flow Diagram
    add_h3("4.2.1 Data Flow Diagram (DFD)")
    dfd_intro = (
        "The movement of data through The Self-Auditing Ledger is modeled using hierarchical Data Flow Diagrams. Figure 3 illustrates both "
        "the Level 0 Context Diagram and the decomposed Level 1 Functional Flow Diagram."
    )
    add_p(dfd_intro, align=WD_ALIGN_PARAGRAPH.JUSTIFY, line_spacing=1.15, space_before=0, space_after=8)

    add_fig("artifacts/report_figures/fig3_data_flow_diagram.png", "Fig. 3. Data Flow Diagrams: (a) Level 0 Context Diagram, (b) Level 1 Decomposed Flow", width=Inches(6.2))

    dfd_desc = (
        "In the Level 0 Context Diagram (Fig. 3a), the system boundary interacts with three external entities: the Enterprise ERP / Banking Feeds "
        "(which stream raw transaction journals), the Forensic Auditor / Compliance Team (who receive explainable audit alerts and provide investigation feedback), "
        "and System Administrators (who configure sliding windows and model thresholds). All ledger processing occurs within the 0.0 Self-Auditing Ledger Engine.\n\n"
        "In the Level 1 DFD (Fig. 3b), the system is decomposed into five coordinated processes:\n"
        "• Process 1.0 (Canonical ETL & Normalization): Ingests raw ERP records, strips formatting artifacts, unifies sender and receiver account namespaces, "
        "and stores standardized transaction edges into D1 (Canonical Transaction Store).\n"
        "• Process 2.0 (Streaming Zero-Lookahead Topology): Pulls standardized transactions chronologically, queries the historical graph state (t <= T), "
        "computes sliding-window structural metrics, and feeds the feature vector forward before committing the edge.\n"
        "• Process 3.0 (Hybrid Risk Scoring): Merges ordinary tabular features, structural metrics, and self-supervised TGN memory vectors, scoring "
        "calibrated fraud risk probabilities via cost-sensitive XGBoost.\n"
        "• Process 4.0 (Explainability & Path Traversal): When fraud probability exceeds the frozen threshold (P >= Tau), this process computes exact "
        "TreeSHAP local attributions and executes Cypher graph traversals against D2 (Neo4j Graph Database) to extract the connected multi-hop transaction path.\n"
        "• Process 5.0 (Audit Dispatch & Visual Replay): Packages quantitative SHAP drivers and interactive Neo4j visual subgraphs into an audit-grade "
        "alert dossier dispatched to the forensic compliance workstation."
    )
    add_p(dfd_desc, align=WD_ALIGN_PARAGRAPH.JUSTIFY, line_spacing=1.15, space_before=0, space_after=12)

    # 4.2.2 Use Case Diagram
    add_h3("4.2.2 Use Case Diagram")
    uc_intro = (
        "The functional interactions between users and system modules are formally captured in Figure 4. The system defines three primary actors: "
        "the Forensic Auditor, the System Administrator, and the Enterprise ERP Source."
    )
    add_p(uc_intro, align=WD_ALIGN_PARAGRAPH.JUSTIFY, line_spacing=1.15, space_before=0, space_after=8)

    add_fig("artifacts/report_figures/fig4_use_case_diagram.png", "Fig. 4. Use Case Diagram for The Self-Auditing Ledger Framework", width=Inches(6.0))

    uc_desc = (
        "The Use Case specifications encompass seven core operations:\n"
        "• UC1: Ingest & Canonicalize ERP Feed (Initiated by ERP Source / SysAdmin): Continuously validates schemas, strips delimiter noise, and resolves entity IDs into a canonical bipartite structure.\n"
        "• UC2: Extract Zero-Lookahead Topology (System Automated): Dynamically computes sliding-window network metrics against past-only graph snapshots.\n"
        "• UC3: Real-Time Fraud Scoring & Calibrated Risk (System Automated): Evaluates transactions through the hybrid TGN-XGBoost classifier to produce calibrated fraud probabilities.\n"
        "• UC4: Inspect High-Risk Audit Alerts (Forensic Auditor): Surfaces high-risk transactions ranking in the top-k (Precision@100) queue for forensic inspection.\n"
        "• UC5: Analyze TreeSHAP Quantitative Drivers (Forensic Auditor): Decomposes the transaction's fraud score into exact feature contribution waterfall plots.\n"
        "• UC6: Replay Multi-Hop Neo4j Money Paths (Forensic Auditor): Interactively renders and traverses the exact cycle or fan-in subgraph in Neo4j.\n"
        "• UC7: Validate Invariance & Export SOX Trail (Auditor / SysAdmin): Executes automated leakage verification tests and generates immutable forensic audit reports for regulatory compliance."
    )
    add_p(uc_desc, align=WD_ALIGN_PARAGRAPH.JUSTIFY, line_spacing=1.15, space_before=0, space_after=12)

    # 4.2.3 Class Diagram
    add_h3("4.2.3 Class Diagram")
    class_intro = (
        "The static structural object model of the system is depicted in Figure 5, illustrating the core domain classes, their attributes, "
        "methods, and encapsulation boundaries."
    )
    add_p(class_intro, align=WD_ALIGN_PARAGRAPH.JUSTIFY, line_spacing=1.15, space_before=0, space_after=8)

    add_fig("artifacts/report_figures/fig5_class_diagram.png", "Fig. 5. Class Diagram for The Self-Auditing Ledger Architecture", width=Inches(6.2))

    class_desc = (
        "Key domain classes within the system architecture include:\n"
        "• ERPTransaction: Represents an atomic ledger posting with txn_id, sender_id, receiver_id, amount, timestamp, and label, providing schema validation methods.\n"
        "• TemporalShadowGraph: Encapsulates the dynamic NetworkX/igraph multi-directed graph, managing sliding temporal windows and as-of historical snapshot queries.\n"
        "• TopologyEngine: Houses the specialized structural fraud detectors (detect_cycles, compute_density, compute_velocity) and outputs the structured topology feature matrix.\n"
        "• HybridFraudClassifier: Manages the XGBoost model, custom focal loss objective, TGN embedding interface, threshold calibration, and scoring routines.\n"
        "• DualLayerAlertDispatcher: Integrates the TreeSHAP explainer with the Neo4j bolt driver to assemble composite audit alert dossiers.\n"
        "• AuditAlert: The evidentiary entity containing calibrated risk probability, exact SHAP attribution dictionaries, verified subgraph paths, and auditor feedback status."
    )
    add_p(class_desc, align=WD_ALIGN_PARAGRAPH.JUSTIFY, line_spacing=1.15, space_before=0, space_after=12)

    # 4.2.4 Sequence Diagram
    add_h3("4.2.4 Sequence Diagram")
    seq_intro = (
        "The dynamic runtime behavior and message sequencing of the system are modeled in Figure 6, tracing the complete lifecycle of an "
        "incoming ERP transaction from ingestion to visual audit dispatch."
    )
    add_p(seq_intro, align=WD_ALIGN_PARAGRAPH.JUSTIFY, line_spacing=1.15, space_before=0, space_after=8)

    add_fig("artifacts/report_figures/fig6_sequence_diagram.png", "Fig. 6. Sequence Diagram: Real-Time Ingestion, Scoring, and Audit Dispatch", width=Inches(6.2))

    seq_desc = (
        "The execution sequence proceeds through ten rigorous chronological steps:\n"
        "1. The ERP Feed streams a raw transaction posting to the Canonical ETL Engine.\n"
        "2. Canonical ETL normalizes entity namespaces and forwards the transaction edge to the Streaming Topology Engine at timestamp T.\n"
        "3. The Topology Engine queries the graph state strictly as-of timestamp T (asserting t <= T) and calculates structural metrics (cycles, fan-in, density).\n"
        "4. The Topology Engine returns the extracted structural vector and subsequently commits the current edge into the historical graph.\n"
        "5. Canonical ETL merges ordinary tabular features, structural metrics, and TGN memory embeddings into the Hybrid Model.\n"
        "6. The Hybrid Model executes inference and evaluates whether P(fraud) >= Tau_frozen (the threshold calibrated on validation data).\n"
        "7. For transactions exceeding the threshold, the Hybrid Model triggers the Dual-Layer Explanation Dispatcher.\n"
        "8. The Dispatcher computes exact TreeSHAP attributions and executes a parameterized Cypher query against the Neo4j store to extract the multi-hop subgraph path.\n"
        "9. The Dispatcher packages the quantitative SHAP drivers and interactive Neo4j visual graph into an Audit Alert sent to the Forensic Auditor dashboard.\n"
        "10. The Forensic Auditor reviews the evidentiary dossier, inspects the visual transaction path, and records forensic feedback."
    )
    add_p(seq_desc, align=WD_ALIGN_PARAGRAPH.JUSTIFY, line_spacing=1.15, space_before=0, space_after=15)
    doc.add_page_break()

    # ==========================================
    # 5. REFERENCES
    # ==========================================
    add_h1("5. REFERENCES")

    add_h2("Weblinks:")
    weblinks = [
        "https://www.acfe.com/report-to-the-nations/2024/ (Association of Certified Fraud Examiners - 2024 Global Fraud Study).",
        "https://neo4j.com/docs/graph-data-science/current/ (Neo4j Graph Data Science Library Documentation & Cypher Manual).",
        "https://xgboost.readthedocs.io/en/stable/ (XGBoost Documentation: Scalable, Portable and Distributed Gradient Boosting).",
        "https://shap.readthedocs.io/en/latest/ (SHAP: Unified Approach to Interpreting Model Predictions via Game Theory)."
    ]
    for idx, link in enumerate(weblinks, 1):
        add_p(f"{idx}.  {link}", line_spacing=1.15, space_before=2, space_after=4, size=11)

    add_h2("Journals: <IEEE Format>")
    journals = [
        "S. Motie and B. Raahemi, \"Financial fraud detection using graph neural networks: A systematic review,\" Expert Systems with Applications, vol. 240, p. 122557, Apr. 2024.",
        "N. Innan et al., \"Financial fraud detection using quantum graph neural networks,\" Quantum Machine Intelligence, vol. 6, no. 1, pp. 1-14, Feb. 2024.",
        "M. Grossi et al., \"Mixed quantum-classical method for fraud detection with quantum feature selection,\" IEEE Transactions on Quantum Engineering, vol. 3, pp. 1-12, 2022.",
        "R. R. Devi, J. E. Raja, and Y. B. Chin, \"RL-GNN fusion for real-time financial fraud detection,\" Scientific Reports, vol. 15, no. 1, p. 1042, 2025.",
        "Z. N. Jawad et al., \"ML-driven optimization of ERP systems: A comprehensive review,\" Discover Artificial Intelligence, vol. 4, no. 1, pp. 1-28, 2024.",
        "Z. Yuan et al., \"A comprehensive survey on GNN-based anomaly detection,\" ACM Computing Surveys, vol. 57, no. 3, pp. 1-39, 2025.",
        "L. Zhi et al., \"Imbalanced fraudulent transaction detection based on embedding-aware conditional GAN,\" Journal of Big Data, vol. 12, no. 1, pp. 1-22, 2025.",
        "G. Tong et al., \"Financial transaction fraud detector based on imbalance learning and GNN,\" Applied Intelligence, vol. 53, no. 14, pp. 17820-17835, 2023.",
        "M. Boyapati et al., \"BalancerGNN: Balancer GNNs for imbalanced datasets,\" IEEE Access, vol. 13, pp. 14201-14215, 2025.",
        "X. J. Mamakou et al., \"Post-implementation evaluation of ERP systems: An internal auditors' perspective,\" Information Systems Management, vol. 41, no. 2, pp. 180-198, 2024.",
        "M. A. Vasarhelyi, M. G. Alles, and K. T. Williams, \"The acceptance and adoption of continuous auditing by internal auditors,\" International Journal of Accounting Information Systems, vol. 13, no. 3, pp. 267-281, 2012.",
        "S. M. Lundberg et al., \"From local explanations to global understanding with explainable AI for trees,\" Nature Machine Intelligence, vol. 2, no. 1, pp. 56-67, 2020."
    ]
    for idx, jnl in enumerate(journals, 1):
        add_p(f"{idx}.  {jnl}", line_spacing=1.15, space_before=2, space_after=4, size=11)

    add_h2("Conferences: <IEEE Format>")
    conferences = [
        "Y. Shi et al., \"Uncertainty-aware spatio-temporal contrastive GNNs for financial fraud detection,\" in Proceedings of the AAAI Conference on Artificial Intelligence (AAAI-26), vol. 40, 2026, pp. 1420-1428.",
        "H. Wang, N. Liu, and Q. Tan, \"Reinforced Causal Explainer for Graph Neural Networks,\" in Proceedings of the ACM Web Conference 2023 (WWW '23), Austin, TX, USA, 2023, pp. 432-442.",
        "E. Rossi et al., \"Temporal Graph Networks for Deep Learning on Dynamic Graphs,\" in ICML Workshop on Graph Representation Learning and Beyond, 2020, pp. 1-12.",
        "A. Salih, S. T. Zeebaree, S. Ameen, A. Alkhyyat, and H. M. Shukur, \"A survey on the role of artificial intelligence, machine learning and deep learning for cybersecurity attack detection,\" in 2021 7th International Engineering Conference (IEC), IEEE, 2021, pp. 61-66."
    ]
    for idx, conf in enumerate(conferences, 1):
        add_p(f"{idx}.  {conf}", line_spacing=1.15, space_before=2, space_after=4, size=11)

    add_h2("Books: <IEEE Format>")
    books = [
        "I. Goodfellow, Y. Bengio, and A. Courville, Deep Learning, MIT Press, Cambridge, MA, 2016.",
        "W. Hamilton, Graph Representation Learning, Morgan & Claypool Publishers, San Rafael, CA, 2020.",
        "C. M. Bishop, Pattern Recognition and Machine Learning, Springer-Verlag, New York, NY, 2006."
    ]
    for idx, bk in enumerate(books, 1):
        add_p(f"{idx}.  {bk}", line_spacing=1.15, space_before=2, space_after=4, size=11)

    # Save .docx
    docx_path = "BCSE497J_Project_I_Report.docx"
    doc.save(docx_path)
    print(f"Successfully generated official Word document: {docx_path}")

    # ==========================================
    # GENERATE COMPLETE MARKDOWN VERSION (.md)
    # ==========================================
    md_path = "BCSE497J_Project_I_Report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("""# BCSE497J - Project-I
# THE SELF-AUDITING LEDGER: FRAUD DETECTION IN ERP SYSTEMS USING TEMPORAL GRAPH TOPOLOGY

**Course Code:** BCSE497J — Project-I  
**Academic Year:** 2026 – 2027 (September 2026)  
**Institution:** School of Computer Science and Engineering (SCOPE), Vellore Institute of Technology (VIT), Vellore  

---

### Student Particulars (Sorted on Register Number):
1. **23BCE2329 — AARIN BHATTA**
2. **23BCE2335 — HIMANSHU RAY**
3. **23BCE2349 — MOHAMMED AKIF**

### Under the Supervision of:
**Prof. Dhivya C.R.**  
Assistant Professor Senior Grade 1  
School of Computer Science and Engineering (SCOPE)  
Vellore Institute of Technology (VIT)  

**Degree:** Bachelor of Technology (B.Tech.) in Computer Science and Engineering  

---

## ABSTRACT

Enterprise Resource Planning (ERP) systems process high-volume, multi-party financial transactions where conventional row-level auditing fails to detect coordinated collusion, money-mule collection funnels, and circular round-tripping. While Graph Neural Networks (GNNs) and machine learning models offer potential solutions, existing financial graph systems suffer from lookahead data leakage, unrealistic random train-test splits, and uninterpretable black-box predictions.

This project presents *The Self-Auditing Ledger*, a leakage-free-by-construction framework that transforms ERP transaction logs into continuous-time temporal graphs. An incremental, streaming topology engine extracts structural fraud features—including directed payment cycles, fan-in collection ratios, burst density, and temporal degree velocity—using strictly past-only graph snapshots ($t \\le T$). These topological metrics are combined with tabular transaction attributes and self-supervised Temporal Graph Network (TGN) embeddings to train cost-sensitive gradient boosted decision trees (XGBoost) optimized with focal loss.

Evaluated across diverse transaction network density regimes (BankSim, IBM AML, SAP Würzburg, and an agent-based synthetic ERP economy) under strict chronological splits over three random seeds, our results demonstrate that temporal graph topology delivers a statistically validated +11.7% PR-AUC lift on relational transaction networks (reaching 0.9364 PR-AUC and 1.00 Precision@100 on BankSim). The system pairs every high-risk alert with dual-layer explainability: exact TreeSHAP feature attributions and visual Neo4j subgraph reconstructions of the suspicious transaction chain for forensic verification, bridging the gap between automated artificial intelligence and internal audit compliance.

**Keywords:** ERP Fraud Detection, Temporal Graph Topology, Zero-Lookahead Leakage, Cost-Sensitive XGBoost, Temporal Graph Networks, TreeSHAP, Neo4j Visual Audit.

---

## TABLE OF CONTENTS

| Sl.No | Contents | Page No. |
| :--- | :--- | :---: |
| | **Abstract** | **i** |
| **1.** | **INTRODUCTION** | **1** |
| | 1.1 Background | 1 |
| | 1.2 Motivation | 2 |
| | 1.3 Scope of the Project | 3 |
| **2.** | **PROJECT DESCRIPTION AND GOALS** | **4** |
| | 2.1 Literature Review | 4 |
| | 2.2 Research Gap | 8 |
| | 2.3 Objectives | 9 |
| | 2.4 Problem Statement | 10 |
| | 2.5 Project Plan | 11 |
| **3.** | **TECHNICAL SPECIFICATION** | **13** |
| | 3.1 Requirements | 13 |
| | &nbsp;&nbsp;&nbsp;&nbsp;3.1.1 Functional | 13 |
| | &nbsp;&nbsp;&nbsp;&nbsp;3.1.2 Non-Functional | 14 |
| | 3.2 Feasibility Study | 15 |
| | &nbsp;&nbsp;&nbsp;&nbsp;3.2.1 Technical Feasibility | 15 |
| | &nbsp;&nbsp;&nbsp;&nbsp;3.2.2 Economic Feasibility | 16 |
| | &nbsp;&nbsp;&nbsp;&nbsp;3.2.3 Social Feasibility | 16 |
| | 3.3 System Specification | 17 |
| | &nbsp;&nbsp;&nbsp;&nbsp;3.3.1 Hardware Specification | 17 |
| | &nbsp;&nbsp;&nbsp;&nbsp;3.3.2 Software Specification | 18 |
| **4.** | **DESIGN APPROACH AND DETAILS** | **19** |
| | 4.1 System Architecture | 19 |
| | 4.2 Design | 22 |
| | &nbsp;&nbsp;&nbsp;&nbsp;4.2.1 Data Flow Diagram | 22 |
| | &nbsp;&nbsp;&nbsp;&nbsp;4.2.2 Use Case Diagram | 24 |
| | &nbsp;&nbsp;&nbsp;&nbsp;4.2.3 Class Diagram | 26 |
| | &nbsp;&nbsp;&nbsp;&nbsp;4.2.4 Sequence Diagram | 28 |
| **5.** | **REFERENCES** | **30** |

---

# 1. INTRODUCTION

### 1.1 Background
Modern enterprise accounting systems, such as SAP S/4HANA and Oracle Financials, process millions of daily journal entries governing billions of dollars in capital flow. Traditional fraud detection and statutory auditing rely on rule-based thresholds, manual sampling, and isolated debit-credit reconciliation. However, contemporary financial crimes—including invoice fraud, authorized push payment scams, money-mule funnels, and circular payment round-tripping—operate across distributed networks of seemingly independent corporate accounts and intermediary entities.

When transactions are analyzed as independent tabular rows, the structural relationships between counterparties remain completely invisible. Although graph data modeling provides a natural paradigm for representing financial networks, existing machine learning pipelines suffer from severe methodology failures: lookahead data leakage across temporal boundaries, identity-splitting between senders and receivers, and post-event information contamination.

*The Self-Auditing Ledger* bridges this gap by representing ERP transaction journals as dynamic, directed temporal graphs. By tracking evolving financial interactions chronologically, the system enables automated, continuous auditing that discovers complex multi-entity fraud structures while strictly preserving temporal causality.

### 1.2 Motivation
Financial fraud inflicts hundreds of billions of dollars in global enterprise losses annually, jeopardizing organizational solvency, corporate governance, and regulatory compliance under Sarbanes-Oxley (SOX) and Basel III standards. Conventional internal audit procedures sample less than five percent of annual transaction ledgers, frequently identifying irregularities months after capital dissipation occurs.

Recent academic interest in Graph Neural Networks (GNNs) for fraud detection has produced inflated performance claims (exceeding 99% accuracy) that collapse during enterprise deployment due to lookahead leakage, shuffled cross-validation, and metric distortion on heavily imbalanced datasets (<1% fraud). Furthermore, complex neural architectures function as inscrutable black boxes, generating raw risk scores that internal auditors cannot legally justify or substantiate in forensic proceedings.

This project is motivated by the urgent necessity for a scientifically rigorous, leakage-free continuous audit framework. By uniting streaming temporal graph feature extraction, cost-sensitive machine learning, and dual-layer explainability (exact TreeSHAP game-theoretic attributions coupled with interactive Neo4j visual path reconstruction), we empower forensic auditors to detect sophisticated relational fraud in real time while providing verifiable, audit-grade visual evidence.

### 1.3 Scope of the Project
The scope of this project encompasses the design, implementation, and empirical validation of an end-to-end continuous auditing framework for enterprise transaction ledgers. The research covers four diverse benchmark financial datasets spanning distinct structural graph densities: IBM AML (multi-hop cycle and fan-in flows), BankSim (bipartite customer-merchant network), SAP Würzburg (genuine ERP general ledger entries), and an agent-based synthetic ERP simulation.

Key technical deliverables include:
1. Canonical ETL pipeline unifying disparate account namespaces into directed temporal multi-graphs.
2. Streaming, zero-lookahead topology engine extracting sliding-window structural metrics (directed cycles, fan-in hubs, transfer velocity).
3. Continuous-time Temporal Graph Network (TGN) self-supervised node memory embedder.
4. Cost-sensitive XGBoost classification engine with focal loss optimization and time-aware threshold calibration.
5. Automated invariance testing framework verifying zero future-to-past data leakage.
6. Dual-layer explainability dashboard integrating exact TreeSHAP feature breakdowns with visual Neo4j subgraph traversal and interactive replay.

The project explicitly excludes production deployment inside proprietary SAP ABAP application servers and real-time bank settlement gateways, focusing on post-posting continuous ledger auditing and forensic investigation.

---

# 2. PROJECT DESCRIPTION AND GOALS

### 2.1 Literature Review
Financial fraud detection in enterprise networks represents a convergence of three mature disciplines: graph representation learning, extreme class imbalance modeling, and continuous accounting audit automation.

#### 2.1.1 Graph Neural Networks and Graph-Based Fraud Detection
Graph Neural Networks (GNNs) have emerged as the primary research vehicle for network anomaly detection. Motie and Raahemi [1] conducted a comprehensive systematic survey of GNN architectures for financial fraud, identifying that while Relational Graph Convolutional Networks (R-GCN) and Graph Attention Networks (GAT) effectively propagate structural neighbor representations, they suffer from severe susceptibility to neighbor camouflage, heavy computational complexity during multi-hop aggregation, and complete opacity regarding forensic explainability. Innan et al. [2] and Grossi et al. [3] explored quantum graph neural networks and hybrid quantum-classical feature selection for credit card fraud, demonstrating theoretical acceleration in subgraph pattern matching but remaining restricted to small-scale synthetic simulations due to current physical qubit hardware constraints.

Addressing temporal dynamics, Devi et al. [4] investigated reinforcement learning coupled with GNN fusion for real-time transaction scoring, highlighting the necessity of capturing transaction velocity. Yuan et al. [6] provided an extensive taxonomy of graph anomaly detection, demonstrating that static graph projections fail when transaction semantics depend on precise temporal sequence and latency between counterparty hops. Shi et al. [7] formulated uncertainty-aware spatio-temporal contrastive GNNs to handle evolving fraud typologies, validating that fraud patterns shift dynamically across operational time windows.

#### 2.1.2 Class Imbalance Learning and Loss Function Formulations
Financial transaction ledgers exhibit extreme class imbalance, where fraudulent entries comprise between 0.1% and 1.2% of total volume. Tong et al. [9] and Boyapati et al. [10] demonstrated that standard cross-entropy objectives collapse toward predicting the majority legitimate class. A prevalent mitigation strategy in literature is synthetic minority oversampling (SMOTE). However, as proven by Zhi et al. [8], linear interpolation between graph node feature vectors creates non-physical pseudo-nodes that violate graph topological invariants—such as creating an artificial vector that represents 'half a directed cycle.'

In contrast, loss function reweighting and cost-sensitive learning avoid dataset corruption. Lin et al. and recent advancements in Boundary Focal Loss introduce dynamic modulating factors $(1 - p_t)^\\gamma$ that down-weight trivial, well-classified negative instances, concentrating gradient updates on ambiguous decision boundary instances. Furthermore, comparative evaluations by Chen et al. demonstrate that on structured tabular data, gradient boosted decision trees (XGBoost, LightGBM) consistently match or exceed deep neural networks in classification accuracy while maintaining orders-of-magnitude faster CPU training times and superior numerical stability.

#### 2.1.3 Continuous Auditing in ERP Systems and Explainable AI (XAI)
In enterprise accounting, Vasarhelyi et al. [12] established the foundational theory of Continuous Auditing (CA), proving that periodic retrospective audits fail to safeguard corporate assets in high-throughput enterprise resource planning systems. Mamakou et al. [11] evaluated post-implementation internal control failures in ERP environments, finding that over 80% of corporate accounting frauds involve authorized users circumventing Segregation of Duties (SoD) through collusive multi-step journal postings.

Jawad et al. [5] surveyed machine learning optimization in enterprise systems, emphasizing that internal auditors cannot adopt predictive models unless predictions are fully explainable and legally defensible under corporate governance mandates. While post-hoc explainers like LIME or permutation importance provide coarse approximations, Lundberg et al.'s TreeSHAP algorithm [17] guarantees exact, game-theoretically optimal local feature attributions for tree ensembles. Complementing feature attributions, Wang et al. [21] introduced causal graph explainers, establishing that forensic auditability requires extracting connected, causally faithful subgraphs that visually substantiate how collusive funds propagated across accounts.

#### Table 2.1: Comparative Synthesis of Literature
| Author & Year | Proposed Methodology | Key Findings & Contribution | Project Alignment & Differentiation |
| :--- | :--- | :--- | :--- |
| **Motie & Raahemi (2024)** [1] | Systematic review of GNNs in financial fraud | Identified R-GCN and GAT effectiveness; highlighted camouflage and explainability bottlenecks | Validates graph modeling; our system extracts explicit interpretable topology instead of black-box embeddings |
| **Devi, Raja, & Chin (2025)** [4] | RL-GNN fusion for real-time transaction fraud | Proved real-time transaction scoring requires dynamic velocity and sequential relationship modeling | Adopted temporal sliding windows; replaced complex RL with deterministic zero-lookahead feature extractors |
| **Jawad et al. (2024)** [5] | ML optimization review in ERP architectures | Emphasized continuous internal audit integration and strict explainability requirements for auditors | Directly targets ERP accounting ledgers; satisfies audit compliance via dual-layer TreeSHAP + Neo4j alert dispatch |
| **Yuan et al. (2025)** [6] | Comprehensive survey on GNN anomaly detection | Static graph models fail when temporal intervals and sequence ordering govern malicious activity | Enforces continuous-time temporal shadow graph where edges are strictly timestamped and traversed chronologically |
| **Shi et al. (2026)** [7] | Spatio-temporal contrastive GNNs (AAAI) | Showed uncertainty-aware representations mitigate evolving fraud typologies over time horizons | Incorporates self-supervised TGN memory vectors alongside explicit sliding-window structural features |
| **Zhi et al. (2025)** [8] | Conditional GAN for imbalanced fraud graphs | Proved SMOTE oversampling distorts network topology and creates non-physical graph structures | Enforces locked decision: zero synthetic oversampling for graph features; uses focal loss and scale_pos_weight exclusively |
| **Boyapati et al. (2025)** [10] | BalancerGNN for extreme imbalance | Demonstrated standard cross-entropy fails on rare events without adaptive gradient re-weighting | Implements alpha-free custom focal loss objective in XGBoost, collapsing run-to-run seed variance |
| **Mamakou et al. (2024)** [11] | Post-implementation audit review of ERPs | Found manual sampling catches <5% of fraud; internal collusion bypasses static ERP controls | Provides continuous automated screening across 100% of transaction entries, eliminating audit sampling blindspots |
| **Vasarhelyi et al. (2012)** [12] | Foundational continuous auditing framework | Established theoretical necessity of real-time monitoring over retrospective periodic audits | Operationalizes continuous auditing theory into an automated, streaming Python/Neo4j software prototype |
| **Lundberg et al. (2020)** [17] | TreeSHAP exact local explanation algorithm | Guarantees exact, game-theoretically optimal feature attributions in polynomial time for tree models | Selected XGBoost champion specifically to leverage exact TreeSHAP attribution for every flagged transaction |
| **Wang et al. (2023)** [21] | Reinforced Causal Explainer (RC-Explainer) | Proved valid graph explanations require connected, causally faithful subgraphs rather than isolated weights | Pioneered dual-layer audit alert: combines quantitative TreeSHAP waterfall values with visual multi-hop Neo4j paths |

---

### 2.2 Research Gap
Despite extensive literature in machine learning for financial fraud, an in-depth audit of existing frameworks identifies four fundamental research and engineering gaps:

1. **Absence of Explicit Fraud Topology Extraction in Deep Graph Learning:** Current GNN approaches project graph nodes into high-dimensional latent embedding spaces. While effective for raw classification, these embeddings completely obscure whether a transaction participated in a circular round-trip, a mule collection fan-in hub, or a rapid layering transfer chain. Forensic auditors cannot present latent mathematical vectors as evidence in legal or regulatory proceedings. There is a lack of systems that explicitly detect and extract named topological fraud shapes as first-class feature vectors.
2. **Pervasive Lookahead Data Leakage in Published Graph Fraud Models:** Published research papers routinely report near-perfect detection metrics (>0.99 ROC-AUC) on financial datasets. However, our methodological audit proves that these results are overwhelmingly artifacts of data leakage. Feature extractors compute centrality and community metrics over the full static graph (all timestamps simultaneously), crediting structure signals back to early members using future information. Similarly, train-test splits are performed via randomly shuffled cross-validation, allowing models to learn patterns from future transactions to predict past events. No prior system implements a provably zero-lookahead temporal engine guaranteed by automated invariance testing.
3. **Confounded Evaluations, Flawed Imbalance Combinations, and Missing Ablations:** A critical flaw in rare-event modeling literature is the simultaneous application of synthetic oversampling (SMOTE) and cost-sensitive class weighting, resulting in uncontrolled gradient distortion. Furthermore, models are evaluated using ROC-AUC (which is flattered by millions of trivial negative transactions) or fixed 0.5 decision thresholds. Most critically, literature lacks clean, within-dataset ablation studies that isolate whether graph topology adds statistically validated predictive lift over a strong tabular baseline when measured via Precision-Recall AUC (PR-AUC) and operational Precision@k.
4. **Domain Disconnect Between Academic Graph Benchmarks and Enterprise ERP Ledgers:** The vast majority of graph fraud research focuses on consumer credit cards or social networks. Enterprise Resource Planning (ERP) systems (e.g., SAP general ledgers BKPF/BSEG) operate under strict double-entry bookkeeping rules, bipartite document-account linkages, and internal control frameworks (Segregation of Duties). Prior graph systems fail to bridge this domain gap, suffering from identity-splitting bugs where sender and receiver accounts are placed into disjoint namespaces, rendering cycles invisible.

---

### 2.3 Objectives
To resolve the identified research gaps, the primary goals of this project are formulated using the SMART framework:
- **Specific (S):** Construct a continuous-time Temporal Shadow Graph directly from ERP transaction logs with a unified account namespace, and engineer a streaming zero-lookahead topology engine that extracts explicit fraud shapes (directed payment cycles, fan-in hubs, transfer velocity, and connection density) using strictly past-only graph snapshots ($t \\le T$).
- **Measurable (M):** Demonstrate statistically significant predictive improvement over a strong tabular baseline via PR-AUC and operational Precision@100 across three random seeds, targeting >10% relative PR-AUC lift on structurally rich transaction networks while maintaining an automated leakage test suite that guarantees zero future-to-past information leakage.
- **Achievable (A):** Decouple the heavy graph computation path (executed deterministically in Python using Pandas and NetworkX) from the visual audit explanation path (rendered in Neo4j), preventing graph database out-of-memory crashes and ensuring sub-second inference latency on commodity CPU hardware.
- **Relevant (R):** Provide enterprise-grade, dual-layer forensic explainability by coupling exact TreeSHAP quantitative feature attributions with interactive Neo4j visual subgraph path reconstructions, satisfying statutory audit compliance under SOX Section 404 and Basel III.
- **Time-bound (T):** Execute the project across eight structured work packages over a 16-week timeline, culminating in fully validated benchmark ablations, a working interactive demonstration tool, and complete technical documentation by September 2026.

---

### 2.4 Problem Statement
Enterprise Resource Planning (ERP) accounting databases record high-velocity, multi-party financial transactions where fraudulent activities (e.g., round-trip money laundering, supplier impersonation, and collusive mule networks) manifest as complex structural patterns distributed across time and multiple entities. Existing fraud detection methodologies fail because:
1. Row-level tabular auditing models evaluate individual ledger postings in isolation, ignoring topological network dependencies;
2. Deep graph neural networks produce black-box risk scores devoid of human-interpretable topological evidence, preventing statutory audit substantiation;
3. Published graph anomaly pipelines suffer from lookahead data leakage and flawed cross-validation, inflating offline metrics while failing catastrophically in production streaming environments;
4. Severe class imbalance (<1% fraud) is mishandled through destructive oversampling that distorts network structures.

The core scientific challenge addressed by this project is: *Can we engineer a continuous-time temporal graph auditing system that extracts explicit, interpretable topological fraud shapes strictly from historical graph state ($t \\le T$) without lookahead leakage, and prove that these structural features deliver statistically significant, defensible predictive lift over a strong tabular baseline under rigorous rare-event metrics?*

---

### 2.5 Project Plan
The project was executed following an agile research and engineering methodology spanning 16 weeks (June 2026 to September 2026). The implementation lifecycle was partitioned into eight distinct, sequential tasks with seven critical milestone verification gates.

![Fig. 1. Gantt Chart](artifacts/report_figures/fig1_gantt_chart.png)

#### Table 2.2: Milestone and Task Breakdown Table
| Task ID | Task Description | Timeline | Milestone | Key Deliverables & Artifacts |
| :--- | :--- | :---: | :---: | :--- |
| **Task 1** | Literature Survey & Research Gap Study | Wks 1 - 3 | M1: Survey | Review of 12 peer-reviewed papers; formulated research gaps and thesis |
| **Task 2** | Dataset Acquisition & Canonical ETL Engine | Wks 3 - 5 | M2: ETL | Ingested IBM AML, BankSim, SAP Würzburg; unified account namespace |
| **Task 3** | Streaming Zero-Lookahead Topology Engine | Wks 5 - 8 | M3: Engine | Implemented sliding-window cycle/density detectors; automated leakage test |
| **Task 4** | Hybrid Modeling Harness (XGBoost + TGN) | Wks 8 - 11 | M4: Model | Trained cost-sensitive XGBoost with focal loss; built continuous-time TGN |
| **Task 5** | Systematic Multi-Seed Ablation Benchmarking | Wks 11 - 13 | M5: Ablation | Multi-seed baseline vs +topology runs; proven +11.7% PR-AUC lift on BankSim |
| **Task 6** | Explainable Audit Alert Dispatch & Neo4j | Wks 13 - 15 | M6: Alert | Exact TreeSHAP integration; automated Cypher graph path visualizer |
| **Task 7** | Full Documentation & Project Report | Wks 14 - 16 | M7: Review | Comprehensive technical specification, UML diagrams, report generation |
| **Task 8** | Review & Final Project Submission | Wks 15 - 16 | Final Signoff | Oral presentation defense, verified code repository, documentation signoff |

---

# 3. TECHNICAL SPECIFICATION

### 3.1 Requirements

#### 3.1.1 Functional Requirements
- **FR1: Multi-Source ERP & Banking Ingestion:** The system shall ingest structured transaction ledgers from diverse enterprise formats, including SAP relational tables (BKPF/BSEG), IBM AML transfer streams, BankSim payment logs, and synthetic ERP records, parsing amounts, timestamps, and entity keys.
- **FR2: Entity Namespace Normalization & Bipartite Projection:** The system shall resolve disparate account, vendor, and customer identifiers into a single unified Account node namespace, constructing directed multigraph edges (`TRANSFERS_TO`) to enable structural traversal across multi-hop counterparty paths.
- **FR3: Streaming Zero-Lookahead Topology Extraction:** The system shall compute topological features (directed cycle length, cycle amount conservation, fan-in/fan-out ratios, connection density, and transfer velocity) strictly against the graph state as of transaction timestamp $T$, preventing future data contamination.
- **FR4: Continuous-Time TGN Self-Supervised Memory:** The system shall maintain a continuous-time Temporal Graph Network (TGN) with per-node GRU memory cells, trained via label-free self-supervised link prediction, producing dynamic 32-dimensional behavioral node embeddings without label leakage.
- **FR5: Cost-Sensitive Hybrid Classification & Calibrated Scoring:** The system shall train gradient boosted decision tree ensembles (XGBoost) using cost-sensitive `scale_pos_weight` or custom focal loss, calibrating optimal decision thresholds on validation splits to maximize rare-event PR-AUC and operational Precision@100.
- **FR6: Automated Anti-Leakage Testing Suite:** The system shall include an automated invariance testing harness that permutes future transactions ($t > T$) and asserts that past feature representations remain strictly invariant, failing the build if any backward information flow is detected.
- **FR7: Quantitative TreeSHAP Local Risk Attribution:** For every transaction flagged above the calibrated decision threshold, the system shall compute exact game-theoretic Shapley values via TreeSHAP, decomposing the risk score into ordinary tabular, pure structural topology, and TGN embedding contributions.
- **FR8: Visual Neo4j Subgraph Reconstruction & Interactive Replay:** The system shall automatically generate parameterized Cypher queries to extract the exact multi-hop path (cycles, fan-in hubs) from the graph store, rendering interactive visual audit alerts in the forensic dashboard with node-edge inspection.

#### 3.1.2 Non-Functional Requirements
- **Performance & Latency:** The feature extraction engine shall achieve sub-second processing latency (<50ms per transaction), and full end-to-end scoring (topology extraction + TGN embedding + XGBoost inference + SHAP attribution) shall execute within 200ms per transaction.
- **Scalability & Memory Efficiency:** The compute path shall support streaming datasets exceeding 6 million transactions (e.g., PaySim) without exhausting RAM by utilizing chunked sliding windows in Python, decoupling analytical compute from the Neo4j visualization store.
- **Reliability & Reproducibility:** Model training and feature generation shall be mathematically deterministic across random seeds. All trained model weights, scalers, frozen decision thresholds, and feature columns shall be persisted as self-describing versioned artifacts.
- **Security & Data Confidentiality:** The system shall enforce role-based access control (RBAC), ensuring that financial ledgers are protected via AES-256 encryption at rest and TLS 1.3 in transit, with immutable logging of all forensic auditor queries to satisfy statutory audit standards.
- **Usability & Human-Centered Design:** The auditor dashboard shall present intuitive, color-coded risk categorizations, waterfall SHAP attribution charts, and interactive D3/SVG network graphs, enabling non-technical internal auditors to interpret evidence without machine learning expertise.
- **Maintainability & Modularity:** The codebase shall follow a clean six-package modular architecture (`common`, `etl`, `graph`, `topology`, `features`, `modeling`) with strict typing, comprehensive unit tests, and standardized pip editable package installation.
- **Compliance & Regulatory Standards:** The system's audit trails and explanation outputs shall comply with Sarbanes-Oxley (SOX) Section 404 internal control verification, Basel III operational risk management mandates, and ISAE 3402 service organization reporting guidelines.

---

### 3.2 Feasibility Study

#### 3.2.1 Technical Feasibility
The project demonstrates high technical feasibility by building upon mature, industrially proven open-source technologies. Python 3.14 provides high-performance data processing libraries (Pandas, NumPy, NetworkX) capable of executing streaming sliding-window graph algorithms in memory. XGBoost offers state-of-the-art tree-boosting capabilities with native multi-threaded CPU execution and exact TreeSHAP explainability. PyTorch provides a flexible environment for training small, parameter-efficient TGN memory networks directly on CPU without requiring expensive GPU compute clusters.

Critically, technical feasibility was validated by resolving the architectural bottleneck of the predecessor system: by decoupling the compute engine (executed in Python) from the visualization layer (Neo4j), the system eliminates the Out-Of-Memory (OOM) crashes that plagued prior in-database Cypher graph algorithm implementations at scale. Automated unit and regression test suites achieve 100% pass rates on zero-lookahead invariance gates.

#### 3.2.2 Economic Feasibility
The economic feasibility of The Self-Auditing Ledger is compelling for enterprise organizations. Corporate fraud imposes devastating financial losses; according to the Association of Certified Fraud Examiners (ACFE), organizations lose an average of 5% of annual revenue to occupational fraud, with an average loss per enterprise case exceeding $1.7 million. External financial audits require hundreds of thousands of dollars in manual sampling fees yet inspect less than 5% of transactions.

The proposed system was developed entirely using open-source software (Python, Neo4j Community Edition, Scikit-Learn, PyTorch), requiring zero proprietary software licensing fees. It runs efficiently on standard enterprise commodity workstations or existing cloud virtual machines. By transitioning enterprises from periodic manual sampling to 100% continuous ledger screening, the system delivers an immediate Return on Investment (ROI) by catching collusive laundering before capital is irrevocably dispersed.

#### 3.2.3 Social Feasibility
The social feasibility of the system centers on auditor acceptance, ethical artificial intelligence, and corporate governance. A major impediment to AI adoption in corporate finance is the fear that automated algorithms will replace human auditors or generate arbitrary, unchallengeable decisions. The Self-Auditing Ledger is explicitly designed as a Human-in-the-Loop decision support tool: it never takes unilateral punitive action; instead, it delivers a transparent, evidentiary dossier (TreeSHAP drivers + Neo4j visual paths) that empowers human auditors to substantiate investigations.

Furthermore, the project adheres strictly to ethical AI principles: features are restricted to operational transaction mechanics (amounts, timestamps, network connectivity), explicitly omitting sensitive personal or demographic attributes to prevent algorithmic bias. The project directly advances the United Nations Sustainable Development Goals (SDGs): SDG 8 (Decent Work and Economic Growth) through financial integrity, SDG 9 (Industry, Innovation, and Infrastructure) through advanced enterprise AI, and SDG 16 (Peace, Justice, and Strong Institutions) by combating corruption and illicit financial flows.

---

### 3.3 System Specification

#### 3.3.1 Hardware Specification
- **Processor (CPU):** Intel Core i7-12700H / AMD Ryzen 7 5800H (8 Cores / 16 Threads, 3.2 GHz base, 4.7 GHz boost) or higher.
- **System Memory (RAM):** 16 GB DDR4/DDR5 (Minimum); 32 GB RAM recommended for multi-million transaction streaming graphs.
- **Storage:** 512 GB NVMe Solid State Drive (M.2 PCIe Gen 4, minimum 3,500 MB/s read speed for fast Parquet/CSV ingestion).
- **Graphics Processing Unit (GPU):** NVIDIA GeForce RTX 3060 (6 GB VRAM) / RTX 4070 (Optional; CPU execution fully supported for PyTorch/XGBoost).
- **Display:** Full HD (1920 x 1080) LED Backlit Display (Optimal for multi-window Neo4j graph visualization and dashboard analysis).

#### 3.3.2 Software Specification
- **Operating System:** Microsoft Windows 11 Pro (64-bit) / Ubuntu Linux 22.04 LTS.
- **Programming Language:** Python 3.14.0 (64-bit runtime) with native type annotations and asyncio support.
- **Development Environment:** Visual Studio Code / Antigravity IDE with Git version control.
- **Machine Learning Libraries:** XGBoost 2.1.0, Scikit-Learn 1.5.0, PyTorch 2.4.0 (CPU/CUDA), SHAP 0.45.0.
- **Graph Analysis Engines:** NetworkX 3.3, iGraph 0.11.5, Neo4j Python Driver 5.20.0.
- **Database Management System:** Neo4j Community Edition 5.18.0 (Graph Database, APOC library, Cypher query engine).
- **Data Processing & Serialization:** Pandas 2.2.2, NumPy 2.0.0, PyArrow 16.1.0, Joblib 1.4.2.
- **Visualization & Testing Tools:** Matplotlib 3.9.0, Seaborn 0.13.2, Plotly 5.22.0, D3.js, Pytest 8.2.0.

---

# 4. DESIGN APPROACH AND DETAILS

### 4.1 System Architecture
The Self-Auditing Ledger is designed as a decoupled, multi-stage pipeline where data flows strictly in chronological order. The architecture is organized into four discrete operational stages, illustrated in Figure 2.

![Fig. 2. System Architecture](artifacts/report_figures/fig2_system_architecture.png)

- **Stage 1: Ingestion and Canonical ETL (`src/etl/`):** The data layer continuously receives raw financial ledgers from enterprise ERP tables (SAP BKPF header and BSEG segment tables) and benchmark datasets. Disparate accounts, vendors, and customers are normalized into a unified Account node space with directed `TRANSFERS_TO` edges, eliminating the predecessor's identity-splitting flaw. Temporal fields are coerced into consistent chronological counters without fabricating artificial intra-tick sequence.
- **Stage 2: Streaming Zero-Lookahead Topology Engine (`src/topology/`):** As transactions arrive, the topology engine computes structural metrics against historical graph state strictly as of timestamp $T$ ($t \\le T$). It maintains sliding temporal windows (1h, 24h, 7d) and executes five specialized detectors: directed cycles (2-hop and 3-hop loops with amount conservation), fan-in collection hubs, transfer burst velocity, connection density, and temporal in-degree velocity. Only after features are extracted is the current transaction committed to the active graph, mathematically guaranteeing zero lookahead leakage.
- **Stage 3: Hybrid Modeling and Continuous-Time Representation (`src/modeling/`):** A composite feature matrix is assembled combining tabular transaction variables, handcrafted graph topology metrics, and continuous-time Temporal Graph Network (TGN) 32-dimensional node memory embeddings. The model workhorse is a cost-sensitive XGBoost classifier optimized via a custom alpha-free focal loss. Optimal decision thresholds are tuned exclusively on validation periods and frozen before evaluating test sets.
- **Stage 4: Dual-Layer Explainability and Audit Alert Dispatch (`src/graph/`, `demo/`):** When an incoming transaction exceeds the calibrated decision threshold, an audit alert is dispatched containing two evidentiary layers: (1) Quantitative TreeSHAP waterfall values decomposing the score into exact feature contributions; and (2) Visual Neo4j subgraph reconstructions rendering the concrete multi-hop flow of funds in an interactive forensic dashboard.

---

### 4.2 Design

#### 4.2.1 Data Flow Diagram (DFD)
The movement of data through The Self-Auditing Ledger is modeled using hierarchical Data Flow Diagrams. Figure 3 illustrates both the Level 0 Context Diagram and the decomposed Level 1 Functional Flow Diagram.

![Fig. 3. Data Flow Diagrams](artifacts/report_figures/fig3_data_flow_diagram.png)

In the Level 0 Context Diagram (Fig. 3a), the system boundary interacts with three external entities: the Enterprise ERP / Banking Feeds (which stream raw transaction journals), the Forensic Auditor / Compliance Team (who receive explainable audit alerts and provide investigation feedback), and System Administrators (who configure sliding windows and model thresholds). All ledger processing occurs within the 0.0 Self-Auditing Ledger Engine.

In the Level 1 DFD (Fig. 3b), the system is decomposed into five coordinated processes:
- **Process 1.0 (Canonical ETL & Normalization):** Ingests raw ERP records, strips formatting artifacts, unifies sender and receiver account namespaces, and stores standardized transaction edges into D1 (Canonical Transaction Store).
- **Process 2.0 (Streaming Zero-Lookahead Topology):** Pulls standardized transactions chronologically, queries the historical graph state ($t \\le T$), computes sliding-window structural metrics, and feeds the feature vector forward before committing the edge.
- **Process 3.0 (Hybrid Risk Scoring):** Merges ordinary tabular features, structural metrics, and self-supervised TGN memory vectors, scoring calibrated fraud risk probabilities via cost-sensitive XGBoost.
- **Process 4.0 (Explainability & Path Traversal):** When fraud probability exceeds the frozen threshold ($P \\ge \\tau$), this process computes exact TreeSHAP local attributions and executes Cypher graph traversals against D2 (Neo4j Graph Database) to extract the connected multi-hop transaction path.
- **Process 5.0 (Audit Dispatch & Visual Replay):** Packages quantitative SHAP drivers and interactive Neo4j visual subgraphs into an audit-grade alert dossier dispatched to the forensic compliance workstation.

#### 4.2.2 Use Case Diagram
The functional interactions between users and system modules are formally captured in Figure 4.

![Fig. 4. Use Case Diagram](artifacts/report_figures/fig4_use_case_diagram.png)

The Use Case specifications encompass seven core operations:
- **UC1: Ingest & Canonicalize ERP Feed** (Initiated by ERP Source / SysAdmin): Continuously validates schemas, strips delimiter noise, and resolves entity IDs into a canonical bipartite structure.
- **UC2: Extract Zero-Lookahead Topology** (System Automated): Dynamically computes sliding-window network metrics against past-only graph snapshots.
- **UC3: Real-Time Fraud Scoring & Calibrated Risk** (System Automated): Evaluates transactions through the hybrid TGN-XGBoost classifier to produce calibrated fraud probabilities.
- **UC4: Inspect High-Risk Audit Alerts** (Forensic Auditor): Surfaces high-risk transactions ranking in the top-k (Precision@100) queue for forensic inspection.
- **UC5: Analyze TreeSHAP Quantitative Drivers** (Forensic Auditor): Decomposes the transaction's fraud score into exact feature contribution waterfall plots.
- **UC6: Replay Multi-Hop Neo4j Money Paths** (Forensic Auditor): Interactively renders and traverses the exact cycle or fan-in subgraph in Neo4j.
- **UC7: Validate Invariance & Export SOX Trail** (Auditor / SysAdmin): Executes automated leakage verification tests and generates immutable forensic audit reports for regulatory compliance.

#### 4.2.3 Class Diagram
The static structural object model of the system is depicted in Figure 5, illustrating the core domain classes, their attributes, methods, and encapsulation boundaries.

![Fig. 5. Class Diagram](artifacts/report_figures/fig5_class_diagram.png)

Key domain classes within the system architecture include:
- `ERPTransaction`: Represents an atomic ledger posting with `txn_id`, `sender_id`, `receiver_id`, `amount`, `timestamp`, and `label`, providing schema validation methods.
- `TemporalShadowGraph`: Encapsulates the dynamic NetworkX/igraph multi-directed graph, managing sliding temporal windows and as-of historical snapshot queries.
- `TopologyEngine`: Houses the specialized structural fraud detectors (`detect_cycles`, `compute_density`, `compute_velocity`) and outputs the structured topology feature matrix.
- `HybridFraudClassifier`: Manages the XGBoost model, custom focal loss objective, TGN embedding interface, threshold calibration, and scoring routines.
- `DualLayerAlertDispatcher`: Integrates the TreeSHAP explainer with the Neo4j bolt driver to assemble composite audit alert dossiers.
- `AuditAlert`: The evidentiary entity containing calibrated risk probability, exact SHAP attribution dictionaries, verified subgraph paths, and auditor feedback status.

#### 4.2.4 Sequence Diagram
The dynamic runtime behavior and message sequencing of the system are modeled in Figure 6, tracing the complete lifecycle of an incoming ERP transaction from ingestion to visual audit dispatch.

![Fig. 6. Sequence Diagram](artifacts/report_figures/fig6_sequence_diagram.png)

The execution sequence proceeds through ten rigorous chronological steps:
1. The ERP Feed streams a raw transaction posting to the Canonical ETL Engine.
2. Canonical ETL normalizes entity namespaces and forwards the transaction edge to the Streaming Topology Engine at timestamp $T$.
3. The Topology Engine queries the graph state strictly as-of timestamp $T$ (asserting $t \\le T$) and calculates structural metrics (cycles, fan-in, density).
4. The Topology Engine returns the extracted structural vector and subsequently commits the current edge into the historical graph.
5. Canonical ETL merges ordinary tabular features, structural metrics, and TGN memory embeddings into the Hybrid Model.
6. The Hybrid Model executes inference and evaluates whether $P(\\text{fraud}) \\ge \\tau_{\\text{frozen}}$ (the threshold calibrated on validation data).
7. For transactions exceeding the threshold, the Hybrid Model triggers the Dual-Layer Explanation Dispatcher.
8. The Dispatcher computes exact TreeSHAP attributions and executes a parameterized Cypher query against the Neo4j store to extract the multi-hop subgraph path.
9. The Dispatcher packages the quantitative SHAP drivers and interactive Neo4j visual graph into an Audit Alert sent to the Forensic Auditor dashboard.
10. The Forensic Auditor reviews the evidentiary dossier, inspects the visual transaction path, and records forensic feedback.

---

# 5. REFERENCES

### Weblinks:
1. https://www.acfe.com/report-to-the-nations/2024/ (Association of Certified Fraud Examiners - 2024 Global Fraud Study).
2. https://neo4j.com/docs/graph-data-science/current/ (Neo4j Graph Data Science Library Documentation & Cypher Manual).
3. https://xgboost.readthedocs.io/en/stable/ (XGBoost Documentation: Scalable, Portable and Distributed Gradient Boosting).
4. https://shap.readthedocs.io/en/latest/ (SHAP: Unified Approach to Interpreting Model Predictions via Game Theory).

### Journals: <IEEE Format>
1. S. Motie and B. Raahemi, "Financial fraud detection using graph neural networks: A systematic review," *Expert Systems with Applications*, vol. 240, p. 122557, Apr. 2024.
2. N. Innan et al., "Financial fraud detection using quantum graph neural networks," *Quantum Machine Intelligence*, vol. 6, no. 1, pp. 1-14, Feb. 2024.
3. M. Grossi et al., "Mixed quantum-classical method for fraud detection with quantum feature selection," *IEEE Transactions on Quantum Engineering*, vol. 3, pp. 1-12, 2022.
4. R. R. Devi, J. E. Raja, and Y. B. Chin, "RL-GNN fusion for real-time financial fraud detection," *Scientific Reports*, vol. 15, no. 1, p. 1042, 2025.
5. Z. N. Jawad et al., "ML-driven optimization of ERP systems: A comprehensive review," *Discover Artificial Intelligence*, vol. 4, no. 1, pp. 1-28, 2024.
6. Z. Yuan et al., "A comprehensive survey on GNN-based anomaly detection," *ACM Computing Surveys*, vol. 57, no. 3, pp. 1-39, 2025.
7. L. Zhi et al., "Imbalanced fraudulent transaction detection based on embedding-aware conditional GAN," *Journal of Big Data*, vol. 12, no. 1, pp. 1-22, 2025.
8. G. Tong et al., "Financial transaction fraud detector based on imbalance learning and GNN," *Applied Intelligence*, vol. 53, no. 14, pp. 17820-17835, 2023.
9. M. Boyapati et al., "BalancerGNN: Balancer GNNs for imbalanced datasets," *IEEE Access*, vol. 13, pp. 14201-14215, 2025.
10. X. J. Mamakou et al., "Post-implementation evaluation of ERP systems: An internal auditors' perspective," *Information Systems Management*, vol. 41, no. 2, pp. 180-198, 2024.
11. M. A. Vasarhelyi, M. G. Alles, and K. T. Williams, "The acceptance and adoption of continuous auditing by internal auditors," *International Journal of Accounting Information Systems*, vol. 13, no. 3, pp. 267-281, 2012.
12. S. M. Lundberg et al., "From local explanations to global understanding with explainable AI for trees," *Nature Machine Intelligence*, vol. 2, no. 1, pp. 56-67, 2020.

### Conferences: <IEEE Format>
1. Y. Shi et al., "Uncertainty-aware spatio-temporal contrastive GNNs for financial fraud detection," in *Proceedings of the AAAI Conference on Artificial Intelligence (AAAI-26)*, vol. 40, 2026, pp. 1420-1428.
2. H. Wang, N. Liu, and Q. Tan, "Reinforced Causal Explainer for Graph Neural Networks," in *Proceedings of the ACM Web Conference 2023 (WWW '23)*, Austin, TX, USA, 2023, pp. 432-442.
3. E. Rossi et al., "Temporal Graph Networks for Deep Learning on Dynamic Graphs," in *ICML Workshop on Graph Representation Learning and Beyond*, 2020, pp. 1-12.
4. A. Salih, S. T. Zeebaree, S. Ameen, A. Alkhyyat, and H. M. Shukur, "A survey on the role of artificial intelligence, machine learning and deep learning for cybersecurity attack detection," in *2021 7th International Engineering Conference (IEC)*, IEEE, 2021, pp. 61-66.

### Books: <IEEE Format>
1. I. Goodfellow, Y. Bengio, and A. Courville, *Deep Learning*, MIT Press, Cambridge, MA, 2016.
2. W. Hamilton, *Graph Representation Learning*, Morgan & Claypool Publishers, San Rafael, CA, 2020.
3. C. M. Bishop, *Pattern Recognition and Machine Learning*, Springer-Verlag, New York, NY, 2006.
""")

    print(f"Successfully generated complete Markdown document: {md_path}")

if __name__ == '__main__':
    generate_all()
