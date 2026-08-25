from __future__ import annotations

import json
from pathlib import Path

import pytest
from lexhint import HeadwordRelation, Lexicon
from lexhint.builder import build_dictionary
from lexhint.lexicon import LexiconCapabilityError
from lexhint.status import read_artifact_status

from scripts.validate import validate


def relation_source(path: Path) -> Path:
    path.write_text(
        "\n".join(
            json.dumps(value)
            for value in (
                {
                    "word": "color",
                    "lang_code": "en",
                    "pos": "noun",
                    "redirects": ["colour"],
                    "senses": [{"glosses": ["A hue."]}],
                },
                {
                    "word": "colours",
                    "lang_code": "en",
                    "pos": "noun",
                    "senses": [
                        {"glosses": ["Plural hue."], "form_of": [{"word": "color"}]}
                    ],
                },
                {
                    "word": "colour",
                    "lang_code": "en",
                    "pos": "noun",
                    "senses": [
                        {
                            "glosses": ["Alternative spelling."],
                            "alt_of": [{"word": "color", "tags": ["UK"]}],
                        }
                    ],
                },
            )
        )
        + "\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def artifacts(tmp_path: Path) -> dict[str, Path]:
    source = relation_source(tmp_path / "relations.jsonl")
    result: dict[str, Path] = {}
    for name, kwargs in {
        "lexical": {"capabilities": "lexical"},
        "runtime": {"profile": "runtime"},
        "dictionary": {"capabilities": "lexical,semantic,dictionary"},
        "rich": {"profile": "rich"},
    }.items():
        path, _ = build_dictionary(
            "en",
            source,
            output=tmp_path / f"{name}.sqlite3",
            no_frequency=True,
            **kwargs,
        )
        result[name] = path
    return result


def test_relations_are_only_in_dictionary_capable_variants(
    artifacts: dict[str, Path],
) -> None:
    statuses = {
        name: read_artifact_status(path=path) for name, path in artifacts.items()
    }

    assert statuses["lexical"].counts["relations"] is None
    assert statuses["runtime"].counts["relations"] is None
    assert statuses["dictionary"].counts["relations"] == 3
    assert statuses["rich"].counts["relations"] == 3

    with pytest.raises(LexiconCapabilityError):
        Lexicon.from_path(artifacts["runtime"]).relations("colour")

    dictionary = Lexicon.from_path(artifacts["dictionary"])
    assert dictionary.relations("colour") == (
        HeadwordRelation("colour", "color", "alternative", ("UK",)),
    )
    assert dictionary.resolve_headword("colours") == ("color",)

    rich = Lexicon.from_path(artifacts["rich"])
    assert rich.resolve_headword("colours") == ("color",)


def test_validator_supports_relation_count_and_behavior_probes(
    artifacts: dict[str, Path],
) -> None:
    result = validate(
        artifacts["dictionary"],
        language="en",
        variant="dictionary",
        probe_word="colour",
        min_lexemes=1,
        min_relations=3,
        relation_probe_word="colour",
        relation_probe_target="color",
    )

    assert result["counts"]["relations"] == 3
