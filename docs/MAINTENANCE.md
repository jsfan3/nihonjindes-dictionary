# Maintenance

## Prune repo noise

Dry-run:

```bash
python tools/prune_repo.py --repo-root .
```

Apply (also remove redundant `.json` when `.json.gz` exists):

```bash
python tools/prune_repo.py --repo-root . --write --remove-json-when-gz-exists
```

## Sanitize metadata keys

See `tools/sanitize_repo.py` (removes timestamps/supersedes markers and normalizes `schema.version`).
