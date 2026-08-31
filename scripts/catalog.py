#!/usr/bin/env python3
"""Pure catalog construction and validation for published dataset releases."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from scripts.config import DatasetConfig, load_config

REPOSITORY = "buchwandler/lexhint-datasets"
CATALOG_VERSION = 1
RUNTIME_CONTRACT = 1
_RELEASE_TAG = re.compile(r"^data-(?:(?P<language>[a-z]{2})-)?(?P<version>[^/]+)$")
_ASSET_NAME = re.compile(
    r"^lexhint-(?P<language>[a-z]{2})-(?P<variant>[a-z0-9_-]+)"
    r"-s(?P<schema>[0-9]+)-(?P<version>[^/]+)\.sqlite3\.gz$"
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")

IMMUTABLE_FIELDS = (
    "language",
    "variant",
    "dataset_version",
    "schema_version",
    "profile",
    "coverage",
    "capabilities",
    "release_tag",
    "release_published_at",
    "manifest",
    "asset",
)


class CatalogError(RuntimeError):
    """The catalog or a published release violates the discovery contract."""


@dataclass(frozen=True, slots=True)
class CatalogArtifact:
    id: str
    language: str
    variant: str
    dataset_version: str
    schema_version: str
    profile: str | None
    coverage: str
    capabilities: tuple[str, ...]
    release_tag: str
    release_published_at: str
    manifest_url: str
    manifest_sha256: str
    asset_name: str
    asset_url: str
    asset_sha256: str
    compressed_size: int
    uncompressed_size: int

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "language": self.language,
            "variant": self.variant,
            "dataset_version": self.dataset_version,
            "schema_version": self.schema_version,
            "profile": self.profile,
            "coverage": self.coverage,
            "capabilities": list(self.capabilities),
            "release_tag": self.release_tag,
            "release_published_at": self.release_published_at,
            "manifest": {
                "url": self.manifest_url,
                "sha256": self.manifest_sha256,
            },
            "asset": {
                "name": self.asset_name,
                "url": self.asset_url,
                "sha256": self.asset_sha256,
                "compressed_size": self.compressed_size,
                "uncompressed_size": self.uncompressed_size,
            },
        }


def empty_catalog() -> dict[str, object]:
    return {
        "catalog_version": CATALOG_VERSION,
        "runtime_contract": RUNTIME_CONTRACT,
        "repository": REPOSITORY,
        "artifacts": [],
    }


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CatalogError(f"{field} must be a non-empty string")
    return value.strip()


def _sha(value: object, field: str) -> str:
    result = _text(value, field)
    if _SHA256.fullmatch(result) is None:
        raise CatalogError(f"{field} must be 64 lowercase hex characters")
    return result


def _size(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise CatalogError(f"{field} must be positive")
    return value


def _config(config: DatasetConfig | None) -> DatasetConfig:
    return config or load_config()


def _release_tag(tag: str, *, language: str, version: str) -> None:
    match = _RELEASE_TAG.fullmatch(tag)
    if match is None or match.group("version") != version:
        raise CatalogError(
            f"invalid release tag for dataset version {version!r}: {tag!r}"
        )
    tag_language = match.group("language")
    if tag_language is not None and tag_language != language:
        raise CatalogError(
            f"language-qualified release tag {tag!r} does not match language {language!r}"
        )


def _release_url(tag: str, filename: str) -> str:
    return f"https://github.com/{REPOSITORY}/releases/download/{tag}/{filename}"


def _require_release_asset(
    assets: Mapping[str, Mapping[str, object]], name: str, *, field: str
) -> Mapping[str, object]:
    try:
        return assets[name]
    except KeyError as exc:
        raise CatalogError(f"missing {field} asset: {name}") from exc


def _asset_map(release: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    raw_assets = release.get("assets")
    if not isinstance(raw_assets, Iterable) or isinstance(raw_assets, (str, bytes)):
        raise CatalogError("release assets must be an array")
    result: dict[str, Mapping[str, object]] = {}
    for raw_asset in raw_assets:
        if not isinstance(raw_asset, Mapping):
            raise CatalogError("release asset must be an object")
        name = _text(raw_asset.get("name"), "release asset name")
        if name in result:
            raise CatalogError(f"duplicate release asset: {name}")
        result[name] = raw_asset
    return result


def _published_at(release: Mapping[str, object]) -> str:
    value = release.get("published_at")
    if value is None:
        value = release.get("created_at")
    return _text(value, "release_published_at")


def _manifest_sha256(
    release: Mapping[str, object], manifest: Mapping[str, object]
) -> str:
    value = release.get("manifest_sha256", release.get("_manifest_sha256"))
    if value is None:
        value = manifest.get("manifest_sha256", manifest.get("_manifest_sha256"))
    return _sha(value, "manifest.sha256")


def _validate_url(url: object, expected: str, field: str) -> str:
    actual = _text(url, field)
    parsed = urlsplit(actual)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "github.com"
        or actual != expected
    ):
        raise CatalogError(f"{field} must be the exact GitHub release URL: {expected}")
    return actual


def _artifact_entry(
    release: Mapping[str, object],
    manifest: Mapping[str, object],
    artifact: Mapping[str, object],
    release_assets: Mapping[str, Mapping[str, object]],
    *,
    config: DatasetConfig,
    manifest_sha256: str,
    published_at: str,
    tag: str,
    manifest_asset: Mapping[str, object],
) -> dict[str, object]:
    language = _text(artifact.get("language"), "artifact.language")
    tag_match = _RELEASE_TAG.fullmatch(tag)
    if tag_match is not None and tag_match.group("language") not in (None, language):
        raise CatalogError(
            f"language-qualified release tag {tag!r} does not match language {language!r}"
        )
    manifest_language = manifest.get("language")
    if manifest_language is not None:
        manifest_language = _text(manifest_language, "manifest.language")
    if manifest_language is not None and language != manifest_language:
        raise CatalogError("artifact language does not match manifest language")
    language_config = config.languages.get(language)
    if language_config is None or not language_config.enabled:
        raise CatalogError(f"language is not configured and enabled: {language!r}")
    variant = _text(artifact.get("variant"), "artifact.variant")
    try:
        variant_config = config.variant(variant)
    except ValueError as exc:
        raise CatalogError(str(exc)) from exc
    profile = artifact.get("profile")
    if profile is not None and not isinstance(profile, str):
        raise CatalogError("artifact.profile must be a string or null")
    coverage = _text(artifact.get("coverage"), "artifact.coverage")
    if coverage != "full":
        raise CatalogError(f"artifact coverage must be full: {language}/{variant}")
    raw_capabilities = artifact.get("capabilities")
    if not isinstance(raw_capabilities, list) or any(
        not isinstance(item, str) for item in raw_capabilities
    ):
        raise CatalogError(
            f"artifact capabilities must be an array: {language}/{variant}"
        )
    capabilities = tuple(raw_capabilities)
    if capabilities != variant_config.capabilities:
        raise CatalogError(f"capability mismatch for {language}/{variant}")
    dataset_version = _text(manifest.get("dataset_version"), "manifest.dataset_version")
    schema = _text(artifact.get("schema_version"), "artifact.schema_version")
    asset_name = _text(artifact.get("asset"), "artifact.asset")
    match = _ASSET_NAME.fullmatch(asset_name)
    if match is None or (
        match.group("language") != language
        or match.group("variant") != variant
        or match.group("schema") != schema
        or match.group("version") != dataset_version
    ):
        raise CatalogError(
            f"schema/filename mismatch for {language}/{variant}: {asset_name!r}"
        )
    artifact_version = artifact.get("dataset_version")
    if artifact_version is not None and str(artifact_version) != dataset_version:
        raise CatalogError(f"artifact dataset version mismatch for {asset_name}")
    asset = _require_release_asset(release_assets, asset_name, field="database")
    asset_size = _size(asset.get("size"), f"release asset size for {asset_name}")
    compressed_size = _size(
        artifact.get("compressed_size"), f"manifest compressed_size for {asset_name}"
    )
    if asset_size != compressed_size:
        raise CatalogError(f"GitHub asset size mismatch for {asset_name}")
    asset_hash = _sha(artifact.get("sha256"), f"manifest sha256 for {asset_name}")
    digest = asset.get("digest")
    if digest is not None:
        digest_text = _text(digest, f"GitHub digest for {asset_name}")
        if not digest_text.startswith("sha256:") or digest_text[7:] != asset_hash:
            raise CatalogError(f"GitHub digest mismatch for {asset_name}")
    asset_url = _release_url(tag, asset_name)
    _validate_url(
        asset.get("browser_download_url"), asset_url, f"asset URL for {asset_name}"
    )
    uncompressed_size = _size(
        artifact.get("uncompressed_size"),
        f"manifest uncompressed_size for {asset_name}",
    )
    manifest_url = _release_url(tag, "datasets-v2.json")
    _validate_url(
        manifest_asset.get("browser_download_url"),
        manifest_url,
        "manifest asset URL",
    )
    artifact_id = f"{language}/{variant}/s{schema}/{dataset_version}"
    return {
        "id": artifact_id,
        "language": language,
        "variant": variant,
        "dataset_version": dataset_version,
        "schema_version": schema,
        "profile": profile,
        "coverage": coverage,
        "capabilities": list(capabilities),
        "release_tag": tag,
        "release_published_at": published_at,
        "manifest": {"url": manifest_url, "sha256": manifest_sha256},
        "asset": {
            "name": asset_name,
            "url": asset_url,
            "sha256": asset_hash,
            "compressed_size": compressed_size,
            "uncompressed_size": uncompressed_size,
        },
    }


def release_entries(
    release: Mapping[str, object],
    manifest: Mapping[str, object],
    *,
    config: DatasetConfig | None = None,
) -> tuple[dict[str, object], ...]:
    """Convert one release API object and its manifest into catalog entries."""
    config = _config(config)
    tag = _text(release.get("tag_name"), "release tag")
    manifest_version = manifest.get("manifest_version")
    if manifest_version != 2:
        raise CatalogError("release manifest_version must be 2")
    manifest_language = manifest.get("language")
    if manifest_language is not None:
        manifest_language = _text(manifest_language, "manifest.language")
    dataset_version = _text(manifest.get("dataset_version"), "manifest.dataset_version")
    tag_match = _RELEASE_TAG.fullmatch(tag)
    if tag_match is None or tag_match.group("version") != dataset_version:
        raise CatalogError(
            f"invalid release tag for dataset version {dataset_version!r}: {tag!r}"
        )
    tag_language = tag_match.group("language")
    if tag_language and manifest_language and tag_language != manifest_language:
        raise CatalogError(
            f"language-qualified release tag {tag!r} does not match manifest language {manifest_language!r}"
        )
    published_at = _published_at(release)
    assets = _asset_map(release)
    manifest_asset = _require_release_asset(
        assets, "datasets-v2.json", field="manifest"
    )
    manifest_sha = _manifest_sha256(release, manifest)
    raw_artifacts = manifest.get("artifacts")
    if not isinstance(raw_artifacts, list) or not raw_artifacts:
        raise CatalogError("release manifest contains no artifacts")
    entries = tuple(
        _artifact_entry(
            release,
            manifest,
            artifact,
            assets,
            config=config,
            manifest_sha256=manifest_sha,
            published_at=published_at,
            tag=tag,
            manifest_asset=manifest_asset,
        )
        for artifact in raw_artifacts
        if isinstance(artifact, Mapping)
    )
    if len(entries) != len(raw_artifacts):
        raise CatalogError("release manifest artifact must be an object")
    if not entries:
        raise CatalogError("release manifest contains no artifacts")
    return tuple(sorted(entries, key=lambda item: str(item["id"])))


def _entry_fields(entry: Mapping[str, object]) -> tuple[object, ...]:
    return tuple(entry.get(field) for field in IMMUTABLE_FIELDS)


def _slot(entry: Mapping[str, object]) -> tuple[str, str, str, str]:
    return (
        str(entry.get("language", "")),
        str(entry.get("variant", "")),
        str(entry.get("schema_version", "")),
        str(entry.get("dataset_version", "")),
    )


def _is_qualified(tag: object) -> bool:
    match = _RELEASE_TAG.fullmatch(str(tag))
    return bool(match and match.group("language"))


def _variant_order(config: DatasetConfig) -> dict[str, int]:
    return {name: index for index, name in enumerate(config.variants)}


def _sort_key(entry: Mapping[str, object], config: DatasetConfig) -> tuple[object, ...]:
    schema = str(entry.get("schema_version", ""))
    try:
        schema_key: object = (0, int(schema))
    except ValueError:
        schema_key = (1, schema)
    return (
        str(entry.get("language", "")),
        _variant_order(config).get(str(entry.get("variant", "")), len(config.variants)),
        schema_key,
        str(entry.get("release_published_at", "")),
        str(entry.get("dataset_version", "")),
        str(entry.get("release_tag", "")),
    )


def validate_catalog(
    value: Mapping[str, object], *, config: DatasetConfig | None = None
) -> None:
    """Raise CatalogError unless value satisfies the stored catalog contract."""
    config = _config(config)
    if value.get("catalog_version") != CATALOG_VERSION:
        raise CatalogError("catalog_version must be 1")
    if value.get("runtime_contract") != RUNTIME_CONTRACT:
        raise CatalogError("runtime_contract must be 1")
    if value.get("repository") != REPOSITORY:
        raise CatalogError(f"repository must be {REPOSITORY!r}")
    raw_artifacts = value.get("artifacts")
    if not isinstance(raw_artifacts, list):
        raise CatalogError("artifacts must be an array")
    ids: set[str] = set()
    slots: set[tuple[str, str, str, str]] = set()
    for entry in raw_artifacts:
        if not isinstance(entry, Mapping):
            raise CatalogError("catalog artifact must be an object")
        entry_id = _text(entry.get("id"), "artifact.id")
        language = _text(entry.get("language"), "artifact.language")
        variant = _text(entry.get("variant"), "artifact.variant")
        schema = _text(entry.get("schema_version"), "artifact.schema_version")
        version = _text(entry.get("dataset_version"), "artifact.dataset_version")
        expected_id = f"{language}/{variant}/s{schema}/{version}"
        if entry_id != expected_id:
            raise CatalogError(f"artifact id does not match metadata: {entry_id}")
        if entry_id in ids:
            raise CatalogError(f"duplicate artifact id: {entry_id}")
        ids.add(entry_id)
        slot = _slot(entry)
        if slot in slots:
            raise CatalogError(f"duplicate artifact slot: {slot}")
        slots.add(slot)
        if language not in config.languages or not config.languages[language].enabled:
            raise CatalogError(f"language is not configured and enabled: {language!r}")
        try:
            variant_config = config.variant(variant)
        except ValueError as exc:
            raise CatalogError(str(exc)) from exc
        if tuple(entry.get("capabilities", ())) != variant_config.capabilities:
            raise CatalogError(f"capability mismatch for {language}/{variant}")
        if entry.get("coverage") != "full":
            raise CatalogError(f"artifact coverage must be full: {entry_id}")
        profile = entry.get("profile")
        if profile is not None and not isinstance(profile, str):
            raise CatalogError(f"profile must be a string or null: {entry_id}")
        tag = _text(entry.get("release_tag"), "artifact.release_tag")
        _release_tag(tag, language=language, version=version)
        published_at = _text(
            entry.get("release_published_at"), "artifact.release_published_at"
        )
        if not published_at:
            raise CatalogError(f"release publication timestamp is empty: {entry_id}")
        manifest = entry.get("manifest")
        if not isinstance(manifest, Mapping):
            raise CatalogError(f"manifest must be an object: {entry_id}")
        manifest_url = _release_url(tag, "datasets-v2.json")
        _validate_url(manifest.get("url"), manifest_url, f"manifest URL for {entry_id}")
        manifest_sha = _sha(manifest.get("sha256"), f"manifest SHA-256 for {entry_id}")
        del manifest_sha
        asset = entry.get("asset")
        if not isinstance(asset, Mapping):
            raise CatalogError(f"asset must be an object: {entry_id}")
        name = _text(asset.get("name"), f"asset name for {entry_id}")
        match = _ASSET_NAME.fullmatch(name)
        if match is None or (
            match.group("language") != language
            or match.group("variant") != variant
            or match.group("schema") != schema
            or match.group("version") != version
        ):
            raise CatalogError(f"schema/filename mismatch for {entry_id}: {name!r}")
        asset_url = _release_url(tag, name)
        _validate_url(asset.get("url"), asset_url, f"asset URL for {entry_id}")
        _sha(asset.get("sha256"), f"asset SHA-256 for {entry_id}")
        _size(asset.get("compressed_size"), f"compressed_size for {entry_id}")
        _size(asset.get("uncompressed_size"), f"uncompressed_size for {entry_id}")
    expected_order = sorted(raw_artifacts, key=lambda item: _sort_key(item, config))
    if list(raw_artifacts) != expected_order:
        raise CatalogError("artifacts are not in deterministic order")


def merge_entries(
    catalog: Mapping[str, object],
    entries: Iterable[Mapping[str, object]],
    *,
    config: DatasetConfig | None = None,
) -> dict[str, object]:
    """Merge entries, preferring qualified tags over legacy tags for equal slots."""
    config = _config(config)
    result: dict[str, object] = dict(catalog)
    raw_existing = result.get("artifacts", [])
    if not isinstance(raw_existing, list):
        raise CatalogError("catalog artifacts must be an array")
    existing = list(raw_existing)
    by_id: dict[str, Mapping[str, object]] = {
        str(item.get("id")): item for item in existing if isinstance(item, Mapping)
    }
    by_slot: dict[tuple[str, str, str, str], Mapping[str, object]] = {
        _slot(item): item for item in existing if isinstance(item, Mapping)
    }
    for raw_entry in entries:
        if not isinstance(raw_entry, Mapping):
            raise CatalogError("merged catalog entry must be an object")
        entry = dict(raw_entry)
        entry_id = _text(entry.get("id"), "artifact.id")
        tag = _text(entry.get("release_tag"), "artifact.release_tag")
        slot = _slot(entry)
        previous_id_entry = by_id.get(entry_id)
        if previous_id_entry is not None:
            previous_tag = str(previous_id_entry.get("release_tag"))
            if _entry_fields(previous_id_entry) == _entry_fields(entry):
                continue
            if _is_qualified(tag) and not _is_qualified(previous_tag):
                existing.remove(previous_id_entry)
                by_id.pop(entry_id, None)
                by_slot.pop(slot, None)
            elif not _is_qualified(tag) and _is_qualified(previous_tag):
                continue
            else:
                raise CatalogError(
                    f"Published release {tag!r} changed immutable catalog metadata. "
                    "Publish a new release tag instead of rewriting an existing catalog entry."
                )
        previous_slot_entry = by_slot.get(slot)
        if previous_slot_entry is not None:
            previous_tag = str(previous_slot_entry.get("release_tag"))
            if _entry_fields(previous_slot_entry) == _entry_fields(entry):
                continue
            if _is_qualified(tag) and not _is_qualified(previous_tag):
                existing.remove(previous_slot_entry)
                by_id.pop(str(previous_slot_entry.get("id")), None)
            elif not _is_qualified(tag) and _is_qualified(previous_tag):
                continue
            else:
                raise CatalogError(
                    f"duplicate catalog slot {slot} has different release metadata"
                )
        existing.append(entry)
        by_id[entry_id] = entry
        by_slot[slot] = entry
    result["artifacts"] = sorted(existing, key=lambda item: _sort_key(item, config))
    validate_catalog(result, config=config)
    return result


def load_catalog(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalogError(f"cannot load catalog {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CatalogError("catalog root must be an object")
    validate_catalog(value)
    return value


def write_catalog(path: Path, catalog: Mapping[str, object]) -> None:
    validate_catalog(catalog)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(catalog, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()
