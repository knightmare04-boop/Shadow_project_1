import re
from pathlib import Path

referenced = set()
for p in sorted(Path("paper/sections").glob("*.tex")):
    text = p.read_text(encoding="utf-8")
    for m in re.finditer(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", text):
        referenced.add(Path(m.group(1)).name)

existing = {p.name for p in Path("paper/figures").glob("*")}

print(f"referenced: {sorted(referenced)}")
print(f"existing:   {sorted(existing)}")
missing = referenced - existing
print(f"\nMISSING ({len(missing)}): {sorted(missing)}")
