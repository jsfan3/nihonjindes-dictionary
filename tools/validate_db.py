\
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Optional

FORBIDDEN_KEYS = {
    "generated_at_utc", "generated_at", "created_at", "build_stamp", "built_at",
    "timestamp", "time_utc", "supersedes", "superseded_by",
}
VERSION_SUFFIX_RE = re.compile(r"_v\d+\b", re.IGNORECASE)

FAST_MAX_JSON_FILES = 250
FAST_SKIP_LARGE_BYTES = 5 * 1024 * 1024
FAST_JSONL_SAMPLE = 1
FULL_JSONL_SAMPLE = 25


def resolve_json_variant(path: Path) -> Optional[Path]:
    if path.exists():
        return path
    if path.name.endswith(".json"):
        gz = path.with_name(path.name + ".gz")
        if gz.exists():
            return gz
    if path.name.endswith(".json.gz"):
        plain = path.with_name(path.name[:-3])
        if plain.exists():
            return plain
    return None


def load_json_any(path: Path) -> Any:
    if path.name.endswith(".json.gz"):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def iter_json_files(root: Path) -> Iterable[Path]:
    for r, _, files in os.walk(root):
        rp = Path(r)
        for fn in files:
            if fn.endswith(".json") or fn.endswith(".json.gz"):
                yield rp / fn


def iter_jsonl_gz(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def contains_forbidden(obj: Any) -> bool:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in FORBIDDEN_KEYS or "generated_at" in k:
                return True
            if contains_forbidden(v):
                return True
    elif isinstance(obj, list):
        return any(contains_forbidden(x) for x in obj)
    return False


def contains_version_suffix(obj: Any) -> bool:
    if isinstance(obj, str):
        return VERSION_SUFFIX_RE.search(obj) is not None
    if isinstance(obj, dict):
        for k, v in obj.items():
            if contains_version_suffix(k) or contains_version_suffix(v):
                return True
    elif isinstance(obj, list):
        return any(contains_version_suffix(x) for x in obj)
    return False


@dataclass
class Problem:
    code: str
    path: str
    message: str


def add(problems: List[Problem], code: str, path: Path, message: str) -> None:
    problems.append(Problem(code=code, path=str(path), message=message))


def validate_required(repo: Path, problems: List[Problem]) -> None:
    req = [
        repo/"README.md",
        repo/"ATTRIBUTION.md",
        repo/"LICENSE",
        repo/"data/manifest.json",
    ]
    for p in req:
        if not p.exists():
            add(problems, "missing.required", p, "Required file missing")

    sources = repo/"sources"
    if not sources.exists():
        add(problems, "missing.sources_dir", sources, "sources/ directory missing")
    else:
        expected = ["JMdict.gz","JMdict_e_examp.gz","JMnedict.xml.gz","kanjidic2.xml.gz","kradzip.zip"]
        for fn in expected:
            p = sources/fn
            if not p.exists():
                add(problems, "missing.source", p, "Expected upstream source file missing")


def validate_names(repo: Path, problems: List[Problem], mode: str) -> None:
    names = repo/"data/names"
    meta_p = names/"meta.json"
    if not meta_p.exists():
        add(problems, "names.missing_meta", meta_p, "Missing data/names/meta.json")
        return
    try:
        meta = load_json_any(meta_p)
    except Exception as e:
        add(problems, "names.meta_parse", meta_p, f"Failed to parse meta.json: {e}")
        return

    chunks = meta.get("chunks")
    if not isinstance(chunks, list) or not chunks:
        add(problems, "names.meta_chunks", meta_p, "meta.chunks missing/empty")
        return

    to_check = chunks[:2] if mode == "fast" else chunks
    sample = FAST_JSONL_SAMPLE if mode == "fast" else FULL_JSONL_SAMPLE

    for i, ch in enumerate(to_check):
        if not isinstance(ch, dict):
            add(problems, "names.chunk_invalid", meta_p, f"Chunk {i} not an object")
            continue
        for key in ("core_file","lang_en_file","start_id","end_id"):
            if key not in ch:
                add(problems, "names.chunk_missing_field", meta_p, f"Chunk {i} missing {key}")

        core = names / ch.get("core_file","")
        en = names / ch.get("lang_en_file","")
        if not core.exists():
            add(problems, "names.core_missing", core, "Core chunk missing")
            continue
        if not en.exists():
            add(problems, "names.en_missing", en, "Lang/en chunk missing")
            continue

        try:
            n = 0
            for obj in iter_jsonl_gz(core):
                if not isinstance(obj, dict) or "id" not in obj:
                    add(problems, "names.entry_invalid", core, "Invalid entry in jsonl.gz (missing object/id)")
                    break
                n += 1
                if n >= sample:
                    break
        except Exception as e:
            add(problems, "names.jsonl_read", core, f"Failed reading jsonl.gz: {e}")


def validate_search(repo: Path, problems: List[Problem]) -> None:
    sdir = repo/"data/search/search"
    man = sdir/"manifest.json"
    if not man.exists():
        add(problems, "search.missing_manifest", man, "Missing search manifest")
        return
    try:
        m = load_json_any(man)
    except Exception as e:
        add(problems, "search.manifest_parse", man, f"Failed parsing search manifest: {e}")
        return

    if m.get("has_names") is True:
        idx = m.get("names_index_files", {})
        for kind in ("surface","reading"):
            files = idx.get(kind, [])
            if not isinstance(files, list) or not files:
                add(problems, "search.names_index_missing", man, f"names_index_files.{kind} missing/empty")
                continue
            for fn in files:
                p = resolve_json_variant(sdir/fn) or (sdir/fn)
                if not p.exists():
                    add(problems, "search.index_missing", sdir/fn, "Referenced index missing (.json or .json.gz)")


def validate_categories(repo: Path, problems: List[Problem]) -> None:
    cdir = repo/"data/categories"
    man = cdir/"manifest.json"
    if not man.exists():
        add(problems, "categories.missing_manifest", man, "Missing categories manifest")
        return
    try:
        m = load_json_any(man)
    except Exception as e:
        add(problems, "categories.manifest_parse", man, f"Failed parsing categories manifest: {e}")
        return
    scope = m.get("scope", {})
    if isinstance(scope, dict) and scope.get("common_top_n") != 2000:
        add(problems, "categories.scope", man, "Expected scope.common_top_n == 2000")

    w2c = resolve_json_variant(cdir/"word_to_category.json") or (cdir/"word_to_category.json")
    if not w2c.exists():
        add(problems, "categories.word_to_category_missing", cdir/"word_to_category.json", "Missing word_to_category.json(.gz)")


def validate_forbidden_scan(repo: Path, problems: List[Problem], mode: str) -> None:
    data = repo/"data"
    checked = 0
    for fp in iter_json_files(data):
        checked += 1
        if mode == "fast" and checked > FAST_MAX_JSON_FILES:
            break
        try:
            if mode == "fast" and fp.stat().st_size > FAST_SKIP_LARGE_BYTES:
                continue
            obj = load_json_any(fp)
        except Exception as e:
            add(problems, "json.parse_error", fp, str(e))
            continue
        if contains_forbidden(obj):
            add(problems, "json.forbidden_key", fp, "Found forbidden metadata key")
        if contains_version_suffix(obj):
            add(problems, "json.version_suffix", fp, "Found _vN-like suffix in a string")


def main() -> int:
    ap = argparse.ArgumentParser(description="CI-friendly structural validation for Nihonjindes DB.")
    ap.add_argument("--repo-root", default=".", help="Repository root (default: .)")
    ap.add_argument("--mode", choices=["fast","full"], default="fast", help="Validation mode")
    ap.add_argument("--max-errors", type=int, default=200, help="Max errors to report")
    args = ap.parse_args()

    repo = Path(args.repo_root).resolve()
    problems: List[Problem] = []

    validate_required(repo, problems)
    validate_categories(repo, problems)
    validate_names(repo, problems, mode=args.mode)
    validate_search(repo, problems)
    validate_forbidden_scan(repo, problems, mode=args.mode)

    ok = len(problems) == 0
    out = {
        "ok": ok,
        "mode": args.mode,
        "problem_count": len(problems),
        "problems": [p.__dict__ for p in problems[:args.max_errors]],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
