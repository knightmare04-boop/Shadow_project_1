import re
from collections import Counter
from pathlib import Path

for p in sorted(Path("paper/sections").glob("*.tex")):
    text = p.read_text(encoding="utf-8")
    braces = text.count("{") - text.count("}")
    begins = re.findall(r"\\begin\{(\w+)\}", text)
    ends = re.findall(r"\\end\{(\w+)\}", text)
    bc, ec = Counter(begins), Counter(ends)
    mismatch = {k: (bc[k], ec.get(k, 0)) for k in bc if bc[k] != ec.get(k, 0)}
    status = "OK" if braces == 0 and not mismatch else "CHECK"
    print(f"{p.name:35s} braces_diff={braces:4d}  env_mismatch={mismatch}  [{status}]")
