\
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
from typing import Any, List

import jsonschema


def load_json_any(path: Path) -> Any:
    if path.name.endswith(".json.gz"):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def resolve_variant(path: Path) -> Path | None:
    if path.exists():
        return path
    if path.name.endswith(".json") and (path.with_name(path.name + ".gz")).exists():
        return path.with_name(path.name + ".gz")
    if path.name.endswith(".json.gz") and (path.with_name(path.name[:-3])).exists():
        return path.with_name(path.name[:-3])
    return None


def validate_one(file_path: Path, schema_path: Path, label: str, problems: List[dict]) -> None:
    try:
        obj = load_json_any(file_path)
    except Exception as e:
        problems.append({"type": "parse_error", "label": label, "path": str(file_path), "error": str(e)})
        return
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.validate(instance=obj, schema=schema)
    except Exception as e:
        problems.append({"type": "schema_error", "label": label, "path": str(file_path), "error": str(e)})


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate selected dataset files against JSON Schemas (CI-friendly).")
    ap.add_argument("--repo-root", default=".", help="Repository root (default: .)")
    ap.add_argument("--schema-dir", default="schemas", help="Schema directory (default: schemas)")
    ap.add_argument("--mode", choices=["fast","full"], default="fast", help="Validation mode")
    ap.add_argument("--max-errors", type=int, default=200, help="Max errors to report")
    args = ap.parse_args()

    repo = Path(args.repo_root).resolve()
    sdir = (repo / args.schema_dir).resolve()
    data = repo / "data"

    if not sdir.exists():
        raise SystemExit(f"Missing schemas directory: {sdir}")
    if not data.exists():
        raise SystemExit(f"Missing data directory: {data}")

    problems: List[dict] = []

    core = [
        ("data/manifest.json", "manifest.schema.json", "global manifest"),
        ("data/categories/manifest.json", "categories_manifest.schema.json", "categories manifest"),
        ("data/search/search/manifest.json", "search_manifest.schema.json", "search manifest"),
        ("data/names/meta.json", "names_meta.schema.json", "names meta"),
    ]
    for rel, sch, label in core:
        p = resolve_variant(repo/rel) or (repo/rel)
        if not p.exists():
            problems.append({"type": "missing", "label": label, "path": rel})
            continue
        validate_one(p, sdir/sch, label, problems)

    items_dir = data/"categories/items"
    if items_dir.exists():
        files = sorted(list(items_dir.glob("*.json")) + list(items_dir.glob("*.json.gz")))
        if files:
            picks = files[:1] if args.mode == "fast" else files
            for p in picks:
                validate_one(p, sdir/"category_items.schema.json", "category items", problems)
        else:
            problems.append({"type": "missing", "label": "category items", "path": str(items_dir)})
    else:
        problems.append({"type": "missing", "label": "category items dir", "path": str(items_dir)})

    if args.mode == "full":
        search_dir = data/"search/search"
        if search_dir.exists():
            idx_files = sorted([p for p in search_dir.iterdir() if p.name != "manifest.json" and (p.name.endswith(".json") or p.name.endswith(".json.gz"))])
            for p in idx_files:
                validate_one(p, sdir/"search_index.schema.json", "search index", problems)

        lookup_dir = data/"lookup/index"
        if lookup_dir.exists():
            idx_files = sorted([p for p in lookup_dir.iterdir() if p.name != "manifest.json" and (p.name.endswith(".json") or p.name.endswith(".json.gz"))])
            for p in idx_files:
                validate_one(p, sdir/"lookup_index.schema.json", "lookup index", problems)

    ok = len(problems) == 0
    out = {"ok": ok, "mode": args.mode, "problem_count": len(problems), "problems": problems[:args.max_errors]}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
