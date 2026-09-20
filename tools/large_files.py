"""Split / restore files that exceed GitHub's 100 MB per-file push limit.

GitHub rejects any single file over 100 MB, and Git LFS's free quota (1 GB) is smaller
than this project's oversize data files, so every file above the threshold is stored in
the repository as a directory of ordered <=90 MiB chunks under ``large_file_parts/``,
together with a manifest holding each original's size and SHA-256.

    python -m tools.large_files split      # (maintainer) chunk oversize files, write manifest
    python -m tools.large_files restore    # rebuild every original file from its chunks
    python -m tools.large_files verify     # check existing originals against the manifest

The originals are left untouched by ``split``; ``restore`` never overwrites a file whose
SHA-256 already matches the manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PARTS_DIR = REPO_ROOT / "large_file_parts"
MANIFEST = PARTS_DIR / "MANIFEST.json"
DEFAULT_THRESHOLD_MB = 95
CHUNK_BYTES = 90 * 1024 * 1024
READ_BLOCK = 8 * 1024 * 1024


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(READ_BLOCK):
            h.update(block)
    return h.hexdigest()


def find_oversize(threshold_bytes: int) -> list[Path]:
    found: list[Path] = []
    for p in REPO_ROOT.rglob("*"):
        if ".git" in p.relative_to(REPO_ROOT).parts[:1] or PARTS_DIR in p.parents:
            continue
        if p.is_file() and not p.is_symlink() and p.stat().st_size > threshold_bytes:
            found.append(p)
    return sorted(found)


def split_file(src: Path) -> dict:
    rel = src.relative_to(REPO_ROOT).as_posix()
    out_dir = PARTS_DIR / rel
    out_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    parts: list[str] = []
    with src.open("rb") as f:
        idx = 0
        while chunk := f.read(CHUNK_BYTES):
            digest.update(chunk)
            name = f"part-{idx:04d}"
            (out_dir / name).write_bytes(chunk)
            parts.append(name)
            idx += 1
    return {"path": rel, "size": src.stat().st_size, "sha256": digest.hexdigest(), "parts": parts}


def cmd_split(threshold_mb: int) -> int:
    files = find_oversize(threshold_mb * 1024 * 1024)
    entries = []
    for src in files:
        print(f"splitting {src.relative_to(REPO_ROOT).as_posix()} ({src.stat().st_size / 1e6:.0f} MB)")
        entries.append(split_file(src))
    PARTS_DIR.mkdir(exist_ok=True)
    MANIFEST.write_text(json.dumps({"chunk_bytes": CHUNK_BYTES, "files": entries}, indent=2), encoding="utf-8")
    print(f"{len(entries)} files split; manifest -> {MANIFEST.relative_to(REPO_ROOT).as_posix()}")
    return 0


def load_manifest() -> dict:
    if not MANIFEST.exists():
        sys.exit(f"no manifest at {MANIFEST}")
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def cmd_restore() -> int:
    bad = 0
    for entry in load_manifest()["files"]:
        dest = REPO_ROOT / entry["path"]
        if dest.exists() and dest.stat().st_size == entry["size"] and sha256_of(dest) == entry["sha256"]:
            print(f"ok (already present): {entry['path']}")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        with dest.open("wb") as out:
            for name in entry["parts"]:
                data = (PARTS_DIR / entry["path"] / name).read_bytes()
                digest.update(data)
                out.write(data)
        if digest.hexdigest() != entry["sha256"]:
            print(f"CHECKSUM MISMATCH: {entry['path']}", file=sys.stderr)
            bad += 1
        else:
            print(f"restored: {entry['path']}")
    return 1 if bad else 0


def cmd_verify() -> int:
    bad = 0
    for entry in load_manifest()["files"]:
        dest = REPO_ROOT / entry["path"]
        state = "MISSING"
        if dest.exists():
            state = "ok" if sha256_of(dest) == entry["sha256"] else "MISMATCH"
        if state != "ok":
            bad += 1
        print(f"{state:8s} {entry['path']}")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["split", "restore", "verify"])
    ap.add_argument("--threshold-mb", type=int, default=DEFAULT_THRESHOLD_MB)
    args = ap.parse_args()
    if args.command == "split":
        return cmd_split(args.threshold_mb)
    if args.command == "restore":
        return cmd_restore()
    return cmd_verify()


if __name__ == "__main__":
    raise SystemExit(main())
