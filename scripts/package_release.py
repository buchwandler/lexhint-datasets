#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from collections.abc import Iterable

from lexhint import Lexicon
from lexhint.status import read_artifact_status

from scripts.config import DatasetConfig, load_config
from scripts.validate import ValidationError, validate

_ARTIFACT_NAME = re.compile(
    r"(?P<language>[a-z]{2})-(?P<variant>lexical|runtime|rich)\.sqlite3$"
)


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
    with source.open("rb") as src, target.open("wb") as raw:
        with gzip.GzipFile(
            filename=member_name or target.name,
            mode="wb",
            fileobj=raw,
            compresslevel=9,
            mtime=0,
        ) as dst:
            shutil.copyfileobj(src, dst, length=1024 * 1024)


def _metadata_for(lexicon: Lexicon) -> dict[str, str]:
    return dict(lexicon.metadata)


def package_artifact(
    database: str | Path,
    *,
    language: str,
    variant: str,
    dataset_version: str,
    output_dir: str | Path,
    config: DatasetConfig | None = None,
) -> dict[str, Any]:
    path = Path(database)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    config = config or load_config()
    variant_config = config.variant(variant)

    try:
        validation = validate(
            path,
            language=language,
            variant=variant,
            expected_capabilities=variant_config.capabilities,
            probe_word="",
        )
    except (ValidationError, OSError, ValueError) as exc:
        raise PackagingError(f"cannot package {language}/{variant}: {exc}") from exc

    lexicon = Lexicon.from_path(path, language=language)
    status = read_artifact_status(path=path)
    schema_version = status.schema_version
    asset_name = (
        f"lexhint-{language}-{variant}-s{schema_version}-{dataset_version}.sqlite3.gz"
    )
    asset_path = output / asset_name
    gzip_copy(path, asset_path, member_name=asset_name)
    metadata = _metadata_for(lexicon)

    return {
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
        "compressed_size": asset_path.stat().st_size,
        "uncompressed_size": path.stat().st_size,
        "counts": status.counts,
        "frequency": status.frequency,
        "artifact_metadata": {
            key: value
            for key, value in metadata.items()
            if key
            in {
                "built_at",
                "builder_version",
                "dictionary_source_sha256",
                "dictionary_source_url",
                "frequency_source",
                "frequency_corpus",
                "frequency_source_revision",
                "frequency_source_sha256",
            }
        },
    }


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
    source_sha256: str | None,
) -> None:
    slots: set[tuple[str, str]] = set()
    schemas: set[str] = set()
    for record in records:
        slot = (str(record["language"]), str(record["variant"]))
        if slot in slots:
            raise PackagingError(f"duplicate artifact slot: {slot[0]}/{slot[1]}")
        slots.add(slot)
        variant = config.variant(slot[1])
        if tuple(record["capabilities"]) != variant.capabilities:
            raise PackagingError(f"capability mismatch for {slot[0]}/{slot[1]}")
        if record["coverage"] != "full":
            raise PackagingError(f"artifact is not full coverage: {slot[0]}/{slot[1]}")
        if not record["sha256"]:
            raise PackagingError(f"artifact checksum is missing: {slot[0]}/{slot[1]}")
        schemas.add(str(record["schema_version"]))
        embedded_hash = record["artifact_metadata"].get("dictionary_source_sha256")
        if source_sha256 and embedded_hash and embedded_hash != source_sha256:
            raise PackagingError(
                f"source checksum mismatch for {slot[0]}/{slot[1]}: "
                f"{embedded_hash} != {source_sha256}"
            )
    if len(schemas) > 1:
        raise PackagingError(
            f"artifacts use incompatible schema versions: {sorted(schemas)}"
        )
    if not lexhint_commit:
        raise PackagingError("lexhint commit is required")


def _source_record(
    *,
    source_url: str,
    source_label: str,
    source_sha256: str | None,
    publish: bool,
    config: DatasetConfig,
) -> dict[str, str | None]:
    if publish and config.source.require_sha256_on_publish and not source_sha256:
        raise PackagingError("source_sha256 is required for a published release")
    return {"url": source_url, "label": source_label, "sha256": source_sha256}


def _release_notes(manifest: dict[str, Any]) -> str:
    languages = sorted({record["language"] for record in manifest["artifacts"]})
    variants: dict[str, tuple[str, ...]] = {}
    for record in manifest["artifacts"]:
        variants[record["variant"]] = tuple(record["capabilities"])
    lines = [
        f"# Lexhint datasets {manifest['dataset_version']}",
        "",
        f"Built with Lexhint `{manifest['lexhint']['ref']}` at commit `{manifest['lexhint']['commit']}`.",
        "",
        f"Schema: {manifest['lexhint']['schema_version']}",
        "",
        "Languages:",
        *(f"- {language}" for language in languages),
        "",
        "Variants:",
        *(
            f"- {name}: {', '.join(capabilities)}"
            for name, capabilities in sorted(variants.items())
        ),
        "",
        "Source:",
        f"- label: {manifest['source']['label']}",
        f"- SHA-256: {manifest['source']['sha256'] or 'not supplied'}",
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
    source_url: str,
    source_label: str,
    source_sha256: str | None = None,
    attribution: str | Path | None = None,
    publish: bool = False,
    config: DatasetConfig | None = None,
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    config = config or load_config()
    artifact_records = sorted(records, key=lambda record: record["id"])
    if not artifact_records:
        raise PackagingError("release contains no artifacts")
    _check_release_invariants(
        artifact_records,
        config=config,
        lexhint_commit=lexhint_commit,
        source_sha256=source_sha256,
    )
    schema_versions = {record["schema_version"] for record in artifact_records}
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    manifest = {
        "manifest_version": 2,
        "dataset_version": dataset_version,
        "generated_at": generated_at,
        "lexhint": {
            "ref": lexhint_ref,
            "commit": lexhint_commit,
            "schema_version": next(iter(schema_versions)),
        },
        "source": _source_record(
            source_url=source_url,
            source_label=source_label,
            source_sha256=source_sha256,
            publish=publish,
            config=config,
        ),
        "artifacts": artifact_records,
    }

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
    parser.add_argument("--lexhint-commit", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--source-label", required=True)
    parser.add_argument("--source-sha256")
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
        records = [
            package_artifact(
                item.path,
                language=item.language,
                variant=item.variant,
                dataset_version=args.dataset_version,
                output_dir=args.output_dir,
                config=config,
            )
            for item in inputs
        ]
        manifest = package_release(
            records,
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
    except (PackagingError, ValidationError, OSError, ValueError) as exc:
        print(f"packaging failed: {exc}", file=__import__("sys").stderr)
        return 1
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
