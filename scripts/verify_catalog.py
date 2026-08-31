#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scripts.catalog import CatalogError, load_catalog


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a Lexhint dataset catalog.")
    parser.add_argument(
        "path", nargs="?", type=Path, default=Path("catalog/datasets.json")
    )
    args = parser.parse_args()
    try:
        catalog = load_catalog(args.path)
    except CatalogError as exc:
        print(f"catalog verification failed: {exc}", file=sys.stderr)
        return 1
    print(f"catalog verified: {len(catalog['artifacts'])} artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
