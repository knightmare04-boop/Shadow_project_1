# Large files

GitHub rejects any single file over 100 MB. Files above that size (raw and processed
datasets, and any oversize binaries inside `.venv/`) are therefore stored as ordered
90 MiB chunks under `large_file_parts/<original path>/part-NNNN`, with `large_file_parts/MANIFEST.json`
recording each original's size and SHA-256. The original oversize files themselves are
not committed.

Rebuild them (and verify checksums) after cloning:

```bash
python -m tools.large_files restore
python -m tools.large_files verify
```

`python -m tools.large_files split` regenerates the chunks and manifest from the originals.
