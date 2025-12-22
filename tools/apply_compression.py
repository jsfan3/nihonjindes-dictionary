#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import gzip
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

# These are metadata keys we never want in committed dataset JSON.
FORBIDDEN_KEYS = {
    "generated_at_utc", "generated_at", "created_at", "build_stamp", "built_at",
    "timestamp", "time_utc", "supersedes", "superseded_by",
}

def load_plan(plan_path: Path) -> dict[str, Any]:
    with plan_path.open("r", encoding="utf-8") as f:
        return json.load(f)

def iter_files(root: Path) -> Iterable[Path]:
    for r, _, files in os.walk(root):
        rp = Path(r)
        for fn in files:
            yield rp / fn

def matches_any(rel: str, patterns: List[str]) -> bool:
    return any(fnmatch.fnmatch(rel, p) for p in patterns)

def sanitize(obj: Any) -> Any:
    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for k, v in obj.items():
            if k in FORBIDDEN_KEYS or "generated_at" in k:
                continue
            out[k] = sanitize(v)
        # normalize schema.version
        sch = out.get("schema")
        if isinstance(sch, dict) and "version" in sch:
            sch["version"] = "1.0"
        return out
    if isinstance(obj, list):
        return [sanitize(x) for x in obj]
    return obj

def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def write_json_gz(path_gz: Path, obj: Any, pretty: bool) -> None:
    path_gz.parent.mkdir(parents=True, exist_ok=True)
    # Write to a temp file first for safety
    tmp = path_gz.with_suffix(path_gz.suffix + ".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        if pretty:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        else:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    tmp.replace(path_gz)

def main() -> int:
    p = argparse.ArgumentParser(description="Apply compression plan: convert selected .json files into .json.gz.")
    p.add_argument("--repo-root", default=".", help="Repository root (default: .)")
    p.add_argument("--data-dir", default="data", help="Dataset directory relative to repo-root (default: data)")
    p.add_argument("--plan", default="tools/compression_plan.json", help="Compression plan JSON (default: tools/compression_plan.json)")
    p.add_argument("--write", action="store_true", help="Apply changes (without this, only reports what would change).")
    p.add_argument("--sanitize", action="store_true", help="Remove forbidden metadata keys and normalize schema.version to 1.0.")
    p.add_argument("--pretty", action="store_true", help="Write pretty JSON inside .gz (default: minified).")
    p.add_argument("--keep-original", action="store_true", help="Keep the original .json files after creating .json.gz.")
    args = p.parse_args()

    repo_root = Path(args.repo_root).resolve()
    data_root = (repo_root / args.data_dir).resolve()
    plan_path = (repo_root / args.plan).resolve()

    if not data_root.exists():
        raise SystemExit(f"Data directory not found: {data_root}")
    if not plan_path.exists():
        raise SystemExit(f"Compression plan not found: {plan_path}")

    plan = load_plan(plan_path)
    policy = plan.get("policy", {})
    keep_plain = policy.get("keep_plain_json", [])
    compress = policy.get("compress_to_json_gz", [])
    exclusions = policy.get("exclusions", [])

    candidates: List[Tuple[Path, Path]] = []
    for fp in iter_files(data_root):
        if not fp.name.endswith(".json"):
            continue
        rel = str(fp.relative_to(repo_root)).replace(os.sep, "/")
        if matches_any(rel, exclusions) or matches_any(rel, keep_plain):
            continue
        if matches_any(rel, compress):
            gz = fp.with_name(fp.name + ".gz")
            candidates.append((fp, gz))

    report = {
        "plan": str(plan_path.relative_to(repo_root)),
        "data_dir": str(data_root.relative_to(repo_root)),
        "candidates": len(candidates),
        "write_mode": bool(args.write),
        "sanitize": bool(args.sanitize),
        "pretty_gz": bool(args.pretty),
        "keep_original": bool(args.keep_original),
        "examples": [str(a.relative_to(repo_root)) for a, _ in candidates[:10]],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if not args.write:
        return 0

    converted = 0
    for src, dst in candidates:
        try:
            obj = read_json(src)
            if args.sanitize:
                obj = sanitize(obj)
            write_json_gz(dst, obj, pretty=args.pretty)
            converted += 1
            if not args.keep_original:
                src.unlink()
        except Exception as e:
            print(f"ERROR converting {src}: {e}")
            return 1

    print(json.dumps({"converted": converted}, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
