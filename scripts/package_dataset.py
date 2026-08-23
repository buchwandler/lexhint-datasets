#!/usr/bin/env python3
"""Backward-compatible single-artifact entry point.

Use package_release.py for new releases containing multiple artifacts.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts.config import load_config
from scripts.package_release import PackagingError, package_artifact, package_release


def main() -> int:
    config = load_config()
    parser = argparse.ArgumentParser(
        description="Package one Lexhint dataset artifact."
    )
    parser.add_argument("database", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("dist"))
    parser.add_argument("--language", default="en")
    parser.add_argument(
        "--variant",
        default="rich",
        choices=tuple(config.variants),
    )
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--lexhint-ref", required=True)
    parser.add_argument("--lexhint-commit", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--source-label", required=True)
    parser.add_argument("--source-sha256")
    parser.add_argument("--attribution", type=Path, default=Path("DATA_SOURCES.md"))
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    try:
        record = package_artifact(
            args.database,
            language=args.language,
            variant=args.variant,
            dataset_version=args.dataset_version,
            output_dir=args.output_dir,
            config=config,
        )
        manifest = package_release(
            [record],
            output_dir=args.output_dir,
            dataset_version=args.dataset_version,
            lexhint_ref=args.lexhint_ref,
            lexhint_commit=args.lexhint_commit,
            source_url=args.source_url,
            source_label=args.source_label,
            source_sha256=args.source_sha256,
            attribution=args.attribution,
            publish=args.publish,
            config=config,
        )
    except (PackagingError, OSError, ValueError) as exc:
        print(f"packaging failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(manifest["artifacts"][0], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
