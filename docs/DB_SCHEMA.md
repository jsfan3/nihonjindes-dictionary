# DB schema overview

This document provides a compact overview of the dataset. For the canonical, developer-oriented reference, see:

- `docs/DATASET_REFERENCE.md`
- `docs/RELATIONSHIPS.md`
- `docs/INDEXING.md`

## Key points

- Treat `*.json` as the logical name and implement fallback to `*.json.gz`.
- Prefer per-folder `manifest.json` files when discovering “what exists”.
- Do not load `.jsonl.gz` packs fully into RAM; stream them line-by-line.

## Search indices

Search indices live in `data/search/search/` and are built for prefix search (“search-as-you-type”).

- `surface`: written forms (kanji/kana mix)
- `reading`: kana readings (typically hiragana)

Consumers that implement `auto` should generally prefer:
- kana-only query → `reading`
- otherwise → `surface`

See `docs/INDEXING.md` for normalization guidelines.

## Categories

Categories reference word IDs (not strings). Use:

- `data/categories/items/{category_id}.json(.gz)` for category payload
- `data/categories/word_to_category.json(.gz)` for reverse mapping
- `data/categories/lang/{lang}.json` for localized category labels
