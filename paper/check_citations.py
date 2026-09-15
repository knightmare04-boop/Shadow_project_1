import re
from pathlib import Path

bib_text = Path("paper/references.bib").read_text(encoding="utf-8")
bib_keys = set(re.findall(r"@\w+\{([\w-]+),", bib_text))
print(f"{len(bib_keys)} keys in references.bib")

used = set()
for p in sorted(Path("paper/sections").glob("*.tex")):
    text = p.read_text(encoding="utf-8")
    for m in re.finditer(r"\\cite\{([^}]+)\}", text):
        for key in m.group(1).split(","):
            used.add(key.strip())

missing = used - bib_keys
unused = bib_keys - used
print(f"\n{len(used)} distinct citation keys used across sections")
if missing:
    print(f"\nMISSING from references.bib ({len(missing)}):")
    for k in sorted(missing):
        print(f"  {k}")
else:
    print("\nAll cited keys exist in references.bib — OK")
print(f"\n{len(unused)} bib entries never cited: {sorted(unused)}")
