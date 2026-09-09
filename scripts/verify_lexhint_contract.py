#!/usr/bin/env python3
from __future__ import annotations

import argparse
import inspect
import json
import sys
from pathlib import Path
from typing import Any

import lexhint
from lexhint import (
    DATASET_VARIANT_NAMES,
    DATASET_VARIANTS,
    DEFAULT_DATASET_VARIANT,
    SCHEMA_VERSION,
    SOURCE_VARIANTS,
    supported_base_languages,
)
from lexhint.builder import build_dictionary

from scripts.config import DatasetConfig, load_config


class ContractError(RuntimeError):
    """The installed Lexhint contract does not match dataset configuration."""


def _format_values(values: tuple[str, ...]) -> str:
    return ", ".join(values) or "<none>"


def verify_contract(
    config: DatasetConfig | None = None,
    *,
    lexhint_commit: str | None = None,
    expected_version: str | None = None,
) -> dict[str, Any]:
    config = config or load_config()
    lexhint_version = str(lexhint.__version__).strip()
    if not lexhint_version or lexhint_version == "0+unknown":
        raise ContractError(
            f"Lexhint version is not release-identifiable: {lexhint_version!r}"
        )
    if expected_version is not None and lexhint_version != expected_version:
        raise ContractError(
            f"Lexhint version mismatch: expected {expected_version!r}, got {lexhint_version!r}"
        )
    schema_version = str(SCHEMA_VERSION).strip()
    if not schema_version:
        raise ContractError("Lexhint SCHEMA_VERSION is empty")

    public_source_variants = tuple(getattr(lexhint, "SOURCE_VARIANTS", SOURCE_VARIANTS))
    if public_source_variants != SOURCE_VARIANTS:
        raise ContractError(
            f"source variants mismatch: datasets.toml {SOURCE_VARIANTS}; "
            f"lexhint {_format_values(public_source_variants)}"
        )
    required_provenance_parameters = {
        "source_variant",
        "source_edition",
        "source_metadata_language",
    }
    build_parameters = inspect.signature(build_dictionary).parameters
    missing_parameters = required_provenance_parameters - set(build_parameters)
    if missing_parameters:
        raise ContractError(
            "Lexhint builder provenance contract is missing: "
            + ", ".join(sorted(missing_parameters))
        )
    public_variant_names = tuple(DATASET_VARIANT_NAMES)
    configured_variant_names = tuple(config.variants)
    if configured_variant_names != public_variant_names:
        raise ContractError(
            "dataset variant names mismatch: "
            f"datasets.toml {_format_values(configured_variant_names)}; "
            f"lexhint {_format_values(public_variant_names)}"
        )
    if config.default_variant != DEFAULT_DATASET_VARIANT:
        raise ContractError(
            "default dataset variant mismatch: "
            f"datasets.toml {config.default_variant!r}; "
            f"lexhint {DEFAULT_DATASET_VARIANT!r}"
        )

    for name in public_variant_names:
        configured = config.variants[name].capabilities
        public = tuple(DATASET_VARIANTS[name].capabilities)
        if configured != public:
            raise ContractError(
                f"configured variant {name!r} capabilities mismatch: "
                f"datasets.toml {configured}; lexhint {public}"
            )

    public_languages = tuple(supported_base_languages())
    configured_languages = tuple(config.languages)
    if configured_languages != public_languages:
        raise ContractError(
            "supported base languages mismatch: "
            f"datasets.toml {_format_values(configured_languages)}; "
            f"lexhint {_format_values(public_languages)}"
        )
    enabled_languages = tuple(language.code for language in config.enabled_languages)
    if enabled_languages != public_languages:
        raise ContractError(
            "enabled base languages mismatch: "
            f"datasets.toml {_format_values(enabled_languages)}; "
            f"lexhint {_format_values(public_languages)}"
        )

    result: dict[str, Any] = {
        "lexhint_version": lexhint_version,
        "schema_version": schema_version,
        "variants": {
            name: list(config.variants[name].capabilities)
            for name in public_variant_names
        },
        "default_variant": DEFAULT_DATASET_VARIANT,
        "base_languages": list(public_languages),
        "source_variants": list(SOURCE_VARIANTS),
    }
    if lexhint_commit:
        result["lexhint_commit"] = lexhint_commit
    return result


def _print_result(result: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    print("Lexhint dataset contract OK")
    print(f"  Lexhint version       {result['lexhint_version']}")
    if result.get("lexhint_commit"):
        print(f"  Lexhint commit        {result['lexhint_commit']}")
    print(f"  SQLite schema         {result['schema_version']}")
    print(f"  variants              {', '.join(result['variants'])}")
    print(f"  default               {result['default_variant']}")
    print(f"  base languages        {', '.join(result['base_languages'])}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the installed Lexhint dataset contract."
    )
    parser.add_argument("--config", type=Path)
    parser.add_argument("--expected-version")
    parser.add_argument("--lexhint-commit")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = verify_contract(
            load_config(args.config),
            lexhint_commit=args.lexhint_commit,
            expected_version=args.expected_version,
        )
    except (ContractError, OSError, TypeError, ValueError) as exc:
        print(f"Lexhint dataset contract mismatch: {exc}", file=sys.stderr)
        return 1
    _print_result(result, as_json=args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
