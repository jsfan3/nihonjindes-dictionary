#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

def main() -> int:
    p = argparse.ArgumentParser(description="Inspect a .json.gz file (pretty-print or write decompressed .json).")
    p.add_argument("input", help="Path to .json.gz")
    p.add_argument("--output", help="If set, write decompressed pretty JSON to this path")
    args = p.parse_args()

    inp = Path(args.input).resolve()
    if not inp.exists() or not inp.name.endswith(".json.gz"):
        raise SystemExit("Input must be an existing .json.gz file")

    with gzip.open(inp, "rt", encoding="utf-8") as f:
        obj = json.load(f)

    text = json.dumps(obj, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        out = Path(args.output).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8", newline="\n")
    else:
        try:
    print(text, end="")
except BrokenPipeError:
    # When piped to tools like `head`, stdout may close early.
    return 0
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
