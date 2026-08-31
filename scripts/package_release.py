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

from scripts.config import DatasetConfig, load_config
from scripts.validate import ValidationError, validate

_ARTIFACT_NAME = re.compile(
    r"(?P<language>[a-z]{2})-(?P<variant>[a-z0-9_-]+)\.sqlite3$"
)
_ASSET_NAME = re.compile(
    r"lexhint-(?P<language>[a-z]{2})-(?P<variant>[a-z0-9_-]+)"
    r"-s(?P<schema>[0-9]+)-(?P<version>[^/]+)\.sqlite3\.gz$"
)
MAX_RELEASE_ASSET_BYTES = 2 * 1024**3


class PackagingError(RuntimeError):
    """The release candidate violates the dataset packaging contract."""


@dataclass(frozen=True, slots=True)
class ArtifactInput:
    path: Path
    language: str
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
    config: DatasetConfig | None = None,
    build_source: dict[str, Any] | None = None,
    expected_schema: str | None = None,
) -> dict[str, Any]:
    path = Path(database)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    config = config or load_config()
    variant_config = config.variant(variant)
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
        raise PackagingError(f"cannot package {language}/{variant}: {exc}") from exc

    lexicon = Lexicon.from_path(path, language=language)
    status = read_artifact_status(path=path)
    schema_version = str(status.schema_version).strip()
    if not schema_version:
        raise PackagingError(
            f"database schema metadata is missing: {language}/{variant}"
        )
    if schema_version != required_schema:
        raise PackagingError(
            f"artifact schema mismatch for {language}/{variant}: "
            f"expected {required_schema!r}, got {schema_version!r}"
        )
    asset_name = (
        f"lexhint-{language}-{variant}-s{schema_version}-{dataset_version}.sqlite3.gz"
    )
    asset_path = output / asset_name
    gzip_copy(path, asset_path, member_name=asset_name)
    compressed_size = asset_path.stat().st_size
    if compressed_size >= MAX_RELEASE_ASSET_BYTES:
        raise PackagingError(
            f"{asset_name} is {compressed_size} bytes and exceeds the "
            f"{MAX_RELEASE_ASSET_BYTES} byte GitHub Release asset limit"
        )
    metadata = _metadata_for(lexicon)
    source_keys = {
        "built_at",
        "builder_version",
        "dictionary_source",
        "dictionary_source_sha256",
        "dictionary_source_url",
        "source",
        "source_sha256",
        "frequency_source",
        "frequency_corpus",
        "frequency_source_revision",
        "frequency_source_sha256",
    }
    artifact_metadata = {key: metadata[key] for key in source_keys if key in metadata}
    record: dict[str, Any] = {
        "id": f"{language}/{variant}",
        "language": language,
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
            f"cannot infer language and variant from {path.name!r}; "
            "expected <language>-<variant>.sqlite3"
        )
    language = match.group("language")
    variant = match.group("variant")
    if language not in config.languages:
        raise PackagingError(f"language {language!r} is not configured")
    if variant not in config.variants:
        raise PackagingError(f"variant {variant!r} is not configured")
    return ArtifactInput(path, language, variant)


def discover_artifacts(
    build_dir: str | Path, *, config: DatasetConfig | None = None
) -> list[ArtifactInput]:
    config = config or load_config()
    directory = Path(build_dir)
    paths = (
        path
        for path in directory.rglob("*.sqlite3")
        if _ARTIFACT_NAME.fullmatch(path.name) is not None
    )
    return sorted(
        (_artifact_input(path, config) for path in paths),
        key=lambda item: (item.language, item.variant, str(item.path)),
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
    expected_variants: Iterable[str] | None = None,
) -> None:
    slots: set[tuple[str, str, str]] = set()
    schemas: set[str] = set()
    for record in records:
        language = str(record.get("language", ""))
        variant_name = str(record.get("variant", ""))
        schema = str(record.get("schema_version", "")).strip()
        asset = str(record.get("asset", ""))
        asset_match = _ASSET_NAME.fullmatch(asset)
        if not schema:
            raise PackagingError(
                f"artifact schema is missing: {language}/{variant_name}"
            )
        if schema != expected_schema:
            raise PackagingError(
                f"artifact schema mismatch for {language}/{variant_name}: "
                f"expected {expected_schema!r}, got {schema!r}"
            )
        if asset_match is None or (
            asset_match.group("language") != language
            or asset_match.group("variant") != variant_name
            or asset_match.group("schema") != schema
        ):
            raise PackagingError(
                f"artifact filename schema mismatch for {language}/{variant_name}: {asset!r}"
            )
        slot = (language, variant_name, schema)
        if slot in slots:
            raise PackagingError(
                f"duplicate artifact slot: {slot[0]}/{slot[1]}/s{slot[2]}"
            )
        slots.add(slot)
        variant = config.variant(slot[1])
        if tuple(record["capabilities"]) != variant.capabilities:
            raise PackagingError(f"capability mismatch for {slot[0]}/{slot[1]}")
        if record["coverage"] != "full":
            raise PackagingError(f"artifact is not full coverage: {slot[0]}/{slot[1]}")
        if not record["sha256"]:
            raise PackagingError(f"artifact checksum is missing: {slot[0]}/{slot[1]}")
        schemas.add(schema)
        embedded_hash = record["artifact_metadata"].get(
            "dictionary_source_sha256"
        ) or record["artifact_metadata"].get("source_sha256")
        build_source = record.get("build_source") or {}
        upstream_hash = build_source.get("upstream_sha256")
        build_hash = build_source.get("sha256")
        if source_sha256 and upstream_hash and upstream_hash != source_sha256:
            raise PackagingError(
                f"upstream source checksum mismatch for {slot[0]}/{slot[1]}: "
                f"{upstream_hash} != {source_sha256}"
            )
        if embedded_hash:
            expected_artifact_hash = build_hash or source_sha256
            if expected_artifact_hash and embedded_hash != expected_artifact_hash:
                raise PackagingError(
                    f"build source checksum mismatch for {slot[0]}/{slot[1]}: "
                    f"{embedded_hash} != {expected_artifact_hash}"
                )
    if len(schemas) > 1:
        raise PackagingError(
            f"artifacts use incompatible schema versions: {sorted(schemas)}"
        )
    languages = {str(record.get("language", "")) for record in records}
    if len(languages) != 1:
        raise PackagingError(
            f"new releases must contain exactly one language, got {sorted(languages)}"
        )
    if expected_languages is not None and languages != {
        str(item) for item in expected_languages
    }:
        raise PackagingError(
            f"release language mismatch: expected {sorted(set(expected_languages))}, "
            f"got {sorted(languages)}"
        )
    variants = {str(record.get("variant", "")) for record in records}
    if expected_variants is not None and variants != {
        str(item) for item in expected_variants
    }:
        raise PackagingError(
            f"release variants mismatch: expected {sorted(set(expected_variants))}, "
            f"got {sorted(variants)}"
        )
    if not lexhint_commit:
        raise PackagingError("lexhint commit is required")
    if not lexhint_version:
        raise PackagingError("lexhint version is required")
    if not expected_schema:
        raise PackagingError("schema version is required")


def _source_record(
    *,
    source_url: str,
    source_label: str,
    source_edition: str | None,
    source_sha256: str | None,
    publish: bool,
    config: DatasetConfig,
) -> dict[str, str | None]:
    if publish and config.source_policy.require_sha256_on_publish and not source_sha256:
        raise PackagingError("source_sha256 is required for a published release")
    return {
        "url": source_url,
        "label": source_label,
        "wiktionary_edition": source_edition,
        "sha256": source_sha256,
    }


def _release_notes(manifest: dict[str, Any]) -> str:
    variants: dict[str, tuple[str, ...]] = {}
    for record in manifest["artifacts"]:
        variants[record["variant"]] = tuple(record["capabilities"])
    lines = [
        f"# Lexhint datasets {manifest['dataset_version']}",
        "",
        (
            f"Built with Lexhint `{manifest['lexhint']['version']}` "
            f"from `{manifest['lexhint']['ref']}` "
            f"at commit `{manifest['lexhint']['commit']}`."
        ),
        "",
        f"SQLite schema: {manifest['lexhint']['schema_version']}",
        "",
        f"These artifacts require Lexhint schema {manifest['lexhint']['schema_version']}.",
        "Clients using an older schema continue selecting the newest earlier compatible release.",
        "",
        "Language:",
        f"- {manifest['language']}",
        "",
        "Variants:",
        *(
            f"- {name}: {', '.join(capabilities)}"
            for name, capabilities in sorted(variants.items())
        ),
        "",
        "Source:",
        f"- Wiktionary edition: {manifest['source'].get('wiktionary_edition') or 'not supplied'}",
        f"- URL: {manifest['source']['url']}",
        f"- label: {manifest['source']['label']}",
        f"- SHA-256: {manifest['source']['sha256'] or 'not supplied'}",
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
    source_url: str,
    source_label: str,
    source_edition: str | None = None,
    source_sha256: str | None = None,
    attribution: str | Path | None = None,
    publish: bool = False,
    config: DatasetConfig | None = None,
    builder_repository: dict[str, str] | None = None,
    expected_languages: Iterable[str] | None = None,
    expected_variants: Iterable[str] | None = None,
    source_splits: dict[str, Any] | None = None,
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    config = config or load_config()
    required_schema = str(expected_schema or SCHEMA_VERSION).strip()
    required_version = str(lexhint_version or __version__).strip()
    if not required_schema:
        raise PackagingError("schema version is required")
    if not required_version:
        raise PackagingError("lexhint version is required")
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
        expected_variants=expected_variants,
    )
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    release_language = next(iter({record["language"] for record in artifact_records}))
    manifest: dict[str, Any] = {
        "manifest_version": 2,
        "language": release_language,
        "dataset_version": dataset_version,
        "generated_at": generated_at,
        "lexhint": {
            "ref": lexhint_ref,
            "version": required_version,
            "commit": lexhint_commit,
            "schema_version": required_schema,
        },
        "source": _source_record(
            source_url=source_url,
            source_label=source_label,
            source_edition=source_edition,
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

    manifest_path = output / "datasets-v2.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    checksum_lines = [
        f"{record['sha256']}  {record['asset']}" for record in artifact_records
    ]
    (output / "SHA256SUMS").write_text(
        "\n".join(checksum_lines) + "\n", encoding="utf-8"
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
    parser.add_argument("--artifact", action="append", metavar="LANGUAGE/VARIANT=PATH")
    parser.add_argument("--output-dir", type=Path, default=Path("dist"))
    parser.add_argument("--config", type=Path)
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--lexhint-ref", required=True)
    parser.add_argument("--lexhint-version")
    parser.add_argument("--lexhint-commit", required=True)
    parser.add_argument("--expected-schema")
    parser.add_argument("--builder-repository")
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--source-label", required=True)
    parser.add_argument("--source-edition")
    parser.add_argument("--source-sha256")
    parser.add_argument("--source-splits", type=Path)
    parser.add_argument("--contract", type=Path)
    parser.add_argument("--expected-language", action="append")
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
                language, variant = slot.split("/", 1)
            except ValueError as exc:
                raise PackagingError(f"invalid --artifact value: {value!r}") from exc
            inputs.append(ArtifactInput(Path(raw_path), language, variant))
        split_data = None
        if args.source_splits:
            split_data = json.loads(args.source_splits.read_text(encoding="utf-8"))
        contract = None
        if args.contract:
            contract = json.loads(args.contract.read_text(encoding="utf-8"))
        builder_repository = None
        if args.builder_repository:
            builder_repository = {
                "repository": args.builder_repository,
                "commit": __import__("os").environ.get("GITHUB_SHA", ""),
            }
        records = [
            package_artifact(
                item.path,
                language=item.language,
                variant=item.variant,
                dataset_version=args.dataset_version,
                output_dir=args.output_dir,
                config=config,
                expected_schema=args.expected_schema,
                build_source=(
                    split_data.get("splits", {}).get(item.language)
                    if split_data is not None
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
            source_url=args.source_url,
            source_label=args.source_label,
            source_edition=args.source_edition,
            source_sha256=args.source_sha256,
            attribution=args.attribution,
            publish=args.publish,
            config=config,
            builder_repository=builder_repository,
            expected_languages=args.expected_language,
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
