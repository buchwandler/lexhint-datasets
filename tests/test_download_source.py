import hashlib
from pathlib import Path

import pytest

from scripts.download_source import SourceError, download_source, verify_sha256


def test_download_source_copies_local_file_and_verifies_hash(tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"source bytes")
    expected = hashlib.sha256(source.read_bytes()).hexdigest()

    output = download_source(
        source.as_uri(), tmp_path / "build" / "source.bin", expected_sha256=expected
    )

    assert output.read_bytes() == source.read_bytes()
    assert verify_sha256(output, expected) == expected


def test_download_source_requires_hash_when_requested(tmp_path: Path) -> None:
    with pytest.raises(SourceError, match="SHA-256 is required"):
        download_source("file:///missing", tmp_path / "source.bin", require_sha256=True)


def test_download_source_rejects_mismatched_hash(tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"source bytes")

    with pytest.raises(SourceError, match="SHA-256 mismatch"):
        download_source(
            source.as_uri(), tmp_path / "copy.bin", expected_sha256="0" * 64
        )

    assert not (tmp_path / "copy.bin").exists()


def test_download_source_without_expected_hash_reports_actual_digest(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"source bytes")
    output = download_source(source.as_uri(), tmp_path / "copy.bin")
    assert output.is_file()
    assert (
        hashlib.sha256(output.read_bytes()).hexdigest()
        == hashlib.sha256(b"source bytes").hexdigest()
    )


def test_download_source_rejects_invalid_expected_hash(tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"source bytes")
    with pytest.raises(SourceError, match="64 hexadecimal"):
        download_source(source.as_uri(), tmp_path / "copy.bin", expected_sha256="bad")
