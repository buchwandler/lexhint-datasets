import hashlib
import json
from pathlib import Path

import pytest
from lexhint import SCHEMA_VERSION
from lexhint.builder import build_dictionary

from scripts.package_release import PackagingError, package_artifact, package_release

FIXTURE = (
    Path(__file__).parents[2] / "lexhint" / "tests" / "fixtures" / "kaikki-rich.jsonl"
)


def build_artifacts(tmp_path: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for variant, kwargs in {
        "lexical": {"capabilities": "lexical"},
        "runtime": {"profile": "runtime"},
        "dictionary": {"capabilities": "lexical,semantic,dictionary"},
        "rich": {"profile": "rich"},
    }.items():
        result[variant], _ = build_dictionary(
            "en",
            FIXTURE,
            output=tmp_path / f"en-{variant}.sqlite3",
            no_frequency=True,
            **kwargs,
        )
    return result


def test_package_release_aggregates_three_variants(tmp_path: Path) -> None:
    databases = build_artifacts(tmp_path / "build")
    dist = tmp_path / "dist"
    records = [
        package_artifact(
            database,
            language="en",
            variant=variant,
            dataset_version="2026.08.20",
            output_dir=dist,
        )
        for variant, database in databases.items()
    ]
    manifest = package_release(
        records,
        output_dir=dist,
        dataset_version="2026.08.20",
        lexhint_ref="test",
        lexhint_commit="abc123",
        source_url="file://fixture",
        source_label="fixture",
        attribution=Path(__file__).parents[1] / "DATA_SOURCES.md",
    )

    assert manifest["manifest_version"] == 2
    assert [record["id"] for record in manifest["artifacts"]] == [
        "en/dictionary",
        "en/lexical",
        "en/rich",
        "en/runtime",
    ]
    assert manifest["artifacts"][0]["counts"]["entries"] is not None
    assert (dist / "datasets-v2.json").is_file()
    assert (dist / "ATTRIBUTION.md").is_file()
    assert "English" not in (dist / "release-notes.md").read_text(encoding="utf-8")
    assert (dist / "SHA256SUMS").read_text(encoding="utf-8").count("\n") == 4

    assert manifest["lexhint"]["schema_version"] == SCHEMA_VERSION
    assert manifest["lexhint"]["version"]
    assert all(
        record["schema_version"] == SCHEMA_VERSION for record in manifest["artifacts"]
    )
    assert all(
        f"-s{SCHEMA_VERSION}-" in record["asset"] for record in manifest["artifacts"]
    )
    assert f"require Lexhint schema {SCHEMA_VERSION}" in (
        dist / "release-notes.md"
    ).read_text(encoding="utf-8")


def test_gzip_output_is_stable_for_identical_input(tmp_path: Path) -> None:
    database = build_artifacts(tmp_path / "build")["runtime"]
    first = package_artifact(
        database,
        language="en",
        variant="runtime",
        dataset_version="2026.08.20",
        output_dir=tmp_path / "one",
    )
    second = package_artifact(
        database,
        language="en",
        variant="runtime",
        dataset_version="2026.08.20",
        output_dir=tmp_path / "two",
    )

    first_bytes = (tmp_path / "one" / first["asset"]).read_bytes()
    second_bytes = (tmp_path / "two" / second["asset"]).read_bytes()
    assert first_bytes == second_bytes
    assert first["sha256"] == hashlib.sha256(first_bytes).hexdigest()


def test_release_rejects_duplicate_slots_and_publish_without_source_hash(
    tmp_path: Path,
) -> None:
    database = build_artifacts(tmp_path / "build")["runtime"]
    record = package_artifact(
        database,
        language="en",
        variant="runtime",
        dataset_version="2026.08.20",
        output_dir=tmp_path / "dist",
    )
    with pytest.raises(PackagingError, match="duplicate artifact slot"):
        package_release(
            [record, dict(record)],
            output_dir=tmp_path / "dist",
            dataset_version="2026.08.20",
            lexhint_ref="test",
            lexhint_commit="abc123",
            source_url="file://fixture",
            source_label="fixture",
        )
    with pytest.raises(PackagingError, match="source_sha256 is required"):
        package_release(
            [record],
            output_dir=tmp_path / "publish",
            dataset_version="2026.08.20",
            lexhint_ref="test",
            lexhint_commit="abc123",
            source_url="file://fixture",
            source_label="fixture",
            publish=True,
        )


def test_manifest_is_json_serializable(tmp_path: Path) -> None:
    database = build_artifacts(tmp_path / "build")["lexical"]
    record = package_artifact(
        database,
        language="en",
        variant="lexical",
        dataset_version="2026.08.20",
        output_dir=tmp_path / "dist",
    )
    manifest = package_release(
        [record],
        output_dir=tmp_path / "dist",
        dataset_version="2026.08.20",
        lexhint_ref="test",
        lexhint_commit="abc123",
        source_url="file://fixture",
        source_label="fixture",
    )
    assert json.loads(json.dumps(manifest))["artifacts"][0]["capabilities"] == [
        "lexical"
    ]


def test_release_rejects_schema_and_filename_mismatches(tmp_path: Path) -> None:
    database = build_artifacts(tmp_path / "build")["runtime"]
    record = package_artifact(
        database,
        language="en",
        variant="runtime",
        dataset_version="2026.08.20",
        output_dir=tmp_path / "dist",
    )

    wrong_filename = dict(
        record,
        asset=record["asset"].replace(
            f"-s{SCHEMA_VERSION}-",
            "-s999-",
        ),
    )
    with pytest.raises(PackagingError, match="filename schema mismatch"):
        package_release(
            [wrong_filename],
            output_dir=tmp_path / "wrong-filename",
            dataset_version="2026.08.20",
            lexhint_ref="test",
            lexhint_commit="abc123",
            source_url="file://fixture",
            source_label="fixture",
        )

    wrong_manifest = dict(record, schema_version="999")
    with pytest.raises(PackagingError, match="artifact schema mismatch"):
        package_release(
            [wrong_manifest],
            output_dir=tmp_path / "wrong-manifest",
            dataset_version="2026.08.20",
            lexhint_ref="test",
            lexhint_commit="abc123",
            source_url="file://fixture",
            source_label="fixture",
        )

    with pytest.raises(PackagingError, match="schema mismatch"):
        package_artifact(
            database,
            language="en",
            variant="runtime",
            dataset_version="2026.08.20",
            output_dir=tmp_path / "wrong-database-schema",
            expected_schema="999",
        )
