from pathlib import Path

import pytest

from scripts.build_release import BuildError, resolve_selection
from scripts.config import load_config


def test_resolve_selection_defaults_to_enabled_languages_and_configured_variants() -> (
    None
):
    languages, variants = resolve_selection(load_config())
    assert languages == ("cs", "de", "en", "es", "fr", "it", "pt")
    assert variants == ("lexical", "runtime", "dictionary", "rich")


def test_resolve_selection_rejects_disabled_and_unknown_values(tmp_path: Path) -> None:
    config = load_config()
    with pytest.raises(BuildError, match="unknown languages"):
        resolve_selection(config, languages="xx")
    with pytest.raises(BuildError, match="unknown variants"):
        resolve_selection(config, variants="unknown")
