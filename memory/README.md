# Memory

This directory is the optional Obsidian-compatible memory vault for local runs.

Generated memory artifacts are ignored by default. After a run, extract memory
with:

```bash
python3 tools/extract_memory.py runs/<run-name> --memory-dir memory --append
python3 tools/build_global_map.py --runs-root runs --memory-dir memory
```
