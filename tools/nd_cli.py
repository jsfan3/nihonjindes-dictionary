#!/usr/bin/env python3
from __future__ import annotations

import argparse
import bisect
import gzip
import json
import os
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

MAX_UNICODE = "\U0010ffff"

KANJI_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
HIRAGANA_RE = re.compile(r"^[\u3040-\u309f\u30fc\u309d\u309e]+$")
KATAKANA_RE = re.compile(r"^[\u30a0-\u30ff\u31f0-\u31ff]+$")
LATINISH_RE = re.compile(r"^[A-Za-z0-9 \-_\"\'\"./:+&()Ａ-Ｚａ-ｚ０-９　－＿]+$")

def repo_root_from_here() -> Path:
    return Path(__file__).resolve().parents[1]

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

def iter_jsonl_gz(path: Path) -> Iterable[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)

def ascii_to_fullwidth(s: str) -> str:
    out = []
    for ch in s:
        code = ord(ch)
        if ch == " ":
            out.append("\u3000")
        elif 0x21 <= code <= 0x7E:
            out.append(chr(code + 0xFEE0))
        else:
            out.append(ch)
    return "".join(out)

def kata_to_hira(s: str) -> str:
    # Convert Katakana to Hiragana (keeps non-katakana unchanged).
    out = []
    for ch in s:
        o = ord(ch)
        # Katakana letters range (ァ..ヶ) map to Hiragana (ぁ..ゖ) by -0x60
        if 0x30A1 <= o <= 0x30F6:
            out.append(chr(o - 0x60))
        else:
            out.append(ch)
    return "".join(out)

def normalize_base(q: str) -> str:
    # Shared baseline normalization:
    # - NFKC normalization
    # - casefold (for Latin)
    # - Latin-ish ASCII → fullwidth (best-effort; NOT romaji search)
    q2 = unicodedata.normalize("NFKC", q).casefold()
    if LATINISH_RE.match(q2):
        q2 = ascii_to_fullwidth(q2)
    return q2

def normalize_query_search(q: str) -> str:
    # Search indices normalize kana to hiragana.
    # This allows katakana queries like タクシー to match keys indexed as たくしー.
    return kata_to_hira(normalize_base(q))

def normalize_query_search_variants(q: str) -> list[str]:
    """Generate multiple normalized query candidates for search.

    Rationale:
    - indices fold katakana -> hiragana
    - some keys may preserve Latin case or use fullwidth forms
    - mixed JP+ASCII queries may require a second normalization attempt

    The first item is always the primary normalization used historically.
    """
    nfkc = unicodedata.normalize("NFKC", q)
    base_raw = nfkc
    base_fold = nfkc.casefold()

    def fullwidth_mixed(s: str) -> str:
        # convert ASCII in mixed strings to fullwidth; keep non-ASCII unchanged
        out = []
        for ch in s:
            code = ord(ch)
            if ch == " ":
                out.append("\u3000")
            elif 0x21 <= code <= 0x7E:
                out.append(chr(code + 0xFEE0))
            else:
                out.append(ch)
        return "".join(out)

    candidates = []
    for b in (base_fold, base_raw):
        # primary path: (casefolded first) + ascii->fullwidth only when purely latinish (via normalize_base)
        # but for mixed strings we also add fullwidth-mixed variants
        candidates.append(kata_to_hira(normalize_base(b)))
        candidates.append(kata_to_hira(fullwidth_mixed(b)))
    # De-duplicate preserving order
    seen=set()
    out=[]
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def normalize_query_lookup_candidates(q: str) -> list[str]:
    # Lookup indices are more heterogeneous; try multiple candidates:
    # - baseline normalized form (keeps katakana)
    # - kana-normalized form (katakana → hiragana), when different
    q0 = normalize_base(q)
    q1 = kata_to_hira(q0)
    if q1 != q0:
        return [q0, q1]
    return [q0]

def detect_bucket(q: str) -> str:
    if HIRAGANA_RE.match(q):
        return "hiragana"
    if KATAKANA_RE.match(q):
        return "katakana"
    if LATINISH_RE.match(q):
        return "latin"
    # If it contains any kanji, prefer kanji bucket
    if KANJI_RE.search(q):
        return "kanji"
    return "other"

@lru_cache(maxsize=32)
def load_search_index(repo: str, base: str) -> Tuple[List[str], Dict[str, List[int]]]:
    root = Path(repo)
    sdir = root / "data" / "search" / "search"
    idx_path = resolve_json_variant(sdir / f"{base}.json") or (sdir / f"{base}.json")
    keys_path = resolve_json_variant(sdir / f"{base}_keys.json") or (sdir / f"{base}_keys.json")
    idx = load_json_any(idx_path)
    keys = load_json_any(keys_path)
    return keys["keys"], idx["map"]

@lru_cache(maxsize=4)
def load_word_rank(repo: str) -> Dict[str, Dict[str, Any]]:
    root = Path(repo)
    sdir = root / "data" / "search" / "search"
    p = resolve_json_variant(sdir / "word_rank.json") or (sdir / "word_rank.json")
    obj = load_json_any(p)
    return obj["rank"]

def prefix_range(sorted_keys: List[str], prefix: str) -> Tuple[int, int]:
    left = bisect.bisect_left(sorted_keys, prefix)
    right = bisect.bisect_right(sorted_keys, prefix + MAX_UNICODE)
    return left, right

def search_prefix(repo: Path, domain: str, mode: str, query: str, limit: int, max_keys: int, common_first: bool) -> List[dict]:
    manifest = load_json_any(repo / "data" / "search" / "search" / "manifest.json")
    q_variants = normalize_query_search_variants(query)

    # Optional rank list for common-first scoring (words only)
    rank = None
    if domain == "words":
        rank_path = resolve_json_variant(repo/"data/seed/index/word_rank.json") or (repo/"data/seed/index/word_rank.json")
        if rank_path.exists():
            rank = load_json_any(rank_path)

    results: List[Tuple] = []
    for qn in q_variants:
        bucket = detect_bucket(qn)
        bases = manifest["domains"][domain][mode]
        base = None
        for b in bases:
            if b.endswith(bucket):
                base = b
                break
        if base is None:
            base = bases[-1]

        keys, mp = load_search_index(str(repo), base)

        # Find matching keys by prefix
        prefix = qn
        i = bisect.bisect_left(keys, prefix)
        match_keys = []
        while i < len(keys) and keys[i].startswith(prefix):
            match_keys.append(keys[i])
            i += 1
            if len(match_keys) >= max_keys:
                break

        # Build scored results
        seen=set()
        for k in match_keys:
            ids = mp.get(k, [])
            for wid in ids:
                if (k, wid) in seen:
                    continue
                seen.add((k, wid))
                if domain == "words" and rank is not None:
                    info = rank.get(str(wid), {"score": 0, "common": False})
                    score = int(info.get("score", 0))
                    common = 1 if info.get("common") else 0
                else:
                    score, common = 0, 0
                exact = 1 if k == qn else 0
                # sort: exact desc, common desc (optional), score desc, shorter key, id
                results.append((exact, common if common_first else 0, score, -len(k), k, wid))

    # Deduplicate by id (keep best key across all variants)
    best_by_id: Dict[int, Tuple] = {}
    for t in results:
        wid = t[-1]
        if wid not in best_by_id or t > best_by_id[wid]:
            best_by_id[wid] = t

    final = sorted(best_by_id.values(), reverse=True)[:limit]
    out=[]
    for t in final:
        exact, common, score, _, k, wid = t
        out.append({"id": wid, "matched_key": k, "score": score, "common": bool(common), "exact": bool(exact), "key_len": len(k)})
    return out


# ----- Word loading helpers -----

def parse_word_range(filename: str) -> Optional[Tuple[int,int]]:
    # words_1000000_1220670.json.gz
    m = re.match(r"words_(\d+)_(\d+)\.json(\.gz)?$", filename)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))

def parse_it_word_range(filename: str) -> Optional[Tuple[int, int]]:
    # it_words_1000220_1175030.json
    m = re.match(r"it_words_(\d+)_(\d+)\.json(\.gz)?$", filename)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))

@lru_cache(maxsize=1)
def list_word_chunks(repo: str) -> List[Tuple[int,int,Path]]:
    root = Path(repo)
    cdir = root/"data/seed/core"
    chunks=[]
    for p in cdir.iterdir():
        r = parse_word_range(p.name)
        if r:
            chunks.append((r[0], r[1], p))
    chunks.sort()
    return chunks

@lru_cache(maxsize=4)
def load_word_chunk(repo: str, chunk_path: str) -> Dict[int, dict]:
    p = Path(chunk_path)
    obj = load_json_any(p)
    entries = obj["entries"]
    return {int(e["id"]): e for e in entries}

@lru_cache(maxsize=4)
def load_word_lang_chunk(repo: str, lang: str, range_start: int, range_end: int) -> Dict[int, dict]:
    root = Path(repo)
    # English is in data/seed/lang; Italian common is in data/lang/it_common/lang
    if lang == "en":
        p = resolve_json_variant(root/f"data/seed/lang/en_words_{range_start}_{range_end}.json") or (root/f"data/seed/lang/en_words_{range_start}_{range_end}.json")
        if not p.exists():
            return {}
        obj = load_json_any(p)
        return {int(e["id"]): e for e in obj.get("entries", [])}
    if lang == "it":
        chunks = list_it_word_chunks(str(root))
        entries: Dict[int, dict] = {}
        for start_id, end_id, p in chunks:
            if end_id < range_start or start_id > range_end:
                continue
            obj = load_json_any(p)
            for e in obj.get("entries", []):
                entries[int(e["id"])] = e
        return entries
    raise ValueError("Unsupported lang")

@lru_cache(maxsize=1)
def list_it_word_chunks(repo: str) -> List[Tuple[int, int, Path]]:
    root = Path(repo)
    meta_path = root/"data/lang/it_common/meta.json"
    if not meta_path.exists():
        return []
    meta = load_json_any(meta_path)
    chunks: List[Tuple[int, int, Path]] = []
    for rel_path in meta.get("files", []):
        p = root/"data/lang/it_common"/rel_path
        r = parse_it_word_range(p.name)
        if r:
            chunks.append((r[0], r[1], p))
    chunks.sort()
    return chunks

def find_word_chunk_for_id(repo: Path, wid: int) -> Optional[Tuple[int,int,Path]]:
    for a,b,p in list_word_chunks(str(repo)):
        if a <= wid <= b:
            return a,b,p
    return None

def word_card(repo: Path, wid: int, lang_pref: str = "it") -> dict:
    chunk = find_word_chunk_for_id(repo, wid)
    if not chunk:
        return {"id": wid, "error": "word id out of range"}
    a,b,p = chunk
    core = load_word_chunk(str(repo), str(p)).get(wid)
    if not core:
        return {"id": wid, "error": "word not found in chunk"}
    en = load_word_lang_chunk(str(repo), "en", a, b).get(wid, {})
    it = load_word_lang_chunk(str(repo), "it", a, b).get(wid, {}) if lang_pref == "it" else {}
    # Merge senses by sense-id
    senses = []
    en_by = {s["id"]: s for s in en.get("senses", [])} if en else {}
    it_by = {s["id"]: s for s in it.get("senses", [])} if it else {}
    for s in core.get("senses", []):
        sid = s.get("id")
        item = {
            "id": sid,
            "pos": s.get("pos", []),
            "xref": s.get("xref", []),
            "ant": s.get("ant", []),
            "gloss_en": en_by.get(sid, {}).get("gloss", []),
            "gloss_it": it_by.get(sid, {}).get("gloss", []) if it_by else [],
            "short_gloss_it": it_by.get(sid, {}).get("short_gloss") if it_by else None,
        }
        senses.append(item)

    primary = core.get("primary", {})
    return {
        "id": wid,
        "primary": primary,
        "forms": core.get("forms", {}),
        "priority": core.get("priority", {}),
        "education": core.get("education", {}),
        "senses": senses,
        "kanji": core.get("kanji", []),
    }

# ----- Kanji & Kana -----

@lru_cache(maxsize=1)
def load_kanji(repo: str) -> dict:
    root = Path(repo)
    p = resolve_json_variant(root/"data/seed/core/kanji.json") or (root/"data/seed/core/kanji.json")
    return load_json_any(p)

@lru_cache(maxsize=1)
def load_kanji_meanings(repo: str, lang: str) -> dict:
    root = Path(repo)
    p = resolve_json_variant(root/f"data/seed/lang/{lang}_kanji_meanings.json") or (root/f"data/seed/lang/{lang}_kanji_meanings.json")
    if not p.exists():
        return {}
    return load_json_any(p)

def uplus_id(ch: str) -> str:
    return f"U+{ord(ch):04X}"

def kanji_card(repo: Path, ch: str) -> dict:
    kid = uplus_id(ch)
    k = load_kanji(str(repo))["entries"].get(kid)
    if not k:
        return {"id": kid, "literal": ch, "error": "kanji not found"}
    en = load_kanji_meanings(str(repo), "en").get("meanings_by_kanji", {}).get(kid, [])
    return {
        "id": kid,
        "literal": k.get("literal"),
        "strokes": k.get("strokes"),
        "radical": k.get("radical"),
        "readings": k.get("readings", {}),
        "education": k.get("education", {}),
        "misc": k.get("misc", {}),
        "components": k.get("components", []),
        "meanings_en": en,
    }

def kanji_list_by_order(repo: Path, start: int, limit: int) -> List[dict]:
    entries = load_kanji(str(repo))["entries"].values()
    ordered = []
    for e in entries:
        if not isinstance(e, dict):
            continue
        edu = e.get("education") or {}
        ordv = edu.get("order_overall")
        if isinstance(ordv, int):
            ordered.append(e)
    ordered.sort(key=lambda e: (e.get("education") or {}).get("order_overall", 10**9))
    out = []
    for e in ordered[max(0, start-1): max(0, start-1) + limit]:
        edu = e.get("education") or {}
        out.append({
            "order_overall": edu.get("order_overall"),
            "literal": e.get("literal"),
            "section": edu.get("section"),
            "grade": edu.get("grade"),
        })
    return out

@lru_cache(maxsize=1)
def load_kana(repo: str) -> list:
    root = Path(repo)
    p = resolve_json_variant(root/"data/seed/core/kana.json") or (root/"data/seed/core/kana.json")
    obj = load_json_any(p)
    return obj.get("entries", [])

def kana_card(repo: Path, symbol: str) -> dict:
    for e in load_kana(str(repo)):
        if e.get("symbol") == symbol:
            return e
    return {"symbol": symbol, "error": "kana not found"}

# ----- Names -----

@lru_cache(maxsize=1)
def load_names_meta(repo: str) -> dict:
    root = Path(repo)
    return load_json_any(root/"data/names/meta.json")

@lru_cache(maxsize=6)
def load_names_chunk(repo: str, core_file: str) -> Dict[int, dict]:
    root = Path(repo)
    p = root/"data/names"/core_file
    return {int(e["id"]): e for e in iter_jsonl_gz(p)}

@lru_cache(maxsize=6)
def load_names_lang_en_chunk(repo: str, lang_file: str) -> Dict[int, dict]:
    root = Path(repo)
    p = root/"data/names"/lang_file
    return {int(e["id"]): e for e in iter_jsonl_gz(p)}

def find_name_chunk(repo: Path, nid: int) -> Optional[dict]:
    meta = load_names_meta(str(repo))
    for ch in meta.get("chunks", []):
        if int(ch["start_id"]) <= nid <= int(ch["end_id"]):
            return ch
    return None

def name_card(repo: Path, nid: int) -> dict:
    ch = find_name_chunk(repo, nid)
    if not ch:
        return {"id": nid, "error": "name id out of range"}
    core = load_names_chunk(str(repo), ch["core_file"]).get(nid)
    en = load_names_lang_en_chunk(str(repo), ch["lang_en_file"]).get(nid, {})
    return {
        "id": nid,
        "primary": core.get("primary") if core else None,
        "forms": core.get("forms") if core else None,
        "types": core.get("types") if core else None,
        "translations_en": en.get("translations", []),
    }

# ----- Categories -----

@lru_cache(maxsize=1)
def load_categories_manifest(repo: str) -> dict:
    root = Path(repo)
    return load_json_any(root/"data/categories/manifest.json")

@lru_cache(maxsize=4)
def load_categories_lang(repo: str, lang: str) -> dict:
    root = Path(repo)
    p = root/"data/categories/lang"/f"{lang}.json"
    if not p.exists():
        return {}
    obj = load_json_any(p)
    return obj.get("categories", {})

@lru_cache(maxsize=1)
def load_top_common_2000(repo: str) -> List[int]:
    root = Path(repo)
    p = resolve_json_variant(root/"data/search/search/common_word_ids.json") or (root/"data/search/search/common_word_ids.json")
    obj = load_json_any(p)
    ids = [int(x) for x in obj.get("ids", [])[:2000]]
    return ids

@lru_cache(maxsize=1)
def load_word_to_category(repo: str) -> Dict[str, str]:
    root = Path(repo)
    p = resolve_json_variant(root/"data/categories/word_to_category.json") or (root/"data/categories/word_to_category.json")
    obj = load_json_any(p)
    return obj.get("mapping", {})

@lru_cache(maxsize=1)
def build_category_index(repo: str) -> Dict[str, List[int]]:
    top = load_top_common_2000(repo)
    m = load_word_to_category(repo)
    out: Dict[str, List[int]] = {}
    for wid in top:
        cid = m.get(str(wid))
        if not cid:
            cid = "misc"
        out.setdefault(cid, []).append(wid)
    return out

def category_list(repo: Path, lang: str) -> List[dict]:
    man = load_categories_manifest(str(repo))
    order = man.get("categories", [])
    lang_map = load_categories_lang(str(repo), lang)
    out=[]
    for cid in order:
        meta = lang_map.get(cid, {})
        out.append({"id": cid, "title": meta.get("title", cid), "description": meta.get("description")})
    return out

def category_show(repo: Path, cid: str, limit: int) -> dict:
    idx = build_category_index(str(repo))
    ids = idx.get(cid, [])
    return {"category_id": cid, "count": len(ids), "word_ids": ids[:limit]}


# ----- CLI -----

def cmd_search(args) -> int:
    repo = Path(args.repo_root).resolve()
    domain = args.domain
    mode = args.mode
    q = args.query

    domains = ["words","names"] if domain == "all" else [domain]
    gathered: List[dict] = []

    for d in domains:
        modes = ["surface","reading"] if mode == "auto" else [mode]
        for m in modes:
            res = search_prefix(repo, d, m, q, limit=args.limit, max_keys=args.max_keys, common_first=args.common_first)
            for r in res:
                r["domain"] = d
                r["mode"] = m
                gathered.append(r)

    # Dedupe across modes (and optionally domains)
    best: Dict[Tuple[str,int], Tuple] = {}
    keep: Dict[Tuple[str,int], dict] = {}

    for r in gathered:
        key = (r["domain"], int(r["id"]))
        exact = 1 if r.get("exact") else 0
        common = 1 if (args.common_first and r.get("common")) else 0
        score = int(r.get("score", 0))
        prefer_surface = 1 if r.get("mode") == "surface" else 0
        key_len = int(r.get("key_len", len(r.get("matched_key",""))))
        t = (exact, common, score, prefer_surface, -key_len)
        if key not in best or t > best[key]:
            best[key] = t
            keep[key] = r

    final = sorted(keep.values(), key=lambda r: (
        1 if r.get("exact") else 0,
        1 if (args.common_first and r.get("common")) else 0,
        int(r.get("score", 0)),
        1 if r.get("mode") == "surface" else 0,
        -int(r.get("key_len", len(r.get("matched_key","")))),
    ), reverse=True)

    final = final[:args.limit]

    if args.format == "json":
        out = []
        for r in final:
            item = dict(r)
            if args.details:
                if r.get("domain") == "words":
                    item["card"] = word_card(repo, int(r["id"]), lang_pref=args.lang)
                else:
                    item["card"] = name_card(repo, int(r["id"]))
            out.append(item)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    # Text output
    for r in final:
        if r.get("domain") == "words":
            ent = word_card(repo, int(r["id"]), lang_pref=args.lang)
            p = ent.get("primary", {}) or {}
            gloss = ""
            trs = ent.get(f"translations_{args.lang}") or ent.get("translations_en") or []
            if trs and trs[0].get("gloss"):
                gloss = trs[0]["gloss"][0]
            print(f"[word] {r['matched_key']} -> {p.get('written','')}【{p.get('reading','')}】 id={r['id']} {gloss}")
        else:
            ent = name_card(repo, int(r["id"]))
            p = ent.get("primary", {}) or {}
            gloss = ""
            trs = ent.get("translations_en") or []
            if trs and trs[0].get("gloss"):
                gloss = trs[0]["gloss"][0]
            print(f"[name] {r['matched_key']} -> {p.get('written','')}【{p.get('reading','')}】 id={r['id']} {gloss}")
    return 0



def cmd_word(args) -> int:
    repo = Path(args.repo_root).resolve()
    if args.id is not None:
        card = word_card(repo, int(args.id), lang_pref=args.lang)
        print(json.dumps(card, ensure_ascii=False, indent=2))
        return 0
    # lookup by query (exact via lookup indices)
    q_candidates = normalize_query_lookup_candidates(args.query)
    ldir = repo/"data/lookup/index"

    ids=set()
    for q in q_candidates:
        bucket = detect_bucket(q)
        surf_file = resolve_json_variant(ldir/f"lookup_surface_{bucket}.json") or (ldir/f"lookup_surface_{bucket}.json")
        read_file = resolve_json_variant(ldir/f"lookup_reading_{bucket}.json") or (ldir/f"lookup_reading_{bucket}.json")

        if surf_file.exists():
            obj=load_json_any(surf_file)
            for wid in obj.get("map", {}).get(q, []):
                ids.add(int(wid))
        if read_file.exists():
            obj=load_json_any(read_file)
            for wid in obj.get("map", {}).get(q, []):
                ids.add(int(wid))

    out=[]
    for wid in sorted(ids)[:args.limit]:
        out.append(word_card(repo, wid, lang_pref=args.lang))
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0

def cmd_kanji(args) -> int:
    repo = Path(args.repo_root).resolve()
    if args.list:
        rows = kanji_list_by_order(repo, start=args.start, limit=args.limit)
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    card = kanji_card(repo, args.kanji)
    print(json.dumps(card, ensure_ascii=False, indent=2))
    return 0

def cmd_kana(args) -> int:
    repo = Path(args.repo_root).resolve()
    card = kana_card(repo, args.kana)
    print(json.dumps(card, ensure_ascii=False, indent=2))
    return 0

def cmd_name(args) -> int:
    repo = Path(args.repo_root).resolve()
    if args.id is not None:
        card = name_card(repo, int(args.id))
        print(json.dumps(card, ensure_ascii=False, indent=2))
        return 0
    # use search index for names surface auto
    res = search_prefix(repo, "names", "surface", args.query, limit=args.limit, max_keys=args.max_keys, common_first=False)
    out=[]
    for r in res:
        out.append(name_card(repo, int(r["id"])))
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0

def cmd_category(args) -> int:
    repo = Path(args.repo_root).resolve()
    if args.action == "list":
        print(json.dumps(category_list(repo, args.lang), ensure_ascii=False, indent=2))
        return 0
    if args.action == "show":
        obj = category_show(repo, args.category_id, limit=args.limit)
        if args.with_words:
            obj["words"]=[word_card(repo, wid, lang_pref=args.lang) for wid in obj["word_ids"]]
        print(json.dumps(obj, ensure_ascii=False, indent=2))
        return 0
    return 1

def build_argparser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="nd_cli.py", description="Nihonjindes dataset CLI (search, lookup, cards).")
    ap.add_argument("--repo-root", default=str(repo_root_from_here()), help="Repository root (default: inferred from script location).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("search", help="Search-as-you-type (prefix) over words and/or names.")
    sp.add_argument("query")
    sp.add_argument("--domain", choices=["words","names","all"], default="all")
    sp.add_argument("--mode", choices=["surface","reading","auto"], default="auto")
    sp.add_argument("--limit", type=int, default=20)
    sp.add_argument("--max-keys", type=int, default=250, help="Max matched keys to scan (performance guard).")
    sp.add_argument("--common-first", action="store_true", help="Prefer common words (by rank/common).")
    sp.add_argument("--details", action="store_true", help="Attach entry cards for each result.")
    sp.add_argument("--lang", choices=["it","en"], default="it", help="Preferred gloss language for word cards.")
    sp.add_argument("--format", choices=["text","json"], default="text")
    sp.set_defaults(func=cmd_search)

    wp = sub.add_parser("word", help="Word card (by id) or exact lookup (by query).")
    g = wp.add_mutually_exclusive_group(required=True)
    g.add_argument("--id", type=int)
    g.add_argument("--query")
    wp.add_argument("--limit", type=int, default=10)
    wp.add_argument("--lang", choices=["it","en"], default="it")
    wp.set_defaults(func=cmd_word)

    kp = sub.add_parser("kanji", help="Kanji card or list by school order.")
    kp.add_argument("--list", action="store_true", help="List kanji by school order_overall.")
    kp.add_argument("--start", type=int, default=1, help="Start index for list (1-based).")
    kp.add_argument("--limit", type=int, default=20)
    kp.add_argument("kanji", nargs="?", default="亜", help="Kanji character (when not using --list).")
    kp.set_defaults(func=cmd_kanji)

    hp = sub.add_parser("kana", help="Kana card.")
    hp.add_argument("kana")
    hp.set_defaults(func=cmd_kana)

    np = sub.add_parser("name", help="Name card (by id) or search by surface prefix.")
    gg = np.add_mutually_exclusive_group(required=True)
    gg.add_argument("--id", type=int)
    gg.add_argument("--query")
    np.add_argument("--limit", type=int, default=10)
    np.add_argument("--max-keys", type=int, default=250)
    np.set_defaults(func=cmd_name)

    cp = sub.add_parser("category", help="Categories (Drops-like) for top 2000 common words.")
    cp.add_argument("action", choices=["list","show"])
    cp.add_argument("--lang", choices=["en","it"], default="en")
    cp.add_argument("--category-id", dest="category_id", default=None)
    cp.add_argument("--limit", type=int, default=50)
    cp.add_argument("--with-words", action="store_true", help="When showing a category, include word cards.")
    cp.set_defaults(func=cmd_category)

    return ap

def main() -> int:
    ap = build_argparser()
    args = ap.parse_args()
    if args.cmd == "category" and args.action == "show" and not args.category_id:
        ap.error("category show requires --category-id")
    return int(args.func(args) or 0)

if __name__ == "__main__":
    raise SystemExit(main())
