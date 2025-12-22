#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Tuple


def run(cmd: List[str], cwd: Path) -> Tuple[int, str]:
    p = subprocess.run(cmd, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return p.returncode, p.stdout.strip()


def largest_files(root: Path, top_n: int = 15) -> List[Dict[str, Any]]:
    items: List[Tuple[int, str]] = []
    for r, _, files in os.walk(root):
        rp = Path(r)
        for fn in files:
            fp = rp / fn
            try:
                sz = fp.stat().st_size
            except Exception:
                continue
            items.append((sz, str(fp.relative_to(root))))
    items.sort(reverse=True)
    return [{"path": rel, "bytes": sz} for sz, rel in items[:top_n]]


def main() -> int:
    ap = argparse.ArgumentParser(description="Preflight checks before releasing the dataset.")
    ap.add_argument("--repo-root", default=".", help="Repository root (default: .)")
    ap.add_argument("--mode", choices=["fast", "full"], default="fast", help="Validation mode")
    ap.add_argument("--skip-size-scan", action="store_true", help="Skip scanning for largest files (useful in CI).")
    ap.add_argument("--size-warn-mib", type=int, default=90, help="Warn if any file exceeds this size (MiB).")
    args = ap.parse_args()

    repo = Path(args.repo_root).resolve()
    results: Dict[str, Any] = {"ok": True, "mode": args.mode, "checks": {}}

    rc, out = run(["python", "tools/validate_db.py", "--repo-root", ".", "--mode", args.mode], cwd=repo)
    results["checks"]["validate_db"] = {"rc": rc, "output": out}
    if rc != 0:
        results["ok"] = False

    rc, out = run(["python", "tools/validate_schemas.py", "--repo-root", ".", "--mode", args.mode], cwd=repo)
    results["checks"]["validate_schemas"] = {"rc": rc, "output": out}
    if rc != 0:
        results["ok"] = False

    # Cross-file relations (sampling in fast, more exhaustive in full)
    rel_script = repo / "tools" / "validate_relations.py"
    if rel_script.exists():
        rc, out = run(["python", "tools/validate_relations.py", "--repo-root", ".", "--mode", args.mode], cwd=repo)
        results["checks"]["validate_relations"] = {"rc": rc, "output": out}
        if rc != 0:
            results["ok"] = False
    else:
        results["checks"]["validate_relations"] = {"skipped": True, "reason": "tools/validate_relations.py not found"}

    if not args.skip_size_scan:
        warn_bytes = int(args.size_warn_mib * 1024 * 1024)
        largest = largest_files(repo, top_n=15)
        warnings = [x for x in largest if x["bytes"] >= warn_bytes]
        results["checks"]["file_sizes"] = {"largest": largest, "warnings": warnings, "warn_threshold_mib": args.size_warn_mib}

    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0 if results["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
