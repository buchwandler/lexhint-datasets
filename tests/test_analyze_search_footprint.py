from pathlib import Path

from lexhint.builder import build_dictionary

from scripts.analyze_search_footprint import analyze, analyze_database

FIXTURE = (
    Path(__file__).parents[2] / "lexhint" / "tests" / "fixtures" / "kaikki-rich.jsonl"
)


def build_rich(tmp_path: Path) -> Path:
    path, _ = build_dictionary(
        "en",
        FIXTURE,
        output=tmp_path / "rich.sqlite3",
        no_frequency=True,
        profile="rich",
    )
    return path


def test_analyzer_reports_required_objects_fields_and_stable_gzip(tmp_path: Path) -> None:
    database = build_rich(tmp_path)
    first = analyze_database(database)
    second = analyze_database(database)

    assert first["database_raw_bytes"] == database.stat().st_size
    assert first["database_gzip_bytes"] == second["database_gzip_bytes"]
    assert first["row_counts"]["lexemes"] == 1
    assert first["row_counts"]["lexeme_ngrams"] > 0
    assert first["row_counts"]["sense_search_terms"] > 0
    assert "sense_search_terms" in first["dbstat_bytes_by_object"]
    assert "search_index_version" in first["search_metadata"]
    assert "glosses" in first["sense_search_terms_by_field"]


def test_experiments_are_disposable_and_report_narrowed_footprints(tmp_path: Path) -> None:
    database = build_rich(tmp_path)
    original = database.read_bytes()
    result = analyze(database, experiments_dir=tmp_path / "experiments")

    experiments = result["experiments"]
    assert set(experiments) == {
        "full_current_search",
        "no_dictionary_text_index",
        "gloss_only",
        "glosses_plus_synonyms",
        "no_headword_fuzzy_index",
    }
    assert experiments["no_dictionary_text_index"]["row_counts"]["sense_search_terms"] == 0
    assert set(experiments["gloss_only"]["sense_search_terms_by_field"]) == {"glosses"}
    assert set(experiments["glosses_plus_synonyms"]["sense_search_terms_by_field"]) <= {
        "glosses",
        "synonyms",
    }
    assert experiments["no_headword_fuzzy_index"]["row_counts"]["lexeme_ngrams"] == 0
    assert database.read_bytes() == original
    assert all((tmp_path / "experiments" / f"{name}.sqlite3").is_file() for name in experiments if name != "full_current_search")
