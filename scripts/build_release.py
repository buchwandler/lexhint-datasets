#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

from scripts.config import DatasetConfig, VariantConfig, load_config
from scripts.split_source import split_source


class BuildError(RuntimeError):
    """The configured dataset build could not be completed."""


def _values(value: str | Iterable[str] | None) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return tuple(item.strip() for item in value.split(",") if item.strip())
    return tuple(item.strip() for item in value if item.strip())


def maximal_variant(config: DatasetConfig, selected_variants: tuple[str, ...]) -> str:
    specs = [config.variant(name) for name in selected_variants]
    maximal = [
        spec
        for spec in specs
        if all(set(other.capabilities).issubset(spec.capabilities) for other in specs)
    ]
    if len(maximal) != 1:
        raise BuildError(
            "selected dataset variants do not have one unique maximal "
            "capability artifact"
        )
    return maximal[0].name


def _build_variant_command(
    variant: VariantConfig,
    *,
    lexhint_command: str,
    language: str,
    source: Path,
    output: Path,
    no_frequency: bool,
) -> list[str]:
    command = [
        lexhint_command,
        "dictionary",
        "build",
        language,
        "--source",
        str(source),
        "--output",
        str(output),
    ]
    if variant.profile:
        command += ["--profile", variant.profile]
    else:
        command += ["--capabilities", ",".join(variant.capabilities)]
    if no_frequency:
        command.append("--no-frequency")
    return command


def resolve_selection(
    config: DatasetConfig,
    *,
    language: str | Iterable[str] | None,
    variants: str | Iterable[str] | None = None,
) -> tuple[str, tuple[str, ...]]:
    selected_languages = _values(language)
    selected_variants = _values(variants) or config.default_release_variants
    if len(selected_languages) != 1:
        raise BuildError("exactly one language is required")
    selected_language = selected_languages[0]
    if selected_language not in config.languages:
        raise BuildError(f"unknown language: {selected_language!r}")
    if not config.languages[selected_language].enabled:
        raise BuildError(f"disabled language requested: {selected_language!r}")
    unknown_variants = sorted(set(selected_variants) - set(config.variants))
    if unknown_variants:
        raise BuildError(f"unknown variants: {unknown_variants}")
    if not selected_variants:
        raise BuildError("at least one variant is required")
    return selected_language, selected_variants


def _run(command: list[str]) -> None:
    try:
        subprocess.run(command, check=True)
    except OSError as exc:
        raise BuildError(f"could not execute {command[0]!r}: {exc}") from exc
    except subprocess.CalledProcessError as exc:
        raise BuildError(
            f"build command failed with exit code {exc.returncode}: {command}"
        ) from exc


def build_release(
    source: str | Path,
    build_dir: str | Path,
    *,
    language: str | Iterable[str],
    config: DatasetConfig | None = None,
    variants: str | Iterable[str] | None = None,
    upstream_sha256: str | None = None,
    lexhint_commit: str | None = None,
    lexhint_command: str = "lexhint",
    no_frequency: bool = False,
) -> dict[str, object]:
    from scripts.verify_lexhint_contract import verify_contract

    config = config or load_config()
    contract = verify_contract(config, lexhint_commit=lexhint_commit)
    selected_language, selected_variants = resolve_selection(
        config, language=language, variants=variants
    )
    root = Path(build_dir)
    source_dir = root / "source"
    split_dir = source_dir / "by-language"
    work_dir = root / "work"
    root.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    (root / "lexhint-contract.json").write_text(
        json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    split_manifest = split_source(
        source,
        split_dir,
        (selected_language,),
        upstream_sha256=upstream_sha256,
        manifest_path=source_dir / "source-splits-v1.json",
        wiktionary_edition=config.source_for(selected_language).edition,
    )
    source_variant_name = maximal_variant(config, selected_variants)
    source_variant = config.variant(source_variant_name)
    for build_language in (selected_language,):
        source_path = work_dir / f"{build_language}.{source_variant_name}.sqlite3"
        _run(
            _build_variant_command(
                source_variant,
                lexhint_command=lexhint_command,
                language=build_language,
                source=split_dir / f"{build_language}.jsonl.gz",
                output=source_path,
                no_frequency=no_frequency,
            )
        )
        for variant_name in selected_variants:
            variant = config.variant(variant_name)
            output = root / f"{build_language}-{variant_name}.sqlite3"
            if variant_name == source_variant_name:
                shutil.copy2(source_path, output)
            elif variant.profile:
                _run(
                    [
                        lexhint_command,
                        "dictionary",
                        "project",
                        str(source_path),
                        "--output",
                        str(output),
                        "--profile",
                        variant.profile,
                    ]
                )
            else:
                _run(
                    [
                        lexhint_command,
                        "dictionary",
                        "project",
                        str(source_path),
                        "--output",
                        str(output),
                        "--capabilities",
                        ",".join(variant.capabilities),
                    ]
                )
    selection = {
        "languages": [selected_language],
        "language_kind": "base",
        "variants": list(selected_variants),
        "source_splits": str(source_dir / "source-splits-v1.json"),
        "lexhint": contract,
    }
    (root / "selection.json").write_text(
        json.dumps(selection, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {
        "selection": selection,
        "source_splits": split_manifest,
        "lexhint": contract,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build configured Lexhint base-language dataset artifacts."
    )
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    parser.add_argument(
        "--language", required=True, help="configured base/build language"
    )
    parser.add_argument(
        "--variants", help="comma-separated configured dataset variants"
    )
    parser.add_argument("--upstream-sha256")
    parser.add_argument("--lexhint-command", default="lexhint")
    parser.add_argument("--lexhint-commit")
    parser.add_argument("--no-frequency", action="store_true")
    args = parser.parse_args()
    from scripts.verify_lexhint_contract import ContractError

    try:
        result = build_release(
            args.source,
            args.build_dir,
            config=load_config(args.config),
            language=args.language,
            variants=args.variants,
            upstream_sha256=args.upstream_sha256,
            lexhint_commit=args.lexhint_commit,
            lexhint_command=args.lexhint_command,
            no_frequency=args.no_frequency,
        )
    except (BuildError, ContractError, OSError, ValueError) as exc:
        print(f"build failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
