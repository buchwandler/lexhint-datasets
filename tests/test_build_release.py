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


def test_release_selection_requires_one_language() -> None:
    config = load_config()

    with pytest.raises(BuildError, match="exactly one language"):
        resolve_selection(config, language=None)
    with pytest.raises(BuildError, match="exactly one language"):
        resolve_selection(config, language="en,de")


def test_release_selection_accepts_explicit_language_and_default_variants() -> None:
    language, variants = resolve_selection(load_config(), language="de")

    assert language == "de"
    assert variants == ("lexical", "runtime", "dictionary")


def test_release_selection_rejects_unknown_language() -> None:
    with pytest.raises(BuildError, match="unknown language"):
        resolve_selection(load_config(), language="xx")


def test_release_selection_rejects_disabled_language() -> None:
    config = load_config()
    languages = dict(config.languages)
    languages["de"] = replace(languages["de"], enabled=False)
    config = replace(config, languages=languages)

    with pytest.raises(BuildError, match="disabled language"):
        resolve_selection(config, language="de")


def test_release_selection_rejects_unknown_variant() -> None:
    with pytest.raises(BuildError, match="unknown variants"):
        resolve_selection(load_config(), language="en", variants="unknown")


def test_explicit_rich_selection_is_allowed() -> None:
    _, variants = resolve_selection(load_config(), language="en", variants="rich")
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
