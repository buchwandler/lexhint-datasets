import gzip
import json
from pathlib import Path

import pytest

from scripts.build_release import BuildError, _build_variant_command, resolve_selection
from scripts.config import load_config
from scripts.split_source import split_source


def test_configuration_exposes_36_english_source_variants() -> None:
    config = load_config()
    assert len(config.languages) == 41
    assert (
        sum("english" in config.source_variants_for(code) for code in config.languages)
        == 36
    )
    assert config.source_for("de", "native").wiktionary_edition == "dewiktionary"
    assert config.source_for("de", "english").wiktionary_edition == "enwiktionary"
    assert config.source_for("de", "english").metadata_language == "en"
    assert config.source_for("ceb", "english").page_url.endswith("/Cebuano/")
    assert config.source_variants_for("en") == ("native",)
    english_defaults = {
        "cs",
        "de",
        "el",
        "es",
        "fr",
        "it",
        "ja",
        "ko",
        "pl",
        "pt",
        "ru",
        "tr",
        "vi",
        "zh",
    }
    assert {
        code
        for code in english_defaults
        if config.default_source_variant_for(code) == "english"
    } == english_defaults
    assert {
        code
        for code in ("en", "id", "ku", "ms", "th")
        if config.default_source_variant_for(code) == "native"
    } == {"en", "id", "ku", "ms", "th"}


def test_selection_rejects_unconfigured_native_source() -> None:
    with pytest.raises(BuildError, match="not configured"):
        resolve_selection(load_config(), language="ceb", source_variant="native")


def test_build_command_propagates_source_provenance() -> None:
    command = _build_variant_command(
        load_config().variant("runtime"),
        lexhint_command="lexhint",
        language="de",
        source=Path("de.jsonl.gz"),
        output=Path("de.sqlite3"),
        no_frequency=True,
        source_variant="english",
        source_edition="enwiktionary",
        source_metadata_language="en",
    )
    assert command[command.index("--source-variant") + 1] == "english"
    assert command[command.index("--source-edition") + 1] == "enwiktionary"
    assert command[command.index("--source-metadata-language") + 1] == "en"


def test_split_manifest_records_source_variant_and_metadata(tmp_path: Path) -> None:
    source = tmp_path / "raw.jsonl"
    source.write_text(
        json.dumps({"lang_code": "de", "word": "Haus"})
        + "\n"
        + json.dumps({"lang_code": "en", "word": "house"})
        + "\n",
        encoding="utf-8",
    )
    manifest = split_source(
        source,
        tmp_path / "split",
        ("de",),
        source_variant="english",
        wiktionary_edition="enwiktionary",
        metadata_language="en",
    )
    assert manifest["source_variant"] == "english"
    assert manifest["wiktionary_edition"] == "enwiktionary"
    assert manifest["metadata_language"] == "en"
    with gzip.open(
        tmp_path / "split" / "de.jsonl.gz", "rt", encoding="utf-8"
    ) as handle:
        assert json.loads(handle.readline())["lang_code"] == "de"
