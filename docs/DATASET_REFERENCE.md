# Dataset reference

This document describes the *published* dataset layout and how the files relate to each other.
It is intended for developers who want to consume the data (mobile apps, CLIs, services).

## Formats and conventions

### JSON vs JSON.GZ vs JSONL.GZ

- **`.json`**: plain UTF-8 JSON (human-readable).
- **`.json.gz`**: gzip-compressed JSON (usually minified). Treat the `*.json` name as the *logical* name and implement:
  1. try `foo.json`
  2. if missing, try `foo.json.gz`
- **`.jsonl.gz`**: gzip-compressed JSON Lines (one JSON object per line). This format is designed for streaming; avoid loading entire files into RAM.

### Identifiers

- **word id**: integer identifier for a JMdict-derived vocabulary entry.
- **name id**: integer identifier for a JMnedict-derived proper-name entry.
- **kanji**: addressed by the kanji character itself (Unicode literal), and sometimes also via internal IDs depending on the pack.
- **kana**: addressed by the kana character itself (Unicode literal).

## Top-level entry point

### `data/manifest.json`

Single entry point describing dataset components and where to find their manifests.
Consumers should read this first to discover available modules and file paths.

## Core vocabulary / kanji / kana seed packs

### `data/seed/`

The `seed` area contains the core entities and supporting indices used by lookup and search.

Typical subfolders:

- `data/seed/core/`  
  Core entities (words, kanji, kana, learning orders, etc.). Large packs are `.json.gz`.

- `data/seed/index/`  
  Compact indices and ordered lists (e.g. learning orders). Large packs are `.json.gz`.

Important files you can expect (best-effort; consult `data/seed/**/manifest.json` for authoritative lists):

- `.../learning_orders.json(.gz)`  
  Contains kanji learning orders, including the MEXT/Jōyō ordered list used by the app “guided path”.

## Lookup indices

### `data/lookup/index/`

Indices that map from “forms” to IDs and support deterministic lookup.

Use cases:
- exact-match lookup for a word form (surface or reading),
- word-id to entry resolution,
- building app-level caches.

Authoritative list of index files is in:
- `data/lookup/index/manifest.json`

## Search-as-you-type indices

### `data/search/search/`

Prefix-search indices intended for “search-as-you-type” UX.

Two parallel modes exist:

- **surface**: written forms (kanji/kana mix), e.g. `猫`, `明白`
- **reading**: kana readings (usually hiragana), e.g. `ねこ`, `めいはく`

Authoritative list of index files is in:
- `data/search/search/manifest.json`

### Normalization (consumer responsibilities)

Indices are built on normalized keys (see also `docs/INDEXING.md`). In general, consumers should:
- apply Unicode normalization (NFKC) for compatibility forms,
- optionally fold katakana → hiragana when searching “reading”,
- treat “auto” mode as: kana query → reading indices; kanji query → surface indices.

## Proper names pack

### `data/names/`

Names are stored as chunked JSONL.GZ packs:

- `data/names/meta.json` describes chunk files and ID ranges.
- each chunk has:
  - one **core** file (forms/readings/type metadata),
  - one **lang/en** file (English glosses).

This design:
- keeps files small for GitHub and mobile downloads,
- enables streaming reads.

## Topic categories for common words

### `data/categories/`

Categories are built on a selected set of common words (currently: top 2000).

Key files:

- `data/categories/manifest.json`  
  Scope and category list, plus patterns:
  - `item_file_pattern`: `items/{category_id}.json.gz`
  - `lang_file_pattern`: `lang/{lang}.json`

- `data/categories/items/{category_id}.json(.gz)`  
  Category payload: list of word IDs (and optional per-item metadata).

- `data/categories/word_to_category.json(.gz)`  
  Reverse map: `word_id -> category_id` (useful for UI “where does this word belong?”).

- `data/categories/lang/{lang}.json`  
  Localized category names/labels.

## Language packs

### `data/lang/`

Language packs provide localized glosses and UI labels.
English coverage is generally full; Italian coverage is currently focused on common words.

Consumers should treat missing localized glosses as:
- fallback to English,
- optionally allow user-provided overrides at the app layer.

## Where to look for authoritative file lists

Most folders include a `manifest.json` that lists the exact files published. Prefer the manifest over assumptions.

Recommended discovery order:
1. `data/manifest.json`
2. the referenced module manifests (seed/search/lookup/names/categories/lang)
