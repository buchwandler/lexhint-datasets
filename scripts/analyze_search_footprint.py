#!/usr/bin/env python3
"""Measure SQLite search footprint without modifying the source artifact."""

from __future__ import annotations

import argparse
import gzip
import io
import json
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

ROW_TABLES = (
    "lexemes",
    "lexeme_ngrams",
    "entries",
    "senses",
    "sense_topics",
    "sense_search_terms",
)
EXPERIMENTS = {
    "no_dictionary_text_index": "DELETE FROM sense_search_terms",
    "gloss_only": "DELETE FROM sense_search_terms WHERE field <> 'glosses'",
    "glosses_plus_synonyms": (
        "DELETE FROM sense_search_terms WHERE field NOT IN ('glosses', 'synonyms')"
    ),
    "no_headword_fuzzy_index": "DELETE FROM lexeme_ngrams",
}


class FootprintError(RuntimeError):
    """The SQLite artifact could not be analyzed."""


def _metadata(connection: sqlite3.Connection) -> dict[str, str]:
    try:
        rows = connection.execute("SELECT key, value FROM metadata").fetchall()
    except sqlite3.DatabaseError as exc:
        raise FootprintError(f"metadata could not be read: {exc}") from exc
    return {str(key): str(value) for key, value in rows}


def _table_names(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    return {str(row[0]) for row in rows}


def _count(connection: sqlite3.Connection, table: str, tables: set[str]) -> int:
    if table not in tables:
        return 0
    return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def _field_stats(
    connection: sqlite3.Connection, tables: set[str]
) -> dict[str, dict[str, int]]:
    if "sense_search_terms" not in tables:
        return {}
    rows = connection.execute(
        "SELECT field, COUNT(*), COALESCE(SUM(term_count), 0), COUNT(DISTINCT term) "
        "FROM sense_search_terms GROUP BY field ORDER BY field"
    ).fetchall()
    return {
        str(field): {
            "rows": int(row_count),
            "source_token_count": int(token_count),
            "distinct_terms": int(distinct_terms),
        }
        for field, row_count, token_count, distinct_terms in rows
    }


def _object_bytes(connection: sqlite3.Connection) -> dict[str, int]:
    try:
        rows = connection.execute(
            "SELECT name, SUM(pgsize) FROM dbstat GROUP BY name ORDER BY name"
        ).fetchall()
    except sqlite3.DatabaseError as exc:
        raise FootprintError(f"SQLite dbstat is unavailable: {exc}") from exc
    return {str(name): int(size) for name, size in rows}


def _gzip_size(path: Path) -> int:
    buffer = io.BytesIO()
    with (
        path.open("rb") as source,
        gzip.GzipFile(
            filename="", mode="wb", fileobj=buffer, compresslevel=9, mtime=0
        ) as target,
    ):
        shutil.copyfileobj(source, target)
    return len(buffer.getvalue())


def analyze_database(path: str | Path) -> dict[str, Any]:
    artifact = Path(path)
    if not artifact.is_file():
        raise FootprintError(f"database not found: {artifact}")
    try:
        with closing(sqlite3.connect(artifact)) as connection:
            metadata = _metadata(connection)
            tables = _table_names(connection)
            row_counts = {
                table: _count(connection, table, tables) for table in ROW_TABLES
            }
            return {
                "path": str(artifact),
                "database_raw_bytes": artifact.stat().st_size,
                "database_gzip_bytes": _gzip_size(artifact),
                "dbstat_bytes_by_object": _object_bytes(connection),
                "row_counts": row_counts,
                "sense_search_terms_by_field": _field_stats(connection, tables),
                "metadata": metadata,
                "search_metadata": {
                    key: value
                    for key, value in metadata.items()
                    if key == "search_index_version" or key.startswith("search_")
                },
            }
    except sqlite3.DatabaseError as exc:
        raise FootprintError(f"SQLite artifact could not be read: {exc}") from exc


def _experiment_copy(source: Path, destination: Path, statement: str) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    try:
        with closing(sqlite3.connect(destination)) as connection:
            tables = _table_names(connection)
            target = (
                "sense_search_terms"
                if "sense_search_terms" in statement
                else "lexeme_ngrams"
            )
            if target not in tables:
                raise FootprintError(f"experiment table is missing: {target}")
            connection.execute(statement)
            connection.commit()
            connection.execute("VACUUM")
            connection.commit()
    except sqlite3.DatabaseError as exc:
        raise FootprintError(
            f"experiment failed for {destination.name}: {exc}"
        ) from exc
    result = analyze_database(destination)
    result.pop("path", None)
    return result


def analyze(
    path: str | Path, *, experiments_dir: str | Path | None = None
) -> dict[str, Any]:
    source = Path(path)
    result = analyze_database(source)
    if experiments_dir is None:
        return result
    destination = Path(experiments_dir)
    destination.mkdir(parents=True, exist_ok=True)
    experiments: dict[str, dict[str, Any]] = {
        "full_current_search": {
            "database_raw_bytes": result["database_raw_bytes"],
            "database_gzip_bytes": result["database_gzip_bytes"],
        }
    }
    for name, statement in EXPERIMENTS.items():
        experiments[name] = _experiment_copy(
            source, destination / f"{name}.sqlite3", statement
        )
    result["experiments"] = experiments
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze Lexhint SQLite search storage and optional disposable copies."
    )
    parser.add_argument("database", type=Path)
    parser.add_argument(
        "--experiments-dir",
        type=Path,
        help="create disposable experiment copies in this directory",
    )
    args = parser.parse_args()
    try:
        print(
            json.dumps(
                analyze(args.database, experiments_dir=args.experiments_dir), indent=2
            )
        )
    except (FootprintError, OSError, sqlite3.DatabaseError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
