# Validation addendum: cross-file relations

This addendum documents cross-file relation validation.

## Cross-file relations

```bash
python tools/validate_relations.py --mode fast
python tools/validate_relations.py --mode full
```

`fast` uses sampling; `full` is more exhaustive and is intended for local release checks.
