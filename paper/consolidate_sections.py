"""Consolidates the paper-drafting workflow's output into the canonical
paper/sections/NN_name.tex files main.tex's \\input list expects.

Some drafting agents wrote their section directly to disk (under an
inconsistent filename); others returned the full LaTeX as their final
message instead. This reads the workflow's journal.jsonl, and for each
section prefers a complete on-disk file if one exists, else falls back to
the captured result text.

Run:  python paper/consolidate_sections.py
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SECTIONS_DIR = REPO_ROOT / "paper" / "sections"
JOURNAL = Path(r"C:\Users\akifm\.claude\projects\D--project-1-project\43dc5aac-6181-49cf-9b50-6fbd1511b341\subagents\workflows\wf_3e0d6f76-b78\journal.jsonl")

# label -> (canonical filename, known on-disk filenames to check first, in preference order)
CANONICAL = {
    "draft:intro_related": ("01_intro_related.tex", ["introduction_related_work.tex", "01_intro_related.tex"]),
    "draft:problem_datasets": ("02_problem_datasets.tex", ["02_problem_datasets.tex"]),
    "draft:topology_engine": ("03_topology_engine.tex", ["03_topology_engine.tex", "topology_engine.tex"]),
    "draft:protocol_ablation": ("04_protocol_ablation.tex", ["04_protocol_ablation.tex", "protocol_ablation.tex"]),
    "draft:modern_study": ("05_modern_study.tex", ["modern.tex", "05_modern_study.tex"]),
    "draft:synthetic_economy": ("06_synthetic_economy.tex", ["06_synthetic_economy.tex", "synthetic_economy.tex"]),
    "draft:explainability": ("07_explainability.tex", ["07_explainability.tex"]),
    "draft:system": ("08_system.tex", ["08_system.tex", "system.tex"]),
    "draft:limitations_conclusion": ("09_limitations_conclusion.tex", ["09_limitations_conclusion.tex", "limitations_conclusion.tex"]),
}

# A heuristic for "this looks like real LaTeX content, not an agent's prose summary"
def _looks_like_section(text: str) -> bool:
    return text.strip().startswith("\\section") and len(text) > 3000


def main() -> None:
    key_to_label: dict[str, str] = {}
    results: dict[str, str] = {}
    with open(JOURNAL, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if obj.get("type") == "started":
                key_to_label[obj["key"]] = obj["label"]
            elif obj.get("type") == "result":
                results[obj["key"]] = obj["result"]

    label_to_result = {key_to_label.get(k, k): v for k, v in results.items()}

    SECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    report = []
    for label, (canonical_name, disk_candidates) in CANONICAL.items():
        canonical_path = SECTIONS_DIR / canonical_name

        # 1) prefer an existing on-disk file (from a candidate list) that looks complete
        found_on_disk = None
        for candidate in disk_candidates:
            p = SECTIONS_DIR / candidate
            if p.exists():
                text = p.read_text(encoding="utf-8")
                if _looks_like_section(text):
                    found_on_disk = p
                    break

        if found_on_disk is not None:
            if found_on_disk != canonical_path:
                shutil.move(str(found_on_disk), str(canonical_path))
            report.append((label, canonical_name, "disk", canonical_path.stat().st_size))
            continue

        # 2) fall back to the captured agent result text
        result_text = label_to_result.get(label)
        if result_text and _looks_like_section(result_text):
            canonical_path.write_text(result_text, encoding="utf-8")
            report.append((label, canonical_name, "journal-result", len(result_text)))
            continue

        report.append((label, canonical_name, "MISSING", 0))

    # clean up any leftover non-canonical files
    keep = {name for name, _ in CANONICAL.values()}
    for p in SECTIONS_DIR.glob("*.tex"):
        if p.name not in keep:
            print(f"note: leftover non-canonical file not removed automatically: {p.name}")

    print(f"{'label':32s} {'file':32s} {'source':16s} {'bytes'}")
    for label, name, source, size in report:
        print(f"{label:32s} {name:32s} {source:16s} {size}")


if __name__ == "__main__":
    main()
