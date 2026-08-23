from __future__ import annotations

import pytest
from lexhint import SCHEMA_VERSION, datasets


def _artifact(version: str, schema: str) -> datasets.DatasetArtifact:
    return datasets.DatasetArtifact(
        "en",
        "runtime",
        version,
        f"data-{version}",
        "",
        2,
        schema,
        "runtime",
        "full",
        ("lexical", "semantic"),
        1,
        1,
        f"lexhint-en-runtime-s{schema}-{version}.sqlite3.gz",
        "a" * 64,
        "https://example.test/asset",
    )


def test_release_history_keeps_newest_compatible_schema_family(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old = _artifact("2026.08.20", SCHEMA_VERSION)
    newest_compatible = _artifact("2026.09.01", SCHEMA_VERSION)
    newer_schema = _artifact(
        "2026.10.01",
        str(int(SCHEMA_VERSION) + 1),
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

    assert datasets._remote_artifacts(language="en", variant="runtime") == (
        newest_compatible,
    )
