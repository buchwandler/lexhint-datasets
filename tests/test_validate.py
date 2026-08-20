from pathlib import Path

import pytest
from lexhint.builder import build_dictionary
from lexhint.status import read_artifact_status

from scripts.validate import ValidationError, validate

FIXTURE = (
    Path(__file__).parents[2] / "lexhint" / "tests" / "fixtures" / "kaikki-rich.jsonl"
)


@pytest.fixture
def artifacts(tmp_path: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for name, kwargs in {
        "lexical": {"capabilities": "lexical"},
        "runtime": {"profile": "runtime"},
        "rich": {"profile": "rich"},
    }.items():
        path, _ = build_dictionary(
            "en",
            FIXTURE,
            output=tmp_path / f"{name}.sqlite3",
            no_frequency=True,
            **kwargs,
        )
        result[name] = path
    return result


def test_schema_seven_variants_validate_through_lexhint(
    artifacts: dict[str, Path],
) -> None:
    lexical = validate(
        artifacts["lexical"],
        language="en",
        variant="lexical",
        probe_word="love",
        min_lexemes=1,
    )
    runtime = validate(
        artifacts["runtime"],
        language="en",
        variant="runtime",
        min_lexemes=1,
    )
    rich = validate(
        artifacts["rich"],
        language="en",
        variant="rich",
        probe_word="love",
        min_lexemes=1,
        min_entries=1,
        min_senses=1,
    )

    assert lexical["schema_version"] == "7"
    assert lexical["capabilities"] == ("lexical",)
    assert runtime["capabilities"] == ("lexical", "semantic")
    assert rich["capabilities"] == ("lexical", "semantic", "dictionary")
    assert rich["counts"]["entries"] > 0


def test_validator_rejects_wrong_variant_and_missing_probe(
    artifacts: dict[str, Path],
) -> None:
    with pytest.raises(ValidationError, match="capabilities mismatch"):
        validate(artifacts["lexical"], language="en", variant="rich")

    with pytest.raises(ValidationError, match="lexical probe"):
        validate(artifacts["rich"], language="en", variant="rich", probe_word="missing")


def test_validator_preserves_missing_optional_counts(
    artifacts: dict[str, Path],
) -> None:
    status = read_artifact_status(path=artifacts["runtime"])

    assert status.counts["entries"] is None
    result = validate(artifacts["runtime"], language="en", variant="runtime")
    assert result["counts"]["entries"] is None

    with pytest.raises(ValidationError, match="entries count is unavailable"):
        validate(artifacts["runtime"], language="en", variant="runtime", min_entries=1)
