#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
import os
from pathlib import Path

FORBIDDEN_KEYS = {
    "generated_at_utc", "generated_at", "created_at", "build_stamp",
    "built_at", "timestamp", "time_utc", "supersedes", "superseded_by",
}

def load_json_maybe_gz(path: Path):
    if path.suffixes[-2:] == [".json", ".gz"]:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def walk_json_files(root: Path):
    for r, _, files in os.walk(root):
        rp = Path(r)
        for fn in files:
            if fn.endswith(".json") or fn.endswith(".json.gz"):
                yield rp / fn

def contains_forbidden_keys(obj) -> bool:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in FORBIDDEN_KEYS or "generated_at" in k:
                return True
            if contains_forbidden_keys(v):
                return True
    elif isinstance(obj, list):
        for x in obj:
            if contains_forbidden_keys(x):
                return True
    return False

def main() -> int:
    p = argparse.ArgumentParser(description="Verify repo dataset layout and forbidden metadata keys.")
    p.add_argument("--root", default=".", help="Repository root (default: .)")
    args = p.parse_args()

    root = Path(args.root).resolve()

    data_dir = root / "data"
    if not data_dir.exists():
        raise SystemExit(f"Missing data/ under repo root: {root}")

    problems = []

    # Basic required manifests
    required = [
        data_dir / "manifest.json",
    ]
    for req in required:
        if not req.exists():
            problems.append(f"Missing required file: {req}")

    # Forbidden keys scan (best-effort; may be heavy on full dataset)
    checked = 0
    forbidden_hits = 0
    for fp in walk_json_files(data_dir):
        checked += 1
        try:
            obj = load_json_maybe_gz(fp)
        except Exception as e:
            problems.append(f"JSON parse failed: {fp} ({e})")
            continue
        if contains_forbidden_keys(obj):
            forbidden_hits += 1
            problems.append(f"Forbidden metadata key found in: {fp}")
            if forbidden_hits >= 50:
                problems.append("Too many forbidden-key hits; stopping scan early.")
                break

    out = {
        "ok": len(problems) == 0,
        "checked_json_files": checked,
        "problem_count": len(problems),
        "problems": problems[:200],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not problems else 1

if __name__ == "__main__":
    raise SystemExit(main())
