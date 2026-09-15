import re
from pathlib import Path

labels = set()
refs = []
for p in sorted(Path("sections").glob("*.tex")):
    text = p.read_text(encoding="utf-8")
    labels.update(re.findall(r"\\label\{([^}]+)\}", text))
    for m in re.finditer(r"\\(?:ref|eqref)\{([^}]+)\}", text):
        refs.append((p.name, m.group(1)))

missing = [(f, r) for f, r in refs if r not in labels]
print(f"{len(labels)} labels defined, {len(refs)} refs used")
if missing:
    print("MISSING:")
    for f, r in missing:
        print(f"  {f}: {r}")
else:
    print("all refs resolve")
