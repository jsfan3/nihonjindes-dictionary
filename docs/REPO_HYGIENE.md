# Repository hygiene

This repository is intended to be committed as source data + tools.

## Rules

- Do not commit tool output bundles (`*.zip`, `*.tar.gz`, etc.) except upstream source archives in `sources/`.
- Do not commit Python caches (`__pycache__/`, `*.pyc`).
- Do not commit local build artifacts (`optimized/`, `build/`, `dist/`).

## Enforcing the rules

Run:

```bash
python tools/validate_repo_hygiene.py --repo-root .
```

Apply cleanup:

```bash
python tools/prune_repo.py --repo-root . --write --remove-json-when-gz-exists
```

The CI workflow `DB validation` is designed to stay fast; hygiene checks are also fast and can be used as part of it.
