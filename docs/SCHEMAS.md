# JSON Schemas

This repository ships a set of JSON Schemas in `schemas/` to validate key dataset files.

## Philosophy

- Schemas are intentionally **conservative** and **forward-compatible**:
  - they validate the stable structure needed for consumers,
  - they allow additional fields so the dataset can evolve without breaking validators.
- Schema versioning is tracked in `schemas/` and in the `schema.version` field of selected JSON files.
  - For the initial public release, schemas and dataset headers use version `1.0`.

## Validation scripts

- `tools/validate_schemas.py`
  - `--mode fast`: validates manifests + a small sample (CI-friendly)
  - `--mode full`: validates a broader set of files (slower; intended for local pre-release checks)

- `tools/validate_db.py`
  - structural and hygiene checks (forbidden metadata keys, required files, etc.)

- `tools/validate_relations.py`
  - referential integrity across packs (sampling in `fast`, more exhaustive in `full`)

See also:
- `docs/VALIDATION.md`
- `docs/RELEASE.md`
