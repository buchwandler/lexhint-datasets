from pathlib import Path
import hashlib
import json

import pytest

from scripts.publish_candidate import CandidateError, verify_candidate


def test_verify_candidate_checks_manifest_and_assets(tmp_path: Path) -> None:
    asset = tmp_path / "lexhint-en-runtime.sqlite3.gz"
    asset.write_bytes(b"candidate")
    digest = hashlib.sha256(asset.read_bytes()).hexdigest()
    (tmp_path / "SHA256SUMS").write_text(f"{digest}  {asset.name}\n", encoding="utf-8")
    (tmp_path / "ATTRIBUTION.md").write_text("attribution\n", encoding="utf-8")
    (tmp_path / "datasets-v2.json").write_text(
        json.dumps(
            {
                "dataset_version": "v1",
                "source": {"sha256": "a" * 64},
                "builder_repository": {"commit": "abc"},
                "artifacts": [
                    {
                        "language": "en",
                        "variant": "runtime",
                        "asset": asset.name,
                        "sha256": digest,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    manifest = verify_candidate(
        tmp_path,
        dataset_version="v1",
        candidate_commit="abc",
        expected_languages={"en"},
        expected_variants={"runtime"},
    )
    assert manifest["dataset_version"] == "v1"


def test_verify_candidate_rejects_checksum_mismatch(tmp_path: Path) -> None:
    (tmp_path / "datasets-v2.json").write_text(
        json.dumps(
            {
                "dataset_version": "v1",
                "source": {"sha256": "a" * 64},
                "builder_repository": {"commit": "abc"},
                "artifacts": [],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "SHA256SUMS").write_text("" + "a" * 64 + "  unused\n", encoding="utf-8")
    (tmp_path / "ATTRIBUTION.md").write_text("x", encoding="utf-8")
    with pytest.raises(CandidateError, match="no artifacts"):
        verify_candidate(tmp_path, dataset_version="v1", candidate_commit="abc")
