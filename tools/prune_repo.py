\
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import List, Tuple

def find_dupes(root: Path) -> List[Tuple[Path, Path]]:
    out: List[Tuple[Path, Path]] = []
    for r, _, files in os.walk(root):
        rp = Path(r)
        s = set(files)
        for fn in files:
            if fn.endswith(".json") and (fn + ".gz") in s:
                out.append((rp/fn, rp/(fn+".gz")))
    return out

def find_pycache(root: Path) -> List[Path]:
    out=[]
    for r, dirs, _ in os.walk(root):
        for d in dirs:
            if d == "__pycache__":
                out.append(Path(r)/d)
    return out

def main() -> int:
    ap = argparse.ArgumentParser(description="Prune repo noise: __pycache__ and redundant .json when .json.gz exists.")
    ap.add_argument("--repo-root", default=".", help="Repository root (default: .)")
    ap.add_argument("--write", action="store_true", help="Apply deletions (default: dry-run).")
    ap.add_argument("--remove-json-when-gz-exists", action="store_true", help="Remove .json when matching .json.gz exists.")
    args = ap.parse_args()

    repo = Path(args.repo_root).resolve()
    actions = {"pycache_dirs": [], "json_removed": [], "dry_run": not args.write}

    for p in find_pycache(repo):
        actions["pycache_dirs"].append(str(p.relative_to(repo)))
        if args.write:
            import shutil
            shutil.rmtree(p, ignore_errors=True)

    if args.remove_json_when_gz_exists:
        for j, _ in find_dupes(repo):
            actions["json_removed"].append(str(j.relative_to(repo)))
            if args.write:
                try:
                    j.unlink()
                except Exception:
                    pass

    import json
    print(json.dumps(actions, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
