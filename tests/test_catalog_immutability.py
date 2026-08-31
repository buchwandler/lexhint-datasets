from __future__ import annotations

from copy import deepcopy

import pytest
from test_catalog import _release

from scripts.catalog import CatalogError, empty_catalog, merge_entries, release_entries
from scripts.check_catalog_immutability import check_catalog_immutability


def _catalog() -> dict[str, object]:
    release, manifest = _release("de")
    return merge_entries(empty_catalog(), release_entries(release, manifest))


@pytest.mark.parametrize(
    "path",
    [
        ("asset", "url"),
        ("asset", "name"),
        ("asset", "sha256"),
        ("asset", "compressed_size"),
        ("schema_version",),
        ("language",),
        ("variant",),
        ("dataset_version",),
    ],
)
def test_published_release_immutable_fields_cannot_change(
    path: tuple[str, ...],
) -> None:
    base = _catalog()
    proposed = deepcopy(base)
    target: object = proposed["artifacts"][0]
    for key in path[:-1]:
        target = target[key]  # type: ignore[index]
    target[path[-1]] = "changed"  # type: ignore[index]
    with pytest.raises(CatalogError, match="changed immutable"):
        check_catalog_immutability(base, proposed)


def test_new_release_tag_can_add_new_entry() -> None:
    base = _catalog()
    release, manifest = _release("de", version="2026.09.01")
    proposed = merge_entries(base, release_entries(release, manifest))
    check_catalog_immutability(base, proposed)
    assert len(proposed["artifacts"]) == 2
