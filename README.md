# Nihonjindes Dictionary - Japanese to English and Italian

by [Francesco Galgani](https://www.informatica-libera.net/)

**Work in progress** — You can follow the commits.

## What this repository provides

A structured Japanese lexical dataset (JSON / JSON.GZ / JSONL.GZ) derived from the JMdict family, suitable for:

- search-as-you-type dictionary lookup (words + proper names),
- per-entry “cards” (word / kanji / kana / name),
- vocabulary learning (common words + topic categories),
- guided kanji progression (MEXT/Jōyō school learning order).

English coverage is generally full. Italian coverage is currently focused on common words; consumers should fall back to English when Italian data is missing.

## Quick start (CLI)

```bash
python tools/nd_cli.py --help
python tools/nd_cli.py search 明 --domain words --mode surface --limit 5
python tools/nd_cli.py search タクシー --domain words --mode auto --limit 5
python tools/nd_cli.py word --query 猫 --lang en --limit 1
python tools/nd_cli.py kanji 日
python tools/nd_cli.py kana あ
python tools/nd_cli.py category list --lang en
```

More examples and real outputs: `docs/CLI.md`.

## Validation (local or CI)

```bash
python tools/validate_db.py --mode fast
python tools/validate_schemas.py --mode fast
python tools/validate_relations.py --mode fast
python tools/preflight.py --mode fast
```

## Documentation map

- Dataset layout: `docs/DATASET_REFERENCE.md`
- Indexing & normalization: `docs/INDEXING.md`
- Cross-file relationships: `docs/RELATIONSHIPS.md`
- CLI usage: `docs/CLI.md`
- Schemas & validation: `docs/SCHEMAS.md`, `docs/VALIDATION.md`, `docs/RELEASE.md`

## License

See `LICENSE`. Attribution details are in `ATTRIBUTION.md`.
