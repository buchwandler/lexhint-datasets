#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from typing import Any, cast

from lexhint import SCHEMA_VERSION, Lexicon
from lexhint.lexicon import LexiconCapabilityError
from lexhint.status import read_artifact_status

from scripts.config import CAPABILITY_ORDER, load_config


class ValidationError(RuntimeError):
    """The artifact does not satisfy the configured release contract."""


def _canonical_capabilities(
    values: str | tuple[str, ...] | None,
) -> tuple[str, ...] | None:
    if values is None:
        return None
    raw = values.split(",") if isinstance(values, str) else values
    unknown = set(raw) - set(CAPABILITY_ORDER)
    if unknown:
        raise ValidationError(f"unknown capability: {min(unknown)!r}")
    return tuple(capability for capability in CAPABILITY_ORDER if capability in raw)


def _quick_check(path: Path) -> None:
    uri = path.resolve().as_uri() + "?mode=ro"
    try:
        with closing(sqlite3.connect(uri, uri=True)) as connection:
            result = connection.execute("PRAGMA quick_check").fetchone()
    except sqlite3.DatabaseError as exc:
        raise ValidationError(f"SQLite database is unreadable: {exc}") from exc
    if result != ("ok",):
        raise ValidationError(f"PRAGMA quick_check failed: {result!r}")


def _read_schema_version(path: Path) -> str:
    uri = path.resolve().as_uri() + "?mode=ro"
    try:
        with closing(sqlite3.connect(uri, uri=True)) as connection:
            row = connection.execute(
                "SELECT value FROM metadata WHERE key = ?", ("schema_version",)
            ).fetchone()
    except sqlite3.DatabaseError as exc:
        raise ValidationError(f"SQLite schema metadata is unreadable: {exc}") from exc
    if row is None or not str(row[0]).strip():
        raise ValidationError("SQLite schema metadata is missing schema_version")
    return str(row[0]).strip()


def _check_count(
    counts: dict[str, int | None], name: str, minimum: int, *, capability: str
) -> None:
    actual = counts.get(name)
    if actual is None:
        if minimum:
            raise ValidationError(
                f"{name} count is unavailable because capability {capability!r} is absent"
            )
        return
    if actual < minimum:
        raise ValidationError(f"{name} count too small: {actual:,} < {minimum:,}")


def _check_capability_behavior(
    lexicon: Lexicon, capabilities: tuple[str, ...], probe: str
) -> None:
    if "semantic" in capabilities:
        lexicon.context_domains(probe, target=(0, len(probe)))
    else:
        try:
            lexicon.context_domains(probe, target=(0, len(probe)))
        except LexiconCapabilityError:
            pass
        else:
            raise ValidationError(
                "semantic operation succeeded without semantic capability"
            )

    if "dictionary" in capabilities:
        lexicon.entries(probe)
    else:
        try:
            lexicon.entries(probe)
        except LexiconCapabilityError:
            pass
        else:
            raise ValidationError(
                "dictionary operation succeeded without dictionary capability"
            )

    if "search" in capabilities:
        lexicon.suggest(probe, limit=1)
        if "dictionary" in capabilities:
            lexicon.search_definitions(probe, limit=1)
    else:
        try:
            lexicon.suggest(probe, limit=1)
        except LexiconCapabilityError:
            pass
        else:
            raise ValidationError(
                "search operation succeeded without search capability"
            )


def validate(
    path: Path,
    *,
    language: str | None = None,
    expected_schema: str | None = None,
    expected_capabilities: str | tuple[str, ...] | None = None,
    variant: str | None = None,
    probe_word: str | None = None,
    semantic_probe: str | None = None,
    dictionary_probe: str | None = None,
    min_lexemes: int = 0,
    min_semantic_rows: int = 0,
    min_entries: int = 0,
    min_senses: int = 0,
    min_frequency_lexemes: int = 0,
) -> dict[str, object]:
    if not path.is_file():
        raise ValidationError(f"database not found: {path}")
    if path.stat().st_size == 0:
        raise ValidationError(f"database is empty: {path}")

    _quick_check(path)
    actual_schema = _read_schema_version(path)
    required_schema = str(expected_schema or SCHEMA_VERSION).strip()
    if not required_schema:
        raise ValidationError("expected Lexhint schema is empty")
    if actual_schema != required_schema:
        raise ValidationError(
            f"schema mismatch: expected {required_schema!r}, got {actual_schema!r}"
        )
    try:
        lexicon = Lexicon.from_path(path, language=language)
        status = read_artifact_status(path=path)
    except Exception as exc:
        raise ValidationError(f"Lexhint compatibility check failed: {exc}") from exc

    if language is not None and status.language != language:
        raise ValidationError(
            f"metadata language mismatch: expected {language!r}, got {status.language!r}"
        )
    if status.coverage != "full":
        raise ValidationError(f"database is not full coverage: {status.coverage!r}")

    capabilities = _canonical_capabilities(expected_capabilities)
    if variant is not None and expected_capabilities is None:
        config = load_config()
        capabilities = config.variant(variant).capabilities
    if capabilities is not None and status.capabilities != capabilities:
        raise ValidationError(
            f"capabilities mismatch: expected {capabilities!r}, got {status.capabilities!r}"
        )
    if status.schema_version != actual_schema:
        raise ValidationError(
            "schema metadata mismatch: "
            f"SQLite metadata {actual_schema!r}; artifact status {status.schema_version!r}"
        )

    counts = status.counts
    _check_count(counts, "lexemes", min_lexemes, capability="lexical")
    _check_count(counts, "semantic_rows", min_semantic_rows, capability="semantic")
    _check_count(counts, "entries", min_entries, capability="dictionary")
    _check_count(counts, "senses", min_senses, capability="dictionary")
    _check_count(
        counts, "frequency_lexemes", min_frequency_lexemes, capability="lexical"
    )

    probe = probe_word or ""
    if probe_word and not lexicon.contains(probe_word):
        raise ValidationError(f"configured lexical probe is missing: {probe_word!r}")
    if semantic_probe:
        if "semantic" not in status.capabilities:
            raise ValidationError(
                "semantic probe configured for an artifact without semantic capability"
            )
        if not lexicon.context_domains(semantic_probe, target=(0, len(semantic_probe))):
            raise ValidationError(
                f"configured semantic probe returned no evidence: {semantic_probe!r}"
            )
    if dictionary_probe:
        if "dictionary" not in status.capabilities:
            raise ValidationError(
                "dictionary probe configured for an artifact without dictionary capability"
            )
        if not lexicon.entries(dictionary_probe):
            raise ValidationError(
                f"configured dictionary probe returned no evidence: {dictionary_probe!r}"
            )
    _check_capability_behavior(lexicon, status.capabilities, probe or "probe")

    result = status.as_dict()
    result["variant"] = variant
    return result


def _config_defaults(args: argparse.Namespace) -> dict[str, object]:
    config = load_config(args.config)
    language = args.language
    if language is None:
        raise ValidationError("--language is required")
    language_config = config.languages.get(language)
    if language_config is None:
        raise ValidationError(f"unsupported language: {language!r}")
    variant = args.variant or config.default_variant
    variant_config = config.variant(variant)
    validation = language_config.validation
    return {
        "language": language,
        "variant": variant,
        "expected_capabilities": args.expected_capabilities
        or variant_config.capabilities,
        "expected_schema": args.expected_schema or str(SCHEMA_VERSION),
        "probe_word": args.probe_word
        if args.probe_word is not None
        else validation.probe_word,
        "semantic_probe": (
            validation.semantic_probe
            if "semantic" in variant_config.capabilities
            else None
        )
        if args.semantic_probe is None
        else args.semantic_probe,
        "dictionary_probe": (
            validation.dictionary_probe
            if "dictionary" in variant_config.capabilities
            else None
        )
        if args.dictionary_probe is None
        else args.dictionary_probe,
        "min_lexemes": args.min_lexemes
        if args.min_lexemes is not None
        else validation.min_lexemes,
        "min_semantic_rows": (
            args.min_semantic_rows
            if args.min_semantic_rows is not None
            else validation.min_semantic_rows
        )
        if "semantic" in variant_config.capabilities
        else 0,
        "min_entries": (
            args.min_entries if args.min_entries is not None else validation.min_entries
        )
        if "dictionary" in variant_config.capabilities
        else 0,
        "min_senses": (
            args.min_senses if args.min_senses is not None else validation.min_senses
        )
        if "dictionary" in variant_config.capabilities
        else 0,
        "min_frequency_lexemes": (
            args.min_frequency_lexemes
            if args.min_frequency_lexemes is not None
            else validation.min_frequency_lexemes
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a Lexhint dataset artifact.")
    parser.add_argument("database", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--language", required=True)
    parser.add_argument("--variant")
    parser.add_argument("--expected-schema")
    parser.add_argument("--expected-capabilities")
    parser.add_argument("--probe-word")
    parser.add_argument("--semantic-probe")
    parser.add_argument("--dictionary-probe")
    parser.add_argument("--min-lexemes", type=int)
    parser.add_argument("--min-semantic-rows", type=int)
    parser.add_argument("--min-entries", type=int)
    parser.add_argument("--min-senses", type=int)
    parser.add_argument("--min-frequency-lexemes", type=int)
    args = parser.parse_args()

    try:
        result = validate(args.database, **cast(dict[str, Any], _config_defaults(args)))
    except (ValidationError, OSError, ValueError) as exc:
        print(f"validation failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
