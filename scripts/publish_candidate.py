#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from scripts.config import SOURCE_VARIANTS

MAX_RELEASE_ASSET_BYTES = 2 * 1024**3
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ASSET_NAME = re.compile(
    r"lexhint-(?P<language>[a-z]{2,3})-(?:(?P<source_variant>native|english)-)?"
    r"(?P<variant>[a-z0-9_-]+)-s(?P<schema>[0-9]+)-(?P<version>[^/]+)\.sqlite3\.gz$"
)


class CandidateError(RuntimeError):
    """The uploaded candidate is not safe to publish."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_candidate(
    candidate_dir: str | Path,
    *,
    dataset_version: str,
    candidate_commit: str,
    expected_languages: set[str] | None = None,
    expected_source_variant: str | None = None,
    expected_variants: set[str] | None = None,
    expected_schema: str | None = None,
) -> dict[str, Any]:
    root = Path(candidate_dir)
    manifest_path = root / "datasets-v2.json"
    sums_path = root / "SHA256SUMS"
    attribution_path = root / "ATTRIBUTION.md"
    for required in (manifest_path, sums_path, attribution_path):
        if not required.is_file() or required.stat().st_size == 0:
            raise CandidateError(f"candidate file is missing or empty: {required.name}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CandidateError(f"invalid candidate manifest: {exc}") from exc
    if manifest.get("dataset_version") != dataset_version:
        raise CandidateError("candidate dataset version does not match promotion input")
    builder = manifest.get("builder_repository") or {}
    if builder.get("commit") != candidate_commit:
        raise CandidateError("candidate builder commit does not match promotion input")
    source = manifest.get("source")
    if not isinstance(source, dict):
        raise CandidateError("candidate source provenance is missing")
    source_variant = str(
        manifest.get("source_variant", source.get("source_variant", "native"))
    )
    if source_variant not in SOURCE_VARIANTS:
        raise CandidateError("candidate source variant is invalid")
    if source.get("source_variant", source_variant) != source_variant:
        raise CandidateError(
            "candidate manifest source variant does not match source record"
        )
    if not _SHA256.fullmatch(str(source.get("sha256", ""))):
        raise CandidateError("candidate source SHA-256 is missing or invalid")
    lexhint = manifest.get("lexhint")
    if not isinstance(lexhint, dict):
        raise CandidateError("candidate Lexhint provenance is missing")
    schema = str(lexhint.get("schema_version", "")).strip()
    if (
        not schema
        or not str(lexhint.get("version", "")).strip()
        or not str(lexhint.get("commit", "")).strip()
    ):
        raise CandidateError("candidate Lexhint provenance is incomplete")
    if expected_schema is not None and schema != expected_schema:
        raise CandidateError(
            f"candidate schema mismatch: expected {expected_schema!r}, got {schema!r}"
        )

    contract_path = root / "lexhint-contract.json"
    if manifest.get("lexhint_contract") is not None:
        if not contract_path.is_file():
            raise CandidateError("candidate Lexhint contract file is missing")
        try:
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CandidateError(f"invalid candidate Lexhint contract: {exc}") from exc
        for field, value in (
            ("schema_version", schema),
            ("lexhint_version", lexhint["version"]),
            ("lexhint_commit", lexhint["commit"]),
        ):
            if contract.get(field) != value:
                raise CandidateError(
                    f"candidate contract {field} does not match manifest"
                )

    sums: dict[str, str] = {}
    for line in sums_path.read_text(encoding="utf-8").splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) != 2 or not _SHA256.fullmatch(parts[0]):
            raise CandidateError(f"invalid checksum line: {line!r}")
        sums[parts[1].strip()] = parts[0]
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise CandidateError("candidate manifest contains no artifacts")
    slots: set[tuple[str, str, str, str]] = set()
    languages: set[str] = set()
    source_variants: set[str] = set()
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            raise CandidateError("candidate artifact must be an object")
        language = str(artifact.get("language", ""))
        variant = str(artifact.get("variant", ""))
        artifact_source = str(artifact.get("source_variant", source_variant))
        artifact_schema = str(artifact.get("schema_version", "")).strip()
        asset = str(artifact.get("asset", ""))
        asset_match = _ASSET_NAME.fullmatch(asset)
        if artifact_source != source_variant:
            raise CandidateError(f"candidate artifact source variant mismatch: {asset}")
        if artifact_schema != schema:
            raise CandidateError(
                f"candidate artifact schema mismatch: {language}/{variant}"
            )
        if asset_match is None or (
            asset_match.group("language") != language
            or (asset_match.group("source_variant") or "native") != artifact_source
            or asset_match.group("variant") != variant
            or asset_match.group("schema") != schema
            or asset_match.group("version") != dataset_version
        ):
            raise CandidateError(f"candidate filename schema mismatch: {asset}")
        slot = (language, artifact_source, variant, artifact_schema)
        if slot in slots:
            raise CandidateError(
                f"duplicate candidate slot: {language}/{artifact_source}/{variant}/s{schema}"
            )
        slots.add(slot)
        languages.add(language)
        source_variants.add(artifact_source)
        path = root / asset
        if not path.is_file() or path.stat().st_size >= MAX_RELEASE_ASSET_BYTES:
            raise CandidateError(f"candidate asset is missing or too large: {asset}")
        digest = _sha256(path)
        if sums.get(asset) != digest or artifact.get("sha256") != digest:
            raise CandidateError(f"candidate checksum mismatch: {asset}")
    if set(sums) != {str(artifact["asset"]) for artifact in artifacts}:
        raise CandidateError("SHA256SUMS does not exactly match manifest assets")
    if len(languages) != 1 or len(source_variants) != 1:
        raise CandidateError(
            "candidate must contain exactly one language and source variant"
        )
    if manifest.get("language") is not None and manifest["language"] not in languages:
        raise CandidateError("candidate manifest language does not match its artifacts")
    if expected_languages is not None and languages != expected_languages:
        raise CandidateError(
            f"candidate language mismatch: expected {sorted(expected_languages)}, got {sorted(languages)}"
        )
    if expected_source_variant is not None and source_variants != {
        expected_source_variant
    }:
        raise CandidateError(
            f"candidate source variant mismatch: expected {expected_source_variant!r}, got {sorted(source_variants)}"
        )
    actual_variants = {slot[2] for slot in slots}
    if expected_variants is not None and actual_variants != expected_variants:
        raise CandidateError(
            f"candidate variants mismatch: expected {sorted(expected_variants)}, got {sorted(actual_variants)}"
        )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a Lexhint dataset candidate.")
    parser.add_argument("candidate_dir", type=Path)
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--candidate-commit", required=True)
    parser.add_argument("--expected-schema")
    parser.add_argument("--expected-language")
    parser.add_argument("--expected-source-variant", choices=SOURCE_VARIANTS)
    parser.add_argument("--expected-variant", action="append")
    args = parser.parse_args()
    try:
        manifest = verify_candidate(
            args.candidate_dir,
            dataset_version=args.dataset_version,
            candidate_commit=args.candidate_commit,
            expected_schema=args.expected_schema,
            expected_languages={args.expected_language}
            if args.expected_language
            else None,
            expected_source_variant=args.expected_source_variant,
            expected_variants=set(args.expected_variant)
            if args.expected_variant
            else None,
        )
    except (CandidateError, OSError) as exc:
        print(f"candidate verification failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
