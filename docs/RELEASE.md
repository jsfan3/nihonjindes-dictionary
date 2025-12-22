# Release checklist (dataset)

This checklist is intended to keep releases reproducible and PR-safe.

## 1) Validate (fast)

```bash
python tools/validate_db.py --mode fast
python tools/validate_schemas.py --mode fast
python tools/preflight.py --mode fast
python tools/validate_relations.py --mode fast
```

## 2) Validate (full, locally)

Run this before tagging a release, or after large dataset regeneration:

```bash
python tools/validate_db.py --mode full
python tools/validate_schemas.py --mode full
python tools/validate_relations.py --mode full
python tools/preflight.py --mode full
```

Notes:
- `validate_relations.py` checks referential integrity across packs (sampling in fast, more exhaustive in full).
- Full checks may take significantly longer than CI runs.

## 3) Prune repo noise (optional)

```bash
python tools/prune_repo.py --repo-root . --write --remove-json-when-gz-exists
```

## 4) Compression policy (when regenerating data)

This repository stores large JSON as `.json.gz`. When you rebuild the dataset, apply the compression plan:

```bash
python tools/apply_compression.py --repo-root . --data-dir data --plan tools/compression_plan.json --write --sanitize
```

See `docs/COMPRESSION.md`.

## 5) GitHub protection (recommended)

Enable:
- required status checks: `DB validation`
- PR reviews as needed
- prevent direct pushes to `main` (optional)
