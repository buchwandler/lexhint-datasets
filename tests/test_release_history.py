from __future__ import annotations

import pytest

from lexhint import SCHEMA_VERSION, datasets


def _artifact(
    language: str, version: str, schema: str, release_tag: str
) -> datasets.DatasetArtifact:
    return datasets.DatasetArtifact(
        language,
        "runtime",
        version,
        release_tag,
        "",
        2,
        schema,
        "runtime",
        "full",
        ("lexical", "semantic"),
        1,
        1,
        f"lexhint-{language}-runtime-s{schema}-{version}.sqlite3.gz",
        "a" * 64,
        "https://example.test/asset",
    )


def test_release_history_keeps_newest_compatible_schema_family(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old = _artifact("en", "2026.08.20", SCHEMA_VERSION, "data-2026.08.20")
    newest_compatible = _artifact("en", "2026.09.01", SCHEMA_VERSION, "data-2026.09.01")
    newer_schema = _artifact(
        "en", "2026.10.01", str(int(SCHEMA_VERSION) + 1), "data-2026.10.01"
    )
    releases = [
        {"tag_name": newer_schema.release_tag},
        {"tag_name": newest_compatible.release_tag},
        {"tag_name": old.release_tag},
    ]
    manifests = {
        newer_schema.release_tag: (newer_schema,),
        newest_compatible.release_tag: (newest_compatible,),
        old.release_tag: (old,),
    }
    monkeypatch.setattr(datasets, "_releases", lambda version: releases)
    monkeypatch.setattr(
        datasets,
        "_manifest_for_release",
        lambda release: manifests[release["tag_name"]],
    )
    monkeypatch.setattr(
        datasets,
        "_catalog_remote_artifacts",
        lambda **kwargs: (_ for _ in ()).throw(
            datasets._DatasetCatalogTransportError("test")
        ),
    )

    assert datasets._remote_artifacts(language="en", variant="runtime") == (
        newest_compatible,
    )


def test_explicit_language_version_prefers_qualified_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    qualified = _artifact("de", "2026.08.31", SCHEMA_VERSION, "data-de-2026.08.31")
    calls: list[str | None] = []
    monkeypatch.setattr(
        datasets,
        "_releases",
        lambda version: calls.append(version) or [{"tag_name": qualified.release_tag}],
    )
    monkeypatch.setattr(datasets, "_manifest_for_release", lambda release: (qualified,))

    assert datasets._remote_artifacts(language="de", version="2026.08.31") == (
        qualified,
    )
    assert calls == ["data-de-2026.08.31"]


def test_explicit_language_version_falls_back_to_legacy_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy = _artifact("de", "2026.08.25", SCHEMA_VERSION, "data-2026.08.25")
    calls: list[str | None] = []

    def releases(version: str | None) -> list[dict[str, object]]:
        calls.append(version)
        if version == "data-de-2026.08.25":
            raise datasets.DatasetNotFound("missing")
        return [{"tag_name": legacy.release_tag}]

    monkeypatch.setattr(datasets, "_releases", releases)
    monkeypatch.setattr(datasets, "_manifest_for_release", lambda release: (legacy,))

    assert datasets._remote_artifacts(language="de", version="2026.08.25") == (legacy,)
    assert calls == ["data-de-2026.08.25", "data-2026.08.25"]


def test_catalog_listing_aggregates_language_releases_independently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    de = _artifact("de", "2026.08.31", SCHEMA_VERSION, "data-de-2026.08.31")
    en = _artifact("en", "2026.08.31", SCHEMA_VERSION, "data-en-2026.08.31")
    es = _artifact("es", "2026.08.31", SCHEMA_VERSION, "data-es-2026.08.31")
    releases = [{"tag_name": item.release_tag} for item in (de, en, es)]
    manifests = {item.release_tag: (item,) for item in (de, en, es)}
    monkeypatch.setattr(datasets, "_releases", lambda version: releases)
    monkeypatch.setattr(
        datasets,
        "_manifest_for_release",
        lambda release: manifests[release["tag_name"]],
    )

    result = datasets._legacy_remote_artifacts()

    assert {(item.language, item.variant) for item in result} == {
        ("de", "runtime"),
        ("en", "runtime"),
        ("es", "runtime"),
    }


def test_catalog_listing_selects_newest_compatible_schema_per_language(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    de = _artifact("de", "2026.08.31", SCHEMA_VERSION, "data-de-2026.08.31")
    en_old = _artifact("en", "2026.08.30", SCHEMA_VERSION, "data-en-2026.08.30")
    en_newer_schema = _artifact(
        "en", "2026.09.01", str(int(SCHEMA_VERSION) + 1), "data-en-2026.09.01"
    )
    releases = [
        {"tag_name": item.release_tag} for item in (en_newer_schema, de, en_old)
    ]
    manifests = {item.release_tag: (item,) for item in (de, en_old, en_newer_schema)}
    monkeypatch.setattr(datasets, "_releases", lambda version: releases)
    monkeypatch.setattr(
        datasets,
        "_manifest_for_release",
        lambda release: manifests[release["tag_name"]],
    )

    result = datasets._legacy_remote_artifacts()

    assert {(item.language, item.dataset_version) for item in result} == {
        ("de", "2026.08.31"),
        ("en", "2026.08.30"),
    }
