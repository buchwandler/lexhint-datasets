#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from collections.abc import Iterable

from scripts.config import DatasetConfig, load_config
from scripts.split_source import split_source


class BuildError(RuntimeError):
    """The configured dataset build could not be completed."""


def _values(value: str | Iterable[str] | None) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return tuple(item.strip() for item in value.split(",") if item.strip())
    return tuple(item.strip() for item in value if item.strip())


def resolve_selection(
    config: DatasetConfig,
    *,
    languages: str | Iterable[str] | None = None,
    variants: str | Iterable[str] | None = None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    selected_languages = _values(languages) or tuple(
        language.code for language in config.enabled_languages
    )
    selected_variants = _values(variants) or tuple(config.variants)
    unknown_languages = sorted(set(selected_languages) - set(config.languages))
    disabled_languages = sorted(
        language
        for language in selected_languages
        if language in config.languages and not config.languages[language].enabled
    )
    unknown_variants = sorted(set(selected_variants) - set(config.variants))
    if unknown_languages:
        raise BuildError(f"unknown languages: {unknown_languages}")
    if disabled_languages:
        raise BuildError(f"disabled languages requested: {disabled_languages}")
    if unknown_variants:
        raise BuildError(f"unknown variants: {unknown_variants}")
    if not selected_languages or not selected_variants:
        raise BuildError("at least one language and variant are required")
    return selected_languages, selected_variants


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
    config: DatasetConfig | None = None,
    languages: str | Iterable[str] | None = None,
    variants: str | Iterable[str] | None = None,
    upstream_sha256: str | None = None,
    lexhint_command: str = "lexhint",
    no_frequency: bool = False,
) -> dict[str, object]:
    config = config or load_config()
    selected_languages, selected_variants = resolve_selection(
        config, languages=languages, variants=variants
    )
    root = Path(build_dir)
    source_dir = root / "source"
    split_dir = source_dir / "by-language"
    work_dir = root / "work"
    root.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    split_manifest = split_source(
        source,
        split_dir,
        selected_languages,
        upstream_sha256=upstream_sha256,
        manifest_path=source_dir / "source-splits-v1.json",
    )
    for language in selected_languages:
        rich_config = config.variant("rich") if "rich" in config.variants else None
        if rich_config is None or rich_config.profile is None:
            raise BuildError("a rich variant with a build profile is required")
        rich_path = work_dir / f"{language}.rich.sqlite3"
        build_command = [
            lexhint_command,
            "dictionary",
            "build",
            language,
            "--source",
            str(split_dir / f"{language}.jsonl.gz"),
            "--output",
            str(rich_path),
            "--profile",
            rich_config.profile,
        ]
        if no_frequency:
            build_command.append("--no-frequency")
        _run(build_command)
        for variant_name in selected_variants:
            variant = config.variant(variant_name)
            output = root / f"{language}-{variant_name}.sqlite3"
            if variant_name == "rich":
                shutil.copy2(rich_path, output)
            elif variant.profile:
                _run(
                    [
                        lexhint_command,
                        "dictionary",
                        "project",
                        str(rich_path),
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
                        str(rich_path),
                        "--output",
                        str(output),
                        "--capabilities",
                        ",".join(variant.capabilities),
                    ]
                )
    selection = {
        "languages": list(selected_languages),
        "variants": list(selected_variants),
        "source_splits": str(source_dir / "source-splits-v1.json"),
    }
    (root / "selection.json").write_text(
        json.dumps(selection, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {"selection": selection, "source_splits": split_manifest}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build configured Lexhint dataset artifacts."
    )
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--languages")
    parser.add_argument("--variants")
    parser.add_argument("--upstream-sha256")
    parser.add_argument("--lexhint-command", default="lexhint")
    parser.add_argument("--no-frequency", action="store_true")
    args = parser.parse_args()
    try:
        result = build_release(
            args.source,
            args.build_dir,
            config=load_config(args.config),
            languages=args.languages,
            variants=args.variants,
            upstream_sha256=args.upstream_sha256,
            lexhint_command=args.lexhint_command,
            no_frequency=args.no_frequency,
        )
    except (BuildError, OSError, ValueError) as exc:
        print(f"build failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
