#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
import random
from pathlib import Path
from typing import Any, Iterable, List, Optional, Set


def load_json_any(path: Path) -> Any:
    if path.name.endswith(".json.gz"):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def resolve_variant(path: Path) -> Optional[Path]:
    if path.exists():
        return path
    if path.name.endswith(".json") and (path.with_name(path.name + ".gz")).exists():
        return path.with_name(path.name + ".gz")
    if path.name.endswith(".json.gz") and (path.with_name(path.name[:-3])).exists():
        return path.with_name(path.name[:-3])
    return None


def iter_jsonl_gz(path: Path) -> Iterable[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def fail(problems: List[dict], code: str, path: str, message: str) -> None:
    problems.append({"code": code, "path": path, "message": message})


def load_manifest(repo: Path) -> dict:
    return load_json_any(repo / "data" / "manifest.json")


def load_word_id_set(repo: Path, max_ids: int = 0) -> Set[int]:
    """Best-effort set of known word IDs.

    Prefers compact word-id lists if present; otherwise returns an empty set.
    max_ids=0 means load all (if supported by the source).
    """
    candidates = [
        repo / "data/seed/index/word_ids.json",
        repo / "data/seed/index/word_ids.json.gz",
        repo / "data/lookup/index/word_ids.json",
        repo / "data/lookup/index/word_ids.json.gz",
    ]
    for c in candidates:
        p = resolve_variant(c)
        if p and p.exists():
            obj = load_json_any(p)
            if isinstance(obj, dict) and isinstance(obj.get("ids"), list):
                ids = obj["ids"]
                if max_ids and max_ids > 0:
                    ids = ids[:max_ids]
                return set(int(x) for x in ids)
            if isinstance(obj, list):
                return set(int(x) for x in (obj if not max_ids else obj[:max_ids]))
    return set()


def validate_categories_words_exist(repo: Path, problems: List[dict], mode: str) -> None:
    cdir = repo / "data" / "categories"
    w2c = resolve_variant(cdir / "word_to_category.json") or (cdir / "word_to_category.json")
    if not w2c.exists():
        fail(problems, "categories.missing_word_to_category", str(w2c), "Missing word_to_category.json(.gz)")
        return

    mapping = load_json_any(w2c)
    if not isinstance(mapping, dict):
        fail(problems, "categories.invalid_word_to_category", str(w2c), "Expected object mapping word_id -> category_id")
        return

    word_ids = load_word_id_set(repo)
    if not word_ids:
        # If a canonical word-id list isn't present, we can't do a strict referential check here.
        return

    keys = list(mapping.keys())
    if mode == "fast":
        random.shuffle(keys)
        keys = keys[: min(1000, len(keys))]

    for k in keys:
        try:
            wid = int(k)
        except Exception:
            fail(problems, "categories.word_id_not_int", str(w2c), f"Non-integer word_id key: {k!r}")
            continue
        if wid not in word_ids:
            fail(problems, "categories.word_id_missing", str(w2c), f"word_id {wid} not found in canonical word ID set")
            if mode == "fast" and len(problems) > 50:
                break


def validate_kanji_order_exists(repo: Path, problems: List[dict], mode: str) -> None:
    """Validate that the MEXT/Jōyō learning order references existing kanji entries.

    The canonical file is `data/seed/core/learning_orders.json(.gz)` under key
    `kanji_mext_joyo_ordered`.
    """
    candidates = [
        repo / "data/seed/core/learning_orders.json",
        repo / "data/seed/core/learning_orders.json.gz",
    ]
    lo_path = None
    for c in candidates:
        p = resolve_variant(c)
        if p and p.exists():
            lo_path = p
            break
    if not lo_path:
        return

    obj = load_json_any(lo_path)
    items = obj.get("kanji_mext_joyo_ordered") if isinstance(obj, dict) else None
    if not isinstance(items, list):
        fail(problems, "learning_orders.invalid", str(lo_path), "Expected key 'kanji_mext_joyo_ordered' as a list")
        return

    kanji_list = []
    for it in items:
        if isinstance(it, dict) and isinstance(it.get("kanji"), str) and it["kanji"]:
            kanji_list.append(it["kanji"])

    # Load known kanji set (best-effort)
    kanji_set: Set[str] = set()
    kanji_entries_candidates = [
        repo / "data/seed/core/kanji.json",
        repo / "data/seed/core/kanji.json.gz",
        repo / "data/seed/core/kanji_entries.json",
        repo / "data/seed/core/kanji_entries.json.gz",
    ]
    for c in kanji_entries_candidates:
        p = resolve_variant(c)
        if p and p.exists():
            kobj = load_json_any(p)
            if isinstance(kobj, dict) and isinstance(kobj.get("entries"), list):
                for e in kobj["entries"]:
                    if isinstance(e, dict) and isinstance(e.get("literal"), str):
                        kanji_set.add(e["literal"])
            elif isinstance(kobj, dict) and isinstance(kobj.get("by_literal"), dict):
                kanji_set |= set(kobj["by_literal"].keys())
            elif isinstance(kobj, dict) and isinstance(kobj.get("map"), dict):
                kanji_set |= set(kobj["map"].keys())
            break

    if not kanji_set:
        # Basic uniqueness only
        if len(set(kanji_list)) != len(kanji_list):
            fail(problems, "learning_orders.duplicates", str(lo_path), "Duplicate kanji found in order list")
        return

    check_list = kanji_list
    if mode == "fast" and len(check_list) > 500:
        check_list = random.sample(check_list, 500)

    for k in check_list:
        if k not in kanji_set:
            fail(problems, "learning_orders.missing_kanji_entry", str(lo_path), f"Kanji {k} not found in kanji entries")
            if mode == "fast" and len(problems) > 50:
                break

def validate_names_chunks_consistent(repo: Path, problems: List[dict], mode: str) -> None:
    meta_path = repo / "data" / "names" / "meta.json"
    if not meta_path.exists():
        return
    meta = load_json_any(meta_path)
    chunks = meta.get("chunks")
    if not isinstance(chunks, list) or not chunks:
        return

    ncheck = 2 if mode == "fast" else len(chunks)
    for ch in chunks[:ncheck]:
        if not isinstance(ch, dict):
            continue
        core = repo / "data" / "names" / ch.get("core_file", "")
        en = repo / "data" / "names" / ch.get("lang_en_file", "")
        if not core.exists() or not en.exists():
            continue

        try:
            core_iter = iter_jsonl_gz(core)
            en_iter = iter_jsonl_gz(en)
            for _ in range(5 if mode == "fast" else 50):
                c = next(core_iter, None)
                e = next(en_iter, None)
                if c is None or e is None:
                    break
                if isinstance(c, dict) and isinstance(e, dict) and c.get("id") != e.get("id"):
                    fail(problems, "names.chunk_id_mismatch", str(core), f"Core/en id mismatch: {c.get('id')} != {e.get('id')}")
                    break
        except Exception as ex:
            fail(problems, "names.chunk_read_error", str(core), f"Failed reading names chunks: {ex}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate cross-file relations and referential integrity.")
    ap.add_argument("--repo-root", default=".", help="Repository root (default: .)")
    ap.add_argument("--mode", choices=["fast", "full"], default="fast", help="fast=sampling, full=more exhaustive")
    ap.add_argument("--max-errors", type=int, default=200, help="Max errors to report")
    ap.add_argument("--seed", type=int, default=12345, help="Random seed for sampling")
    args = ap.parse_args()

    random.seed(args.seed)

    repo = Path(args.repo_root).resolve()
    problems: List[dict] = []

    # manifest read (required)
    try:
        load_manifest(repo)
    except Exception as e:
        fail(problems, "manifest.read_error", "data/manifest.json", str(e))

    validate_categories_words_exist(repo, problems, mode=args.mode)
    validate_kanji_order_exists(repo, problems, mode=args.mode)
    validate_names_chunks_consistent(repo, problems, mode=args.mode)

    ok = len(problems) == 0
    out = {"ok": ok, "mode": args.mode, "problem_count": len(problems), "problems": problems[: args.max_errors]}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
