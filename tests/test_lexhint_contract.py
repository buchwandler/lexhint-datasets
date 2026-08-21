from pathlib import Path

import pytest

from scripts.config import load_config
from scripts.verify_lexhint_contract import ContractError, verify_contract

ROOT = Path(__file__).parents[1]


def test_installed_lexhint_contract_matches_dataset_configuration() -> None:
    result = verify_contract(load_config(ROOT / "datasets.toml"))

    assert result["schema_version"] == "7"
    assert result["variants"] == {
        "lexical": ["lexical"],
        "runtime": ["lexical", "semantic"],
        "rich": ["lexical", "semantic", "dictionary"],
    }
    assert result["default_variant"] == "runtime"
    assert result["base_languages"] == ["cs", "de", "en", "es", "fr", "it", "pt"]


def test_contract_rejects_variant_capability_mismatch(tmp_path: Path) -> None:
    config_path = tmp_path / "datasets.toml"
    config_path.write_text(
        (ROOT / "datasets.toml")
        .read_text(encoding="utf-8")
        .replace(
            'capabilities = ["lexical", "semantic", "dictionary"]',
            'capabilities = ["lexical", "semantic"]',
        ),
        encoding="utf-8",
    )

    with pytest.raises(ContractError, match="rich.*capabilities mismatch"):
        verify_contract(load_config(config_path))


def test_config_rejects_regional_language_builds(tmp_path: Path) -> None:
    config_path = tmp_path / "datasets.toml"
    config_path.write_text(
        (ROOT / "datasets.toml").read_text(encoding="utf-8")
        + "\n[languages.en-US]\nenabled = true\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unsupported base language"):
        load_config(config_path)
