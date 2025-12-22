# Cross-file relationships

This document summarizes key relationships across packs.

## Words

- word entries live in `data/seed/core/...` (JMdict-derived).
- lookup indices in `data/lookup/index/` resolve:
  - surface/reading forms → word ids
  - ids → entry locations (depending on pack structure)
- search indices in `data/search/search/` provide prefix search:
  - query → list of candidate word ids (plus ranking metadata when available)

## Names

- name entries are chunked in `data/names/*.jsonl.gz` and indexed in `data/search/search/`.
- `data/names/meta.json` is required to locate the correct chunk for a given name id.

## Kanji

- kanji reference entries are derived from KANJIDIC2 and KRADFILE.
- the MEXT/Jōyō school order list is provided in `data/seed/**/learning_orders.json(.gz)`.

## Kana

- kana reference entries provide:
  - character → romaji / IPA-friendly reading (as stored)
  - stroke order metadata when available (depends on seed pack contents)

## Categories

- categories reference **word ids** (not strings).
- use `word_to_category.json(.gz)` for reverse mapping:
  - word id → category id
- use `items/{category_id}.json(.gz)` for category payload:
  - category id → list of word ids

## Language packs

- language packs attach localized glosses to word ids (and/or entry keys depending on pack).
- missing localized data should be treated as “no translation available” and can fall back to English.
