#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

FORBIDDEN_KEYS = {
    "generated_at_utc", "generated_at", "created_at", "build_stamp", "built_at",
    "timestamp", "time_utc", "supersedes", "superseded_by",
}

def iter_json_paths(data_root: Path) -> Iterable[Path]:
    for r, _, files in os.walk(data_root):
        rp = Path(r)
        for fn in files:
            if fn.endswith(".json") or fn.endswith(".json.gz"):
                yield rp / fn

def load_json(path: Path) -> Any:
    if path.name.endswith(".json.gz"):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def dump_json(path: Path, obj: Any, pretty: bool) -> None:
    # Preserve compression state
    if path.name.endswith(".json.gz"):
        with gzip.open(path, "wt", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2 if pretty else None, separators=None if pretty else (",", ":"))
            f.write("\n")
        return
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2 if pretty else None, separators=None if pretty else (",", ":"))
        f.write("\n")

def sanitize(obj: Any) -> Tuple[Any, int]:
    removed = 0
    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for k, v in obj.items():
            if k in FORBIDDEN_KEYS or "generated_at" in k:
                removed += 1
                continue
            vv, rr = sanitize(v)
            removed += rr
            out[k] = vv
        # Normalize schema.version to "1.0" if present
        sch = out.get("schema")
        if isinstance(sch, dict):
            if "version" in sch and sch["version"] != "1.0":
                sch["version"] = "1.0"
        return out, removed
    if isinstance(obj, list):
        out_list = []
        for x in obj:
            xx, rr = sanitize(x)
            removed += rr
            out_list.append(xx)
        return out_list, removed
    return obj, 0

def main() -> int:
    p = argparse.ArgumentParser(description="Sanitize dataset JSON files (remove forbidden metadata keys, normalize schema.version).")
    p.add_argument("--repo-root", default=".", help="Repository root (default: .)")
    p.add_argument("--data-dir", default="data", help="Data directory relative to repo-root (default: data)")
    p.add_argument("--write", action="store_true", help="Apply changes in-place. Without this flag, only reports changes.")
    p.add_argument("--pretty", action="store_true", help="Write pretty JSON when applying changes (default: minified).")
    p.add_argument("--max-files", type=int, default=0, help="If >0, limit number of files processed (for quick runs).")
    args = p.parse_args()

    repo_root = Path(args.repo_root).resolve()
    data_root = (repo_root / args.data_dir).resolve()
    if not data_root.exists():
        raise SystemExit(f"Data directory not found: {data_root}")

    changed_files = 0
    removed_total = 0
    parse_errors = 0
    processed = 0

    for fp in iter_json_paths(data_root):
        processed += 1
        if args.max_files and processed > args.max_files:
            break
        try:
            obj = load_json(fp)
        except Exception:
            parse_errors += 1
            continue
        new_obj, removed = sanitize(obj)
        if removed > 0 or (isinstance(new_obj, dict) and isinstance(new_obj.get("schema"), dict) and new_obj["schema"].get("version") == "1.0" and isinstance(obj, dict) and isinstance(obj.get("schema"), dict) and obj["schema"].get("version") != "1.0"):
            changed_files += 1
            removed_total += removed
            if args.write:
                dump_json(fp, new_obj, pretty=args.pretty)

    out = {
        "ok": parse_errors == 0,
        "processed_files": processed if not args.max_files else args.max_files,
        "changed_files": changed_files,
        "removed_forbidden_keys_total": removed_total,
        "parse_errors": parse_errors,
        "write_mode": bool(args.write),
        "pretty": bool(args.pretty),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if parse_errors == 0 else 1

if __name__ == "__main__":
    raise SystemExit(main())
