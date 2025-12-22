#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import List

ALLOWED_SOURCE_ARCHIVES = {
    "sources/JMdict.gz",
    "sources/JMdict_e_examp.gz",
    "sources/JMnedict.xml.gz",
    "sources/kanjidic2.xml.gz",
    "sources/kradzip.zip",
}

DISALLOWED_EXTENSIONS = {
    ".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z"
}

# Note: we DO allow .gz globally because the dataset uses .json.gz/.jsonl.gz.
# We therefore only disallow archives other than dataset compression, via a path-based filter.


def is_dataset_gz(path: str) -> bool:
    return path.endswith(".json.gz") or path.endswith(".jsonl.gz")


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate repository hygiene (no caches, no accidental archives, etc.).")
    ap.add_argument("--repo-root", default=".", help="Repository root (default: .)")
    ap.add_argument("--max-problems", type=int, default=200, help="Max problems to report")
    args = ap.parse_args()

    repo = Path(args.repo_root).resolve()

    problems: List[dict] = []

    # 1) __pycache__
    for r, dirs, files in os.walk(repo):
        rp = Path(r)
        if "__pycache__" in dirs:
            problems.append({"code": "pycache", "path": str((rp/"__pycache__").relative_to(repo)), "message": "__pycache__ directory must not be committed"})
        for fn in files:
            if fn.endswith(".pyc") or fn.endswith(".pyo"):
                problems.append({"code": "pyc", "path": str((rp/fn).relative_to(repo)), "message": "Python bytecode must not be committed"})

    # 2) Disallowed archives (except sources + dataset .json.gz/.jsonl.gz)
    for r, _, files in os.walk(repo):
        rp = Path(r)
        for fn in files:
            p = rp / fn
            rel = str(p.relative_to(repo)).replace(os.sep, "/")
            suffix = p.suffix.lower()
            if suffix in DISALLOWED_EXTENSIONS:
                if rel in ALLOWED_SOURCE_ARCHIVES:
                    continue
                if is_dataset_gz(rel):
                    continue
                # Allow sources/*.gz and sources/*.zip only if in allowlist above
                problems.append({"code": "archive", "path": rel, "message": "Archive file should not be committed (except allowlisted upstream sources and dataset compression)"})

    ok = len(problems) == 0
    out = {"ok": ok, "problem_count": len(problems), "problems": problems[: args.max_problems]}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
