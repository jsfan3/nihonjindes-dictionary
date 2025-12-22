# Indexing and normalization notes

This document describes the indexing assumptions for search and lookup.

## Modes: surface vs reading

- **surface**: written form, can include kanji, hiragana, katakana, and symbols.
- **reading**: kana reading, typically hiragana.

When implementing “auto”:
- if the query contains kana and no kanji, prefer `reading`,
- otherwise, prefer `surface`.

## Kana folding

To improve UX:
- fold **katakana → hiragana** for reading searches
  - e.g. `タクシー` behaves like `たくしー`.

## Unicode normalization

Use Unicode normalization (NFKC) to reduce surprises from compatibility characters:
- fullwidth Latin → ASCII (or vice versa, as long as it matches your index)
- halfwidth katakana → fullwidth katakana

A practical approach for consumers:
- normalize query with NFKC
- then apply kana folding (if using reading indices)
- then do prefix search on the normalized key

## Long vowel mark (ー)

The Japanese long vowel mark appears in katakana and sometimes in hiragana contexts.
Do not discard it; treat it as part of the key. When folding katakana → hiragana, preserve `ー`.
