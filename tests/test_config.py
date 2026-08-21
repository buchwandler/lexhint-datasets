from pathlib import Path

import pytest

from scripts.config import (
    CAPABILITY_ORDER,
    SUPPORTED_BASE_LANGUAGES,
    load_config,
)

ROOT = Path(__file__).parents[1]


def test_release_configuration_defines_supported_languages_and_variants() -> None:
    config = load_config(ROOT / "datasets.toml")

    assert config.manifest_version == 2
    assert tuple(config.languages) == SUPPORTED_BASE_LANGUAGES
    assert (
        tuple(language.code for language in config.enabled_languages)
        == SUPPORTED_BASE_LANGUAGES
    )
    assert config.default_variant == "runtime"
    assert config.source.require_sha256_on_publish is True
    assert config.variants["lexical"].capabilities == ("lexical",)
    assert config.variants["runtime"].capabilities == CAPABILITY_ORDER[:2]
    assert config.variants["rich"].capabilities == CAPABILITY_ORDER
    assert config.variants["runtime"].recommended is True


def test_validation_settings_are_configurable() -> None:
    config = load_config(ROOT / "datasets.toml")

    assert config.languages["en"].validation.probe_word == "house"
    assert config.languages["en"].validation.min_lexemes == 1
    assert config.languages["de"].validation.probe_word == "Haus"


def test_invalid_variant_without_lexical_capability_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "datasets.toml"
    path.write_text(
        """manifest_version = 2
default_variant = \"runtime\"\n
[source]
url = \"source\"
label = \"snapshot\"

[variants.runtime]
capabilities = [\"semantic\"]

[languages.en]
enabled = true
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must include lexical"):
        load_config(path)
