# Preflight

Run preflight checks before releasing or making large dataset changes:

```bash
python tools/preflight.py --repo-root . --mode fast
```

In CI you may skip the file size scan:

```bash
python tools/preflight.py --repo-root . --mode fast --skip-size-scan
```

For exhaustive checks:

```bash
python tools/preflight.py --repo-root . --mode full
```

Preflight also runs `tools/validate_relations.py` when available.
