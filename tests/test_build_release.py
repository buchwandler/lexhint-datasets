from dataclasses import replace
from pathlib import Path

import pytest

from scripts.build_release import (
    BuildError,
    _build_variant_command,
    maximal_variant,
    resolve_selection,
)
from scripts.config import VariantConfig, load_config


def test_resolve_selection_defaults_to_enabled_languages_and_configured_variants() -> (
    None
):
    languages, variants = resolve_selection(load_config())
    assert languages == ("cs", "de", "en", "es", "fr", "it", "pt")
    assert variants == ("lexical", "runtime", "dictionary")


def test_resolve_selection_rejects_disabled_and_unknown_values(tmp_path: Path) -> None:
    config = load_config()
    with pytest.raises(BuildError, match="unknown languages"):
        resolve_selection(config, languages="xx")
    with pytest.raises(BuildError, match="unknown variants"):
        resolve_selection(config, variants="unknown")


def test_explicit_rich_selection_is_allowed() -> None:
    _, variants = resolve_selection(load_config(), variants="rich")
    assert variants == ("rich",)


def test_maximal_variant_uses_capabilities_not_order() -> None:
    config = load_config()
    assert maximal_variant(config, ("lexical", "runtime", "dictionary")) == "dictionary"
    assert maximal_variant(config, ("lexical", "runtime")) == "runtime"


def test_maximal_variant_rejects_incomparable_capabilities() -> None:
    config = load_config()
    variants = {
        "left": VariantConfig("left", ("lexical", "semantic"), None, False),
        "right": VariantConfig("right", ("lexical", "dictionary"), None, False),
    }
    incomparable = replace(config, variants=variants)
    with pytest.raises(BuildError, match="unique maximal capability artifact"):
        maximal_variant(incomparable, ("left", "right"))


def test_build_variant_command_uses_capabilities_or_profile() -> None:
    config = load_config()
    dictionary_command = _build_variant_command(
        config.variant("dictionary"),
        lexhint_command="lexhint",
        language="en",
        source=Path("source.jsonl.gz"),
        output=Path("dictionary.sqlite3"),
        no_frequency=False,
    )
    rich_command = _build_variant_command(
        config.variant("rich"),
        lexhint_command="lexhint",
        language="en",
        source=Path("source.jsonl.gz"),
        output=Path("rich.sqlite3"),
        no_frequency=False,
    )
    assert dictionary_command[-2:] == ["--capabilities", "lexical,semantic,dictionary"]
    assert rich_command[-2:] == ["--profile", "rich"]
