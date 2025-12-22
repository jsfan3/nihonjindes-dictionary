# Validation

Two validators are provided:

- `tools/validate_db.py`: structural and hygiene checks (CI-friendly).
- `tools/validate_schemas.py`: JSON Schema checks (CI-friendly in `fast` mode).

## Run locally

```bash
python tools/validate_db.py --mode fast
python tools/validate_schemas.py --mode fast
```

Full validation (slower):

```bash
python tools/validate_db.py --mode full
python tools/validate_schemas.py --mode full
```

## GitHub Actions

The workflow `.github/workflows/db_validate.yml` runs `fast` mode on each PR/push.
You can enforce it as a required status check via branch protection / rulesets.

Cross-file relations:

```bash
python tools/validate_relations.py --mode fast
python tools/validate_relations.py --mode full
```
