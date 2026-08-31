#!/usr/bin/env python3
"""Synchronize the static catalog from GitHub Release metadata."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from scripts.catalog import (
    REPOSITORY,
    CatalogError,
    empty_catalog,
    load_catalog,
    merge_entries,
    release_entries,
    sha256_bytes,
    write_catalog,
)

API_ROOT = "https://api.github.com"

DEFAULT_HISTORICAL_SKIP_TAGS = frozenset(
    {"data-2026.08.21"}
    # Schema 7's rich artifacts predate the configured search capability contract.
    # Keep the valid schema 7 family out of the catalog only when the release is obsolete.
)


class SyncError(RuntimeError):
    """Release metadata could not be imported safely."""


def _headers(*, binary: bool = False) -> dict[str, str]:
    headers = {
        "Accept": "application/octet-stream"
        if binary
        else "application/vnd.github+json",
        "User-Agent": "lexhint-datasets-catalog",
    }
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get(url: str, *, binary: bool = False) -> bytes:
    request = Request(url, headers=_headers(binary=binary))
    try:
        with urlopen(request) as response:
            return response.read()
    except (HTTPError, URLError, OSError) as exc:
        raise SyncError(f"cannot fetch {url}: {exc}") from exc


def fetch_json(url: str) -> dict[str, object]:
    try:
        value = json.loads(_get(url).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SyncError(f"invalid JSON from {url}: {exc}") from exc
    if not isinstance(value, dict):
        raise SyncError(f"expected JSON object from {url}")
    return value


def fetch_release(tag: str, *, repository: str = REPOSITORY) -> dict[str, object]:
    url = f"{API_ROOT}/repos/{repository}/releases/tags/{quote(tag, safe='')}"
    return fetch_json(url)


def fetch_releases(*, repository: str = REPOSITORY) -> list[dict[str, object]]:
    releases: list[dict[str, object]] = []
    page = 1
    while True:
        url = f"{API_ROOT}/repos/{repository}/releases?per_page=100&page={page}"
        payload = _get(url)
        try:
            values = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SyncError(f"invalid release list JSON: {exc}") from exc
        if not isinstance(values, list):
            raise SyncError("GitHub release list is not an array")
        if not values:
            return releases
        for value in values:
            if not isinstance(value, dict):
                raise SyncError("GitHub release list contains a non-object")
            releases.append(value)
        if len(values) < 100:
            return releases
        page += 1


def _assets(release: Mapping[str, object]) -> list[Mapping[str, object]]:
    values = release.get("assets")
    if not isinstance(values, list):
        raise SyncError("GitHub release assets are not an array")
    if any(not isinstance(value, Mapping) for value in values):
        raise SyncError("GitHub release assets contain a non-object")
    return [value for value in values if isinstance(value, Mapping)]


def fetch_manifest(release: Mapping[str, object]) -> tuple[dict[str, object], str]:
    manifest_asset = next(
        (
            asset
            for asset in _assets(release)
            if asset.get("name") == "datasets-v2.json"
        ),
        None,
    )
    if manifest_asset is None:
        raise SyncError("release is missing datasets-v2.json")
    url = manifest_asset.get("browser_download_url")
    if not isinstance(url, str) or not url:
        raise SyncError("datasets-v2.json has no browser download URL")
    data = _get(url, binary=True)
    digest = sha256_bytes(data)
    size = manifest_asset.get("size")
    if isinstance(size, int) and size != len(data):
        raise SyncError("GitHub asset size mismatch for datasets-v2.json")
    github_digest = manifest_asset.get("digest")
    if github_digest is not None and github_digest != f"sha256:{digest}":
        raise SyncError("GitHub digest mismatch for datasets-v2.json")
    try:
        manifest = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SyncError(f"invalid datasets-v2.json: {exc}") from exc
    if not isinstance(manifest, dict):
        raise SyncError("datasets-v2.json is not an object")
    return manifest, digest


def _eligible(
    release: Mapping[str, object], *, allow_draft: bool, allow_prerelease: bool
) -> bool:
    return not (
        (release.get("draft") and not allow_draft)
        or (release.get("prerelease") and not allow_prerelease)
    )


def sync_releases(
    releases: Iterable[Mapping[str, object]],
    catalog: Mapping[str, object],
    *,
    config: object | None = None,
    skip_tags: set[str] | None = None,
    allow_draft: bool = False,
    allow_prerelease: bool = False,
) -> dict[str, object]:
    result = dict(catalog)
    errors: list[str] = []
    skipped = skip_tags or set()
    for release in releases:
        tag = str(release.get("tag_name", ""))
        if tag in skipped or not _eligible(
            release, allow_draft=allow_draft, allow_prerelease=allow_prerelease
        ):
            continue
        try:
            manifest, manifest_sha = fetch_manifest(release)
            enriched_release = dict(release)
            enriched_release["_manifest_sha256"] = manifest_sha
            entries = release_entries(enriched_release, manifest, config=config)  # type: ignore[arg-type]
            result = merge_entries(result, entries, config=config)  # type: ignore[arg-type]
        except (CatalogError, SyncError, OSError, ValueError) as exc:
            if tag in skipped:
                continue
            errors.append(f"{tag or '<untagged>'}: {exc}")
    if errors:
        raise SyncError(
            "invalid releases:\n" + "\n".join(f"- {error}" for error in errors)
        )
    return result


def sync_catalog(
    *,
    release_tags: Iterable[str] = (),
    all_releases: bool = False,
    catalog_path: Path = Path("catalog/datasets.json"),
    repository: str = REPOSITORY,
    skip_tags: set[str] | None = None,
    allow_draft: bool = False,
    allow_prerelease: bool = False,
) -> dict[str, object]:
    if all_releases and tuple(release_tags):
        raise SyncError("--all cannot be combined with --release-tag")
    releases: list[Mapping[str, object]]
    if all_releases:
        releases = fetch_releases(repository=repository)
    else:
        releases = [fetch_release(tag, repository=repository) for tag in release_tags]
        for release in releases:
            if not _eligible(
                release, allow_draft=allow_draft, allow_prerelease=allow_prerelease
            ):
                tag = release.get("tag_name", "<untagged>")
                raise SyncError(
                    f"release {tag!r} is draft or prerelease; "
                    "pass an explicit allow flag for test synchronization"
                )
    if catalog_path.is_file():
        catalog = load_catalog(catalog_path)
    else:
        catalog = empty_catalog()
    effective_skip_tags = set(skip_tags or ())
    if all_releases:
        effective_skip_tags.update(DEFAULT_HISTORICAL_SKIP_TAGS)
    return sync_releases(
        releases,
        catalog,
        skip_tags=effective_skip_tags,
        allow_draft=allow_draft,
        allow_prerelease=allow_prerelease,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Synchronize catalog/datasets.json.")
    parser.add_argument(
        "--release-tag", action="append", default=[], dest="release_tags"
    )
    parser.add_argument("--all", action="store_true", dest="all_releases")
    parser.add_argument(
        "--skip-release-tag", action="append", default=[], dest="skip_tags"
    )
    parser.add_argument("--catalog", type=Path, default=Path("catalog/datasets.json"))
    parser.add_argument("--repository", default=REPOSITORY)
    parser.add_argument("--allow-draft", action="store_true")
    parser.add_argument("--allow-prerelease", action="store_true")
    parser.add_argument("--update", action="store_true")
    args = parser.parse_args()
    if not args.all_releases and not args.release_tags:
        parser.error("one of --release-tag or --all is required")
    try:
        catalog = sync_catalog(
            release_tags=args.release_tags,
            all_releases=args.all_releases,
            catalog_path=args.catalog,
            repository=args.repository,
            skip_tags=set(args.skip_tags),
            allow_draft=args.allow_draft,
            allow_prerelease=args.allow_prerelease,
        )
        if args.update:
            serialized = (
                json.dumps(catalog, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
            )
            if (
                not args.catalog.is_file()
                or args.catalog.read_text(encoding="utf-8") != serialized
            ):
                write_catalog(args.catalog, catalog)
        print(json.dumps(catalog, indent=2, sort_keys=True, ensure_ascii=False))
    except (CatalogError, SyncError, OSError, ValueError) as exc:
        print(f"catalog synchronization failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
