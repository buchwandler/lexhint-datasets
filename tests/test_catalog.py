from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.catalog import (
    CatalogError,
    empty_catalog,
    load_catalog,
    merge_entries,
    release_entries,
    validate_catalog,
    write_catalog,
)


def _manifest(
    language: str | None,
    version: str = "2026.08.31",
    *,
    variant: str = "runtime",
    schema: str = "10",
    asset_hash: str = "a" * 64,
    compressed_size: int = 123,
) -> dict[str, object]:
    artifact_language = language or "de"
    artifact = {
        "id": f"{artifact_language}/{variant}",
        "language": artifact_language,
        "variant": variant,
        "profile": "runtime",
        "capabilities": ["lexical", "semantic"],
        "coverage": "full",
        "schema_version": schema,
        "asset": f"lexhint-{artifact_language}-{variant}-s{schema}-{version}.sqlite3.gz",
        "sha256": asset_hash,
        "compressed_size": compressed_size,
        "uncompressed_size": 456,
    }
    return {
        "manifest_version": 2,
        "language": language,
        "dataset_version": version,
        "artifacts": [artifact],
    }


def _release(
    language: str | None,
    *,
    tag: str | None = None,
    version: str = "2026.08.31",
    manifest: dict[str, object] | None = None,
    asset_hash: str = "a" * 64,
    size: int = 123,
    digest: str | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    manifest = manifest or _manifest(
        language, version, asset_hash=asset_hash, compressed_size=size
    )
    raw_manifest = json.dumps(manifest, sort_keys=True).encode()
    tag = tag or (f"data-{language}-{version}" if language else f"data-{version}")
    asset_name = str(manifest["artifacts"][0]["asset"])
    base = f"https://github.com/buchwandler/lexhint-datasets/releases/download/{tag}"
    release = {
        "tag_name": tag,
        "published_at": "2026-08-31T16:40:00Z",
        "assets": [
            {
                "name": "datasets-v2.json",
                "size": len(raw_manifest),
                "browser_download_url": f"{base}/datasets-v2.json",
            },
            {
                "name": asset_name,
                "size": size,
                "digest": digest or f"sha256:{asset_hash}",
                "browser_download_url": f"{base}/{asset_name}",
            },
        ],
        "manifest_sha256": hashlib.sha256(raw_manifest).hexdigest(),
    }
    return release, manifest


def test_empty_catalog_creation_and_deterministic_json(tmp_path: Path) -> None:
    first = tmp_path / "one.json"
    second = tmp_path / "two.json"
    write_catalog(first, empty_catalog())
    write_catalog(second, load_catalog(first))
    assert first.read_bytes() == second.read_bytes()
    assert json.loads(first.read_text()) == empty_catalog()


def test_imports_de_en_es_with_same_version_and_builder_commit() -> None:
    catalog = empty_catalog()
    entries = []
    for language in ("de", "en", "es"):
        release, manifest = _release(language)
        release["target_commitish"] = "builder-commit"
        entries.extend(release_entries(release, manifest))
    result = merge_entries(catalog, entries)
    assert {entry["language"] for entry in result["artifacts"]} == {"de", "en", "es"}
    assert {entry["release_tag"] for entry in result["artifacts"]} == {
        "data-de-2026.08.31",
        "data-en-2026.08.31",
        "data-es-2026.08.31",
    }


def test_duplicate_ids_and_slots_are_rejected() -> None:
    release, manifest = _release("de")
    entry = release_entries(release, manifest)[0]
    with pytest.raises(CatalogError, match="duplicate artifact id"):
        validate_catalog({**empty_catalog(), "artifacts": [entry, dict(entry)]})
    other = dict(entry, id="de/runtime/s10/other")
    with pytest.raises(CatalogError, match="artifact id does not match"):
        validate_catalog({**empty_catalog(), "artifacts": [entry, other]})
    other = dict(entry, release_tag="data-de-2026.08.32")
    with pytest.raises(CatalogError, match="duplicate artifact id"):
        validate_catalog({**empty_catalog(), "artifacts": [entry, other]})


def test_language_qualified_tag_mismatch_is_rejected() -> None:
    release, manifest = _release("de", tag="data-en-2026.08.31")
    with pytest.raises(CatalogError, match="does not match"):
        release_entries(release, manifest)


def test_legacy_combined_release_is_accepted() -> None:
    first = _manifest("de")
    second = _manifest("en")
    second["artifacts"][0]["asset"] = "lexhint-en-runtime-s10-2026.08.31.sqlite3.gz"
    manifest = {
        "manifest_version": 2,
        "dataset_version": "2026.08.31",
        "artifacts": [first["artifacts"][0], second["artifacts"][0]],
    }
    raw = json.dumps(manifest, sort_keys=True).encode()
    release = {
        "tag_name": "data-2026.08.31",
        "published_at": "2026-08-31T16:40:00Z",
        "assets": [
            {
                "name": "datasets-v2.json",
                "size": len(raw),
                "browser_download_url": "https://github.com/buchwandler/lexhint-datasets/releases/download/data-2026.08.31/datasets-v2.json",
            },
            *[
                {
                    "name": str(item["asset"]),
                    "size": 123,
                    "digest": f"sha256:{item['sha256']}",
                    "browser_download_url": f"https://github.com/buchwandler/lexhint-datasets/releases/download/data-2026.08.31/{item['asset']}",
                }
                for item in manifest["artifacts"]
            ],
        ],
        "manifest_sha256": hashlib.sha256(raw).hexdigest(),
    }
    entries = release_entries(release, manifest)
    assert {entry["language"] for entry in entries} == {"de", "en"}


def test_schema_filename_capability_hash_and_size_mismatches_are_rejected() -> None:
    release, manifest = _release("de")
    broken = dict(manifest["artifacts"][0], asset="wrong.sqlite3.gz")
    with pytest.raises(CatalogError, match="schema/filename"):
        release_entries(release, {**manifest, "artifacts": [broken]})

    broken = dict(manifest["artifacts"][0], capabilities=["lexical"])
    with pytest.raises(CatalogError, match="capability"):
        release_entries(release, {**manifest, "artifacts": [broken]})

    broken = dict(manifest["artifacts"][0], sha256="b" * 64)
    with pytest.raises(CatalogError, match="digest mismatch"):
        release_entries(release, {**manifest, "artifacts": [broken]})

    broken_release = {
        **release,
        "assets": [release["assets"][0], {**release["assets"][1], "size": 999}],
    }
    with pytest.raises(CatalogError, match="size mismatch"):
        release_entries(broken_release, manifest)


def test_missing_manifest_or_database_asset_is_rejected() -> None:
    release, manifest = _release("de")
    with pytest.raises(CatalogError, match="missing manifest"):
        release_entries({**release, "assets": [release["assets"][1]]}, manifest)
    with pytest.raises(CatalogError, match="missing database"):
        release_entries({**release, "assets": [release["assets"][0]]}, manifest)


def test_merge_is_idempotent_and_qualified_release_replaces_legacy() -> None:
    legacy_release, legacy_manifest = _release(None)
    qualified_release, qualified_manifest = _release("de")
    catalog = merge_entries(
        empty_catalog(), release_entries(legacy_release, legacy_manifest)
    )
    catalog = merge_entries(
        catalog, release_entries(qualified_release, qualified_manifest)
    )
    assert [entry["release_tag"] for entry in catalog["artifacts"]] == [
        "data-de-2026.08.31"
    ]
    assert (
        merge_entries(catalog, release_entries(qualified_release, qualified_manifest))
        == catalog
    )


def test_sync_entry_manifest_urls_are_direct_github_urls() -> None:
    release, manifest = _release("de")
    entry = release_entries(release, manifest)[0]
    assert entry["manifest"]["url"].startswith("https://github.com/")
    assert entry["asset"]["url"].startswith("https://github.com/")


def test_sync_releases_is_idempotent_and_skips_drafts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release, manifest = _release("de")
    calls = 0

    def fetch(_release: object) -> tuple[dict[str, object], str]:
        nonlocal calls
        calls += 1
        return manifest, str(release["manifest_sha256"])

    monkeypatch.setattr("scripts.sync_catalog.fetch_manifest", fetch)
    from scripts.sync_catalog import sync_releases

    draft = dict(release, tag_name="data-de-draft", draft=True)
    first = sync_releases([draft, release], empty_catalog())
    second = sync_releases([release], first)
    assert first == second
    assert calls == 2
    assert len(first["artifacts"]) == 1
