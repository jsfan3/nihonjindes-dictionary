#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import List

def load_plan(plan_path: Path) -> dict:
    with plan_path.open("r", encoding="utf-8") as f:
        return json.load(f)

def match_any(path: str, patterns: List[str]) -> bool:
    import fnmatch
    for pat in patterns:
        if fnmatch.fnmatch(path, pat):
            return True
    return False

def main() -> int:
    p = argparse.ArgumentParser(description="Remove uncompressed .json files that have a corresponding .json.gz file (according to compression_plan.json).")
    p.add_argument("--repo-root", default=".", help="Repository root (default: .)")
    p.add_argument("--plan", default="tools/compression_plan.json", help="Compression plan JSON (default: tools/compression_plan.json)")
    p.add_argument("--write", action="store_true", help="Actually delete files (default: dry-run)")
    args = p.parse_args()

    repo = Path(args.repo_root).resolve()
    plan_path = (repo / args.plan).resolve()
    if not plan_path.exists():
        raise SystemExit(f"Plan not found: {plan_path}")
    plan = load_plan(plan_path)
    compress_patterns = plan.get("policy", {}).get("compress_to_json_gz", [])
    exclusions = plan.get("policy", {}).get("exclusions", [])

    deleted = []
    skipped = []

    for r, _, files in os.walk(repo / "data"):
        rp = Path(r)
        for fn in files:
            if not fn.endswith(".json"):
                continue
            fp = rp / fn
            rel = str(fp.relative_to(repo)).replace(os.sep, "/")
            if match_any(rel, exclusions):
                skipped.append(rel)
                continue
            if not match_any(rel, compress_patterns):
                skipped.append(rel)
                continue
            gz = fp.with_name(fn + ".gz")
            if gz.exists():
                if args.write:
                    fp.unlink()
                deleted.append(rel)

    out = {"write": bool(args.write), "deleted": deleted, "deleted_count": len(deleted), "skipped_count": len(skipped)}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
