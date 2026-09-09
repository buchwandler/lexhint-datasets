#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import shutil
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lexhint import SCHEMA_VERSION, Lexicon, __version__
from lexhint.status import read_artifact_status

from scripts.config import SOURCE_VARIANTS, DatasetConfig, load_config
from scripts.validate import ValidationError, validate

_ARTIFACT_NAME = re.compile(
    r"(?P<language>[a-z]{2,3})-(?:(?P<source_variant>native|english)-)?"
    r"(?P<variant>[a-z0-9_-]+)\.sqlite3$"
)
_ASSET_NAME = re.compile(
    r"lexhint-(?P<language>[a-z]{2,3})-(?:(?P<source_variant>native|english)-)?"
    r"(?P<variant>[a-z0-9_-]+)-s(?P<schema>[0-9]+)-(?P<version>[^/]+)\.sqlite3\.gz$"
)
MAX_RELEASE_ASSET_BYTES = 2 * 1024**3


class PackagingError(RuntimeError):
    """The release candidate violates the dataset packaging contract."""


@dataclass(frozen=True, slots=True)
class ArtifactInput:
    path: Path
    language: str
    source_variant: str
    variant: str


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def gzip_copy(source: Path, target: Path, *, member_name: str | None = None) -> None:
    with (
        source.open("rb") as src,
        target.open("wb") as raw,
        gzip.GzipFile(
            filename=member_name or target.name,
            mode="wb",
            fileobj=raw,
            compresslevel=9,
            mtime=0,
        ) as dst,
    ):
        shutil.copyfileobj(src, dst, length=1024 * 1024)


def _metadata_for(lexicon: Lexicon) -> dict[str, Any]:
    return dict(lexicon.metadata)


def package_artifact(
    database: str | Path,
    *,
    language: str,
    variant: str,
    dataset_version: str,
    output_dir: str | Path,
    source_variant: str = "native",
    config: DatasetConfig | None = None,
    build_source: dict[str, Any] | None = None,
    expected_schema: str | None = None,
) -> dict[str, Any]:
    path = Path(database)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    config = config or load_config()
    variant_config = config.variant(variant)
    if source_variant not in SOURCE_VARIANTS:
        raise PackagingError(f"unknown source variant: {source_variant!r}")
    required_schema = str(expected_schema or SCHEMA_VERSION).strip()
    if not required_schema:
        raise PackagingError("expected Lexhint schema is empty")
    try:
        validate(
            path,
            language=language,
            variant=variant,
            expected_capabilities=variant_config.capabilities,
            expected_schema=required_schema,
            probe_word="",
        )
    except (ValidationError, OSError, ValueError) as exc:
        raise PackagingError(
            f"cannot package {language}/{source_variant}/{variant}: {exc}"
        ) from exc
    lexicon = Lexicon.from_path(path, language=language)
    status = read_artifact_status(path=path)
    embedded_source_variant = status.provenance.get("dictionary_source_variant")
    if embedded_source_variant and embedded_source_variant != source_variant:
        raise PackagingError(
            f"embedded source variant mismatch: expected {source_variant!r}, got {embedded_source_variant!r}"
        )
    if embedded_source_variant:
        expected_source = config.source_for(language, source_variant)
        for field, expected in (
            ("dictionary_source_edition", expected_source.wiktionary_edition),
            ("dictionary_metadata_language", expected_source.metadata_language),
        ):
            if status.provenance.get(field) != expected:
                raise PackagingError(
                    f"embedded provenance mismatch for {field}: expected {expected!r}, "
                    f"got {status.provenance.get(field)!r}"
                )
    schema_version = str(status.schema_version).strip()
    if not schema_version:
        raise PackagingError(
            f"database schema metadata is missing: {language}/{variant}"
        )
    if schema_version != required_schema:
        raise PackagingError(
            f"artifact schema mismatch for {language}/{variant}: expected {required_schema!r}, got {schema_version!r}"
        )
    asset_name = f"lexhint-{language}-{source_variant}-{variant}-s{schema_version}-{dataset_version}.sqlite3.gz"
    asset_path = output / asset_name
    gzip_copy(path, asset_path, member_name=asset_name)
    compressed_size = asset_path.stat().st_size
    if compressed_size >= MAX_RELEASE_ASSET_BYTES:
        raise PackagingError(f"{asset_name} reaches the GitHub Release asset limit")
    metadata = _metadata_for(lexicon)
    source_keys = {
        "built_at",
        "builder_version",
        "dictionary_source",
        "dictionary_source_sha256",
        "dictionary_source_url",
        "dictionary_source_format",
        "dictionary_source_contract",
        "dictionary_source_variant",
        "dictionary_source_edition",
        "dictionary_metadata_language",
        "source",
        "source_sha256",
        "frequency_source",
        "frequency_corpus",
        "frequency_source_revision",
        "frequency_source_sha256",
    }
    artifact_metadata = {key: metadata[key] for key in source_keys if key in metadata}
    artifact_metadata.setdefault("dictionary_source_variant", source_variant)
    record: dict[str, Any] = {
        "id": f"{language}/{source_variant}/{variant}",
        "language": language,
        "source_variant": source_variant,
        "variant": variant,
        "profile": status.profile,
        "capabilities": list(status.capabilities),
        "coverage": status.coverage,
        "schema_version": schema_version,
        "format": "sqlite3-gzip",
        "asset": asset_name,
        "sha256": sha256(asset_path),
        "compressed_size": compressed_size,
        "uncompressed_size": path.stat().st_size,
        "counts": status.counts,
        "frequency": status.frequency,
        "artifact_metadata": artifact_metadata,
    }
    if build_source is not None:
        record["build_source"] = build_source
    return record


def _artifact_input(path: Path, config: DatasetConfig) -> ArtifactInput:
    match = _ARTIFACT_NAME.fullmatch(path.name)
    if match is None:
        raise PackagingError(
            f"cannot infer language, source variant, and variant from {path.name!r}; "
            "expected <language>-<source_variant>-<variant>.sqlite3"
        )
    language = match.group("language")
    source_variant = match.group("source_variant") or "native"
    variant = match.group("variant")
    if language not in config.languages:
        raise PackagingError(f"language {language!r} is not configured")
    if source_variant not in config.source_variants_for(language):
        raise PackagingError(
            f"source variant {source_variant!r} is not configured for {language!r}"
        )
    if variant not in config.variants:
        raise PackagingError(f"variant {variant!r} is not configured")
    return ArtifactInput(path, language, source_variant, variant)


def discover_artifacts(
    build_dir: str | Path, *, config: DatasetConfig | None = None
) -> list[ArtifactInput]:
    config = config or load_config()
    directory = Path(build_dir)
    paths = (
        path
        for path in directory.rglob("*.sqlite3")
        if _ARTIFACT_NAME.fullmatch(path.name) is not None
        and "work" not in path.relative_to(directory).parts
    )
    return sorted(
        (_artifact_input(path, config) for path in paths),
        key=lambda item: (
            item.language,
            item.source_variant,
            item.variant,
            str(item.path),
        ),
    )


def _check_release_invariants(
    records: list[dict[str, Any]],
    *,
    config: DatasetConfig,
    lexhint_commit: str,
    lexhint_version: str,
    expected_schema: str,
    source_sha256: str | None,
    expected_languages: Iterable[str] | None = None,
    expected_source_variant: str | None = None,
    expected_variants: Iterable[str] | None = None,
) -> None:
    slots: set[tuple[str, str, str, str]] = set()
    languages: set[str] = set()
    source_variants: set[str] = set()
    schemas: set[str] = set()
    for record in records:
        language = str(record.get("language", ""))
        source_variant = str(record.get("source_variant", "native"))
        variant_name = str(record.get("variant", ""))
        schema = str(record.get("schema_version", "")).strip()
        if language not in config.languages or not config.languages[language].enabled:
            raise PackagingError(
                f"language is not configured and enabled: {language!r}"
            )
        if source_variant not in config.source_variants_for(language):
            raise PackagingError(
                f"source variant is not configured for {language!r}: {source_variant!r}"
            )
        expected_id = f"{language}/{source_variant}/{variant_name}"
        if record.get("id") != expected_id:
            raise PackagingError(f"artifact id mismatch: expected {expected_id!r}")
        asset = str(record.get("asset", ""))
        asset_match = _ASSET_NAME.fullmatch(asset)
        if source_variant not in SOURCE_VARIANTS:
            raise PackagingError(f"unknown artifact source variant: {source_variant}")
        if not schema:
            raise PackagingError(
                f"artifact schema is missing: {language}/{variant_name}"
            )
        if schema != expected_schema:
            raise PackagingError(
                f"artifact schema mismatch for {language}/{variant_name}"
            )
        if asset_match is None or (
            asset_match.group("language") != language
            or (asset_match.group("source_variant") or "native") != source_variant
            or asset_match.group("variant") != variant_name
            or asset_match.group("schema") != schema
        ):
            raise PackagingError(
                f"artifact filename schema mismatch for {language}/{source_variant}/{variant_name}"
            )
        slot = (language, source_variant, variant_name, schema)
        if slot in slots:
            raise PackagingError(
                f"duplicate artifact slot: {'/'.join(slot[:3])}/s{slot[3]}"
            )
        slots.add(slot)
        languages.add(language)
        source_variants.add(source_variant)
        schemas.add(schema)
        variant = config.variant(variant_name)
        if tuple(record["capabilities"]) != variant.capabilities:
            raise PackagingError(f"capability mismatch for {language}/{variant_name}")
        if record["coverage"] != "full":
            raise PackagingError(
                f"artifact is not full coverage: {language}/{variant_name}"
            )
        if not record["sha256"]:
            raise PackagingError(
                f"artifact checksum is missing: {language}/{variant_name}"
            )
        embedded_variant = record.get("artifact_metadata", {}).get(
            "dictionary_source_variant"
        )
        if embedded_variant and embedded_variant != source_variant:
            raise PackagingError(
                f"embedded source variant mismatch for {language}/{variant_name}"
            )
        embedded_hash = record.get("artifact_metadata", {}).get(
            "dictionary_source_sha256"
        ) or record.get("artifact_metadata", {}).get("source_sha256")
        build_source = record.get("build_source") or {}
        upstream_hash = build_source.get("upstream_sha256")
        build_hash = build_source.get("sha256")
        if source_sha256 and upstream_hash and upstream_hash != source_sha256:
            raise PackagingError(
                f"upstream source checksum mismatch for {language}/{variant_name}"
            )
        if embedded_hash:
            expected_artifact_hash = build_hash or source_sha256
            if expected_artifact_hash and embedded_hash != expected_artifact_hash:
                raise PackagingError(
                    f"build source checksum mismatch for {language}/{variant_name}"
                )
    if len(schemas) > 1:
        raise PackagingError(
            f"artifacts use incompatible schema versions: {sorted(schemas)}"
        )
    if len(languages) != 1:
        raise PackagingError(
            f"new releases must contain exactly one language, got {sorted(languages)}"
        )
    if len(source_variants) != 1:
        raise PackagingError(
            f"new releases must contain exactly one source variant, got {sorted(source_variants)}"
        )
    if expected_languages is not None and languages != {
        str(item) for item in expected_languages
    }:
        raise PackagingError(
            f"release language mismatch: expected {sorted(set(expected_languages))}, got {sorted(languages)}"
        )
    if expected_source_variant is not None and source_variants != {
        expected_source_variant
    }:
        raise PackagingError(
            f"release source variant mismatch: expected {expected_source_variant!r}, got {sorted(source_variants)}"
        )
    actual_variants = {str(record.get("variant", "")) for record in records}
    if expected_variants is not None and actual_variants != {
        str(item) for item in expected_variants
    }:
        raise PackagingError(
            f"release variants mismatch: expected {sorted(set(expected_variants))}, got {sorted(actual_variants)}"
        )
    if not lexhint_commit or not lexhint_version or not expected_schema:
        raise PackagingError("Lexhint commit, version, and schema version are required")


def _source_record(
    *,
    source_variant: str,
    source_url: str,
    source_label: str,
    source_edition: str | None,
    source_metadata_language: str | None,
    source_page_url: str | None,
    source_sha256: str | None,
    publish: bool,
    config: DatasetConfig,
) -> dict[str, str | None]:
    if source_variant not in SOURCE_VARIANTS:
        raise PackagingError(f"unknown source variant: {source_variant!r}")
    if publish and config.source_policy.require_sha256_on_publish and not source_sha256:
        raise PackagingError("source_sha256 is required for a published release")
    return {
        "source_variant": source_variant,
        "url": source_url,
        "label": source_label,
        "wiktionary_edition": source_edition,
        "metadata_language": source_metadata_language,
        "page_url": source_page_url,
        "sha256": source_sha256,
    }


def _release_notes(manifest: dict[str, Any]) -> str:
    variants = {
        record["variant"]: tuple(record["capabilities"])
        for record in manifest["artifacts"]
    }
    source = manifest["source"]
    lines = [
        f"# Lexhint datasets {manifest['dataset_version']}",
        "",
        f"Built with Lexhint `{manifest['lexhint']['version']}` from `{manifest['lexhint']['ref']}` at commit `{manifest['lexhint']['commit']}`.",
        "",
        f"SQLite schema: {manifest['lexhint']['schema_version']}",
        "",
        f"Language: {manifest['language']}",
        f"Source variant: {source.get('source_variant')}",
        f"Wiktionary edition: {source.get('wiktionary_edition') or 'not supplied'}",
        f"Metadata/gloss language: {source.get('metadata_language') or 'not supplied'}",
        f"Kaikki dictionary page: {source.get('page_url') or 'not supplied'}",
        f"Raw source: {source['url']}",
        f"Source SHA-256: {source['sha256'] or 'not supplied'}",
        "",
        "Variants:",
        *(
            f"- {name}: {', '.join(capabilities)}"
            for name, capabilities in sorted(variants.items())
        ),
        "",
        "See `datasets-v2.json`, `SHA256SUMS`, and `ATTRIBUTION.md` for release details.",
        "",
    ]
    return "\n".join(lines)


def package_release(
    records: Iterable[dict[str, Any]],
    *,
    output_dir: str | Path,
    dataset_version: str,
    lexhint_ref: str,
    lexhint_commit: str,
    lexhint_version: str | None = None,
    expected_schema: str | None = None,
    contract: dict[str, Any] | None = None,
    source_variant: str = "native",
    source_url: str,
    source_label: str,
    source_edition: str | None = None,
    source_metadata_language: str | None = None,
    source_page_url: str | None = None,
    source_sha256: str | None = None,
    attribution: str | Path | None = None,
    publish: bool = False,
    config: DatasetConfig | None = None,
    builder_repository: dict[str, str] | None = None,
    expected_languages: Iterable[str] | None = None,
    expected_source_variant: str | None = None,
    expected_variants: Iterable[str] | None = None,
    source_splits: dict[str, Any] | None = None,
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    config = config or load_config()
    required_schema = str(expected_schema or SCHEMA_VERSION).strip()
    required_version = str(lexhint_version or __version__).strip()
    if contract is not None:
        if str(contract.get("schema_version", "")) != required_schema:
            raise PackagingError("contract schema does not match package schema")
        if str(contract.get("lexhint_version", "")) != required_version:
            raise PackagingError(
                "contract Lexhint version does not match package metadata"
            )
        if (
            contract.get("lexhint_commit")
            and contract["lexhint_commit"] != lexhint_commit
        ):
            raise PackagingError(
                "contract Lexhint commit does not match package metadata"
            )
    artifact_records = sorted(records, key=lambda record: record["id"])
    if not artifact_records:
        raise PackagingError("release contains no artifacts")
    _check_release_invariants(
        artifact_records,
        config=config,
        lexhint_commit=lexhint_commit,
        lexhint_version=required_version,
        expected_schema=required_schema,
        source_sha256=source_sha256,
        expected_languages=expected_languages,
        expected_source_variant=expected_source_variant or source_variant,
        expected_variants=expected_variants,
    )
    release_language = next(iter({record["language"] for record in artifact_records}))
    manifest: dict[str, Any] = {
        "manifest_version": 2,
        "language": release_language,
        "source_variant": source_variant,
        "dataset_version": dataset_version,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "lexhint": {
            "ref": lexhint_ref,
            "version": required_version,
            "commit": lexhint_commit,
            "schema_version": required_schema,
        },
        "source": _source_record(
            source_variant=source_variant,
            source_url=source_url,
            source_label=source_label,
            source_edition=source_edition,
            source_metadata_language=source_metadata_language,
            source_page_url=source_page_url,
            source_sha256=source_sha256,
            publish=publish,
            config=config,
        ),
        "artifacts": artifact_records,
    }
    if builder_repository is not None:
        manifest["builder_repository"] = builder_repository
    if source_splits is not None:
        manifest["build_sources"] = source_splits
    if contract is not None:
        manifest["lexhint_contract"] = contract
    (output / "datasets-v2.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "SHA256SUMS").write_text(
        "\n".join(
            f"{record['sha256']}  {record['asset']}" for record in artifact_records
        )
        + "\n",
        encoding="utf-8",
    )
    if attribution is not None:
        source = Path(attribution)
        if not source.is_file():
            raise PackagingError(f"attribution file not found: {source}")
        shutil.copy2(source, output / "ATTRIBUTION.md")
    (output / "release-notes.md").write_text(_release_notes(manifest), encoding="utf-8")
    if contract is not None:
        (output / "lexhint-contract.json").write_text(
            json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Package a multi-artifact Lexhint release."
    )
    parser.add_argument("--build-dir", type=Path)
    parser.add_argument(
        "--artifact", action="append", metavar="LANGUAGE/SOURCE_VARIANT/VARIANT=PATH"
    )
    parser.add_argument("--output-dir", type=Path, default=Path("dist"))
    parser.add_argument("--config", type=Path)
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--lexhint-ref", required=True)
    parser.add_argument("--lexhint-version")
    parser.add_argument("--lexhint-commit", required=True)
    parser.add_argument("--expected-schema")
    parser.add_argument("--builder-repository")
    parser.add_argument("--source-variant", choices=SOURCE_VARIANTS, default="native")
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--source-label", required=True)
    parser.add_argument("--source-edition")
    parser.add_argument("--source-metadata-language")
    parser.add_argument("--source-page-url")
    parser.add_argument("--source-sha256")
    parser.add_argument("--source-splits", type=Path)
    parser.add_argument("--contract", type=Path)
    parser.add_argument("--expected-language", action="append")
    parser.add_argument("--expected-source-variant", choices=SOURCE_VARIANTS)
    parser.add_argument("--expected-variant", action="append")
    parser.add_argument("--attribution", type=Path, default=Path("DATA_SOURCES.md"))
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    config = load_config(args.config)
    try:
        inputs: list[ArtifactInput] = []
        if args.build_dir:
            inputs.extend(discover_artifacts(args.build_dir, config=config))
        for value in args.artifact or ():
            try:
                slot, raw_path = value.split("=", 1)
                fields = slot.split("/")
                if len(fields) == 2:
                    language, variant = fields
                    source_variant = "native"
                elif len(fields) == 3:
                    language, source_variant, variant = fields
                else:
                    raise ValueError
            except ValueError as exc:
                raise PackagingError(f"invalid --artifact value: {value!r}") from exc
            inputs.append(
                ArtifactInput(Path(raw_path), language, source_variant, variant)
            )
        split_data = (
            json.loads(args.source_splits.read_text(encoding="utf-8"))
            if args.source_splits
            else None
        )
        contract = (
            json.loads(args.contract.read_text(encoding="utf-8"))
            if args.contract
            else None
        )
        builder_repository = None
        if args.builder_repository:
            import os

            builder_repository = {
                "repository": args.builder_repository,
                "commit": os.environ.get("GITHUB_SHA", ""),
            }
        records = [
            package_artifact(
                item.path,
                language=item.language,
                source_variant=item.source_variant,
                variant=item.variant,
                dataset_version=args.dataset_version,
                output_dir=args.output_dir,
                config=config,
                expected_schema=args.expected_schema,
                build_source=(
                    split_data.get("splits", {}).get(item.language)
                    if split_data
                    else None
                ),
            )
            for item in inputs
        ]
        manifest = package_release(
            records,
            output_dir=args.output_dir,
            dataset_version=args.dataset_version,
            lexhint_ref=args.lexhint_ref,
            lexhint_commit=args.lexhint_commit,
            lexhint_version=args.lexhint_version,
            expected_schema=args.expected_schema,
            contract=contract,
            source_variant=args.source_variant,
            source_url=args.source_url,
            source_label=args.source_label,
            source_edition=args.source_edition,
            source_metadata_language=args.source_metadata_language,
            source_page_url=args.source_page_url,
            source_sha256=args.source_sha256,
            attribution=args.attribution,
            publish=args.publish,
            config=config,
            builder_repository=builder_repository,
            expected_languages=args.expected_language,
            expected_source_variant=args.expected_source_variant,
            expected_variants=args.expected_variant,
            source_splits=split_data,
        )
    except (
        PackagingError,
        ValidationError,
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        print(f"packaging failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
