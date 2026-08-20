#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

MAX_RELEASE_ASSET_BYTES = 2 * 1024**3
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


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
    expected_variants: set[str] | None = None,
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
    if not _SHA256.fullmatch(str(manifest.get("source", {}).get("sha256", ""))):
        raise CandidateError("candidate source SHA-256 is missing or invalid")

    sums: dict[str, str] = {}
    for line in sums_path.read_text(encoding="utf-8").splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) != 2 or not _SHA256.fullmatch(parts[0]):
            raise CandidateError(f"invalid checksum line: {line!r}")
        sums[parts[1].strip()] = parts[0]
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise CandidateError("candidate manifest contains no artifacts")
    slots: set[tuple[str, str]] = set()
    for artifact in artifacts:
        slot = (str(artifact.get("language")), str(artifact.get("variant")))
        if slot in slots:
            raise CandidateError(f"duplicate candidate slot: {slot[0]}/{slot[1]}")
        slots.add(slot)
        asset = str(artifact.get("asset", ""))
        path = root / asset
        if not path.is_file() or path.stat().st_size >= MAX_RELEASE_ASSET_BYTES:
            raise CandidateError(f"candidate asset is missing or too large: {asset}")
        digest = _sha256(path)
        if sums.get(asset) != digest or artifact.get("sha256") != digest:
            raise CandidateError(f"candidate checksum mismatch: {asset}")
    if set(sums) != {str(artifact["asset"]) for artifact in artifacts}:
        raise CandidateError("SHA256SUMS does not exactly match manifest assets")
    if expected_languages is not None and expected_variants is not None:
        expected = {
            (language, variant)
            for language in expected_languages
            for variant in expected_variants
        }
        if slots != expected:
            raise CandidateError(
                f"candidate matrix mismatch: expected {expected}, got {slots}"
            )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a Lexhint dataset candidate.")
    parser.add_argument("candidate_dir", type=Path)
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--candidate-commit", required=True)
    args = parser.parse_args()
    try:
        manifest = verify_candidate(
            args.candidate_dir,
            dataset_version=args.dataset_version,
            candidate_commit=args.candidate_commit,
        )
    except (CandidateError, OSError) as exc:
        print(f"candidate verification failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
