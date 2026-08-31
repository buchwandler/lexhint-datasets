#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping
from pathlib import Path

from scripts.catalog import IMMUTABLE_FIELDS, CatalogError, load_catalog


def check_catalog_immutability(
    base: Mapping[str, object], proposed: Mapping[str, object]
) -> None:
    def by_tag(value: Mapping[str, object]) -> dict[str, list[Mapping[str, object]]]:
        artifacts = value.get("artifacts", [])
        if not isinstance(artifacts, list):
            raise CatalogError("catalog artifacts must be an array")
        result: dict[str, list[Mapping[str, object]]] = {}
        for artifact in artifacts:
            if not isinstance(artifact, Mapping):
                raise CatalogError("catalog artifact must be an object")
            tag = str(artifact.get("release_tag", ""))
            result.setdefault(tag, []).append(artifact)
        return result

    base_by_tag = by_tag(base)
    proposed_by_tag = by_tag(proposed)
    for tag, base_entries in base_by_tag.items():
        proposed_entries = proposed_by_tag.get(tag)
        if proposed_entries is None:
            raise CatalogError(
                f"Published release {tag!r} was removed from the catalog."
            )
        base_values = sorted(
            (
                tuple(entry.get(field) for field in IMMUTABLE_FIELDS)
                for entry in base_entries
            ),
            key=repr,
        )
        proposed_values = sorted(
            (
                tuple(entry.get(field) for field in IMMUTABLE_FIELDS)
                for entry in proposed_entries
            ),
            key=repr,
        )
        if base_values != proposed_values:
            raise CatalogError(
                f"Published release {tag!r} changed immutable catalog metadata. "
                "Publish a new release tag instead of rewriting an existing catalog entry."
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check that published catalog release metadata is immutable."
    )
    parser.add_argument(
        "base", type=Path, help="catalog from the merge base/default branch"
    )
    parser.add_argument("proposed", type=Path, help="proposed catalog")
    args = parser.parse_args()
    try:
        base = load_catalog(args.base)
        proposed = load_catalog(args.proposed)
        check_catalog_immutability(base, proposed)
    except CatalogError as exc:
        print(f"catalog immutability check failed: {exc}", file=sys.stderr)
        return 1
    print("catalog immutable entries verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
