"""Adversarial check: extract every plausible numeric literal from the
drafted .tex section files and flag any that don't appear (within a small
rounding tolerance) anywhere in paper/data/*.json. Catches transcription
drift from the parallel drafting agents before compilation — cheap
insurance given the whole point of the harvest step was "every number
generated, never retyped."

This is a SIGNAL, not a hard gate: some numbers in prose are legitimately
derived (percentages computed from two harvested numbers, row/column
counts, page/table references) rather than copied verbatim. Read the
flagged list and manually confirm each one traces to source, rather than
trusting a 0-flags result blindly OR panicking at every flag.

Run:  python paper/verify_numbers.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "paper" / "data"
SECTIONS_DIR = REPO_ROOT / "paper" / "sections"

_NUM_RE = re.compile(r"-?\d+\.\d{2,}")  # floats with >=2 decimal digits — the risky ones


def _flatten_numbers(obj, acc: set[float]) -> None:
    if isinstance(obj, dict):
        for v in obj.values():
            _flatten_numbers(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _flatten_numbers(v, acc)
    elif isinstance(obj, (int, float)):
        acc.add(round(float(obj), 6))
    elif isinstance(obj, str):
        try:
            acc.add(round(float(obj), 6))
        except ValueError:
            pass


def load_all_source_numbers() -> set[float]:
    acc: set[float] = set()
    for f in DATA_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        _flatten_numbers(data, acc)
    return acc


def check_section(path: Path, source_numbers: set[float], tol: float = 0.006) -> list[tuple[str, float]]:
    text = path.read_text(encoding="utf-8")
    flagged = []
    for m in _NUM_RE.finditer(text):
        val = float(m.group())
        if any(abs(val - s) < tol for s in source_numbers):
            continue
        # also allow simple percentage transforms (x*100) and (x - y) deltas
        # by checking against a coarser net (this is intentionally permissive
        # — see module docstring, this is a signal not a gate)
        if any(abs(val - s * 100) < tol * 100 for s in source_numbers):
            continue
        flagged.append((m.group(), val))
    return flagged


def main() -> None:
    source_numbers = load_all_source_numbers()
    print(f"loaded {len(source_numbers)} distinct source numbers from paper/data/*.json\n")

    any_flagged = False
    for section_path in sorted(SECTIONS_DIR.glob("*.tex")):
        flagged = check_section(section_path, source_numbers)
        if flagged:
            any_flagged = True
            print(f"--- {section_path.name}: {len(flagged)} unrecognized numeric literal(s) ---")
            for raw, val in flagged[:30]:
                print(f"    {raw}")
        else:
            print(f"{section_path.name}: all numeric literals trace to source (or are permissive-matched)")

    if any_flagged:
        print("\nReview each flagged number by hand — it may be a legitimate derived "
              "value (a percentage, a row count, a page reference) or a real drift. "
              "This script does not fail the build; it is a checklist.")


if __name__ == "__main__":
    main()
