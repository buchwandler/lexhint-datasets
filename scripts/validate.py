#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path


def load_metadata(connection: sqlite3.Connection) -> dict[str, str]:
    try:
        rows = connection.execute("SELECT key, value FROM metadata").fetchall()
    except sqlite3.DatabaseError as exc:
        raise RuntimeError(f"metadata table is not readable: {exc}") from exc
    return {str(key): str(value) for key, value in rows}


def senses_for(
    connection: sqlite3.Connection,
    word: str,
) -> list[tuple[str, tuple[str, ...], tuple[str, ...]]]:
    rows = connection.execute(
        """
        SELECT pos, glosses, topics
        FROM senses
        WHERE word = ?
        ORDER BY id
        """,
        (word.casefold(),),
    ).fetchall()
    result: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = []
    for pos, glosses_raw, topics_raw in rows:
        glosses = tuple(str(value) for value in json.loads(str(glosses_raw)))
        topics = tuple(str(value) for value in json.loads(str(topics_raw)))
        result.append((str(pos), glosses, topics))
    return result


def fail(message: str) -> None:
    raise RuntimeError(message)


def validate(
    path: Path,
    *,
    language: str,
    schema_version: str,
    min_words: int,
    min_senses: int,
) -> dict[str, object]:
    if not path.is_file():
        fail(f"database not found: {path}")

    uri = path.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        quick_check = connection.execute("PRAGMA quick_check").fetchone()
        if quick_check != ("ok",):
            fail(f"PRAGMA quick_check failed: {quick_check!r}")

        metadata = load_metadata(connection)
        expected_metadata = {
            "schema_version": schema_version,
            "language": language,
            "coverage": "full",
        }
        for key, expected in expected_metadata.items():
            actual = metadata.get(key)
            if actual != expected:
                fail(f"metadata {key!r}: expected {expected!r}, got {actual!r}")

        words = int(
            connection.execute("SELECT COUNT(DISTINCT word) FROM senses").fetchone()[0]
        )
        senses = int(connection.execute("SELECT COUNT(*) FROM senses").fetchone()[0])

        if words < min_words:
            fail(f"word count too small: {words:,} < {min_words:,}")
        if senses < min_senses:
            fail(f"sense count too small: {senses:,} < {min_senses:,}")

        love = senses_for(connection, "love")
        if len(love) < 2:
            fail(f"expected multiple senses for 'love', got {len(love)}")

        compiler = senses_for(connection, "compiler")
        if not compiler:
            fail("'compiler' is missing")
        if not any("computing" in topics for _, _, topics in compiler):
            fail("'compiler' has no 'computing' topic")

        scale = senses_for(connection, "scale")
        if not scale:
            fail("'scale' is missing")
        if not any("music" in topics for _, _, topics in scale):
            fail("'scale' has no 'music' topic")

        house = senses_for(connection, "house")
        if not house:
            fail("'house' is missing")

    return {
        "path": str(path),
        "language": language,
        "schema_version": schema_version,
        "words": words,
        "senses": senses,
        "bytes": path.stat().st_size,
        "quick_check": "ok",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a full Lexhint dictionary dataset.")
    parser.add_argument("database", type=Path)
    parser.add_argument("--language", default="en")
    parser.add_argument("--schema-version", default="4")
    parser.add_argument("--min-words", type=int, default=100_000)
    parser.add_argument("--min-senses", type=int, default=100_000)
    args = parser.parse_args()

    try:
        result = validate(
            args.database,
            language=args.language,
            schema_version=args.schema_version,
            min_words=args.min_words,
            min_senses=args.min_senses,
        )
    except (RuntimeError, sqlite3.DatabaseError, ValueError, json.JSONDecodeError) as exc:
        print(f"validation failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
