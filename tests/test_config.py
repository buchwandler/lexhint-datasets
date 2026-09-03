from pathlib import Path

import pytest

from scripts.config import CAPABILITY_ORDER, SUPPORTED_BASE_LANGUAGES, load_config

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
    assert config.source_policy.require_sha256_on_publish is True
    assert config.variants["lexical"].capabilities == ("lexical",)
    assert config.variants["runtime"].capabilities == CAPABILITY_ORDER[:2]
    assert config.variants["dictionary"].capabilities == CAPABILITY_ORDER[:3]
    assert config.variants["rich"].capabilities == CAPABILITY_ORDER
    assert config.variants["runtime"].recommended is True
    assert config.default_release_variants == ("lexical", "runtime", "dictionary")


def test_validation_settings_are_configurable() -> None:
    config = load_config(ROOT / "datasets.toml")

    assert config.languages["en"].validation.probe_word == "house"
    assert config.languages["en"].validation.min_lexemes == 1
    assert config.languages["de"].validation.probe_word == "Haus"


def test_every_enabled_language_has_source() -> None:
    config = load_config(ROOT / "datasets.toml")

    assert all(language.source for language in config.enabled_languages)


def test_language_sources_use_expected_wiktionary_editions() -> None:
    config = load_config(ROOT / "datasets.toml")
    expected = {
        "cs": "cswiktionary",
        "de": "dewiktionary",
        "en": "enwiktionary",
        "es": "eswiktionary",
        "fr": "frwiktionary",
        "it": "itwiktionary",
        "ja": "jawiktionary",
        "ko": "kowiktionary",
        "pt": "ptwiktionary",
        "ru": "ruwiktionary",
        "th": "thwiktionary",
        "vi": "viwiktionary",
        "zh": "zhwiktionary",
    }

    assert {
        code: config.languages[code].source.edition for code in expected
    } == expected


def test_german_source_is_dewiktionary_not_dictionary() -> None:
    config = load_config(ROOT / "datasets.toml")
    source = config.languages["de"].source

    assert source.edition == "dewiktionary"
    assert source.url == "https://kaikki.org/dewiktionary/raw-wiktextract-data.jsonl.gz"
    assert "/dictionary/" not in source.url


def test_spanish_source_is_eswiktionary() -> None:
    config = load_config(ROOT / "datasets.toml")

    assert config.languages["es"].source.edition == "eswiktionary"
    assert "/eswiktionary/" in config.languages["es"].source.url


def test_missing_language_source_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "datasets.toml"
    path.write_text(
        """manifest_version = 2
default_variant = "runtime"

[source]
require_sha256_on_publish = true

[variants.runtime]
capabilities = ["lexical"]

[languages.en]
enabled = true
""",
        encoding="utf-8",
    )

    with pytest.raises(
        (TypeError, ValueError), match="languages.en.source must be a table"
    ):
        load_config(path)


def test_invalid_variant_without_lexical_capability_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "datasets.toml"
    path.write_text(
        """manifest_version = 2
default_variant = "runtime"

[source]
url = "source"
label = "snapshot"

[variants.runtime]
capabilities = ["semantic"]

[languages.en]
enabled = true
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must include lexical"):
        load_config(path)


def test_invalid_default_release_variants_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "datasets.toml"
    text = (ROOT / "datasets.toml").read_text(encoding="utf-8")
    path.write_text(
        text.replace(
            'default_variants = ["lexical", "runtime", "dictionary"]',
            'default_variants = ["lexical", "lexical"]',
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must not contain duplicates"):
        load_config(path)
