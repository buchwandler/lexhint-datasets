#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def metadata(path: Path) -> dict[str, str]:
    uri = path.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        return {
            str(key): str(value)
            for key, value in connection.execute("SELECT key, value FROM metadata")
        }


def counts(path: Path) -> tuple[int, int]:
    uri = path.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        words = int(
            connection.execute("SELECT COUNT(DISTINCT word) FROM senses").fetchone()[0]
        )
        senses = int(connection.execute("SELECT COUNT(*) FROM senses").fetchone()[0])
    return words, senses


def gzip_copy(source: Path, target: Path) -> None:
    with source.open("rb") as src, target.open("wb") as raw:
        # mtime=0 makes the gzip stream stable for identical SQLite bytes.
        with gzip.GzipFile(
            filename=source.name,
            mode="wb",
            fileobj=raw,
            compresslevel=9,
            mtime=0,
        ) as dst:
            shutil.copyfileobj(src, dst, length=1024 * 1024)


def main() -> int:
    parser = argparse.ArgumentParser(description="Package one Lexhint dictionary dataset.")
    parser.add_argument("database", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("dist"))
    parser.add_argument("--language", default="en")
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--lexhint-ref", required=True)
    parser.add_argument("--lexhint-commit", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--source-label", required=True)
    parser.add_argument("--attribution", type=Path, default=Path("DATA_SOURCES.md"))
    args = parser.parse_args()

    db = args.database
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)

    meta = metadata(db)
    schema_version = meta.get("schema_version", "unknown")
    coverage = meta.get("coverage", "unknown")
    db_language = meta.get("language", "unknown")

    if schema_version == "unknown":
        raise SystemExit("database has no schema_version metadata")
    if db_language != args.language:
        raise SystemExit(
            f"database language mismatch: expected {args.language!r}, got {db_language!r}"
        )
    if coverage != "full":
        raise SystemExit(f"database is not full coverage: {coverage!r}")

    words, senses = counts(db)
    asset_name = (
        f"lexhint-dictionary-{args.language}-s{schema_version}-"
        f"{args.dataset_version}.sqlite3.gz"
    )
    asset_path = output / asset_name
    gzip_copy(db, asset_path)

    digest = sha256(asset_path)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    dataset = {
        "dataset_version": args.dataset_version,
        "schema_version": schema_version,
        "format": "sqlite3-gzip",
        "asset": asset_name,
        "sha256": digest,
        "language": args.language,
        "coverage": coverage,
        "lexhint_ref": args.lexhint_ref,
        "lexhint_commit": args.lexhint_commit,
        "source_url": args.source_url,
        "source_label": args.source_label,
        "generated_at": generated_at,
        "words": words,
        "senses": senses,
        "compressed_size": asset_path.stat().st_size,
        "uncompressed_size": db.stat().st_size,
    }

    manifest = {
        "manifest_version": 1,
        "generated_at": generated_at,
        "datasets": {"dictionary": {args.language: dataset}},
    }
    manifest_path = output / "datasets-v1.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    (output / "SHA256SUMS").write_text(
        f"{digest}  {asset_name}\n",
        encoding="utf-8",
    )

    if args.attribution.is_file():
        shutil.copy2(args.attribution, output / "ATTRIBUTION.md")

    notes = f"""# Lexhint datasets {args.dataset_version}

English full dictionary dataset built by Lexhint.

- Lexhint ref: `{args.lexhint_ref}`
- Lexhint commit: `{args.lexhint_commit}`
- Schema: `{schema_version}`
- Language: `{args.language}`
- Words: {words:,}
- Senses: {senses:,}
- Compressed bytes: {asset_path.stat().st_size:,}
- Uncompressed bytes: {db.stat().st_size:,}
- Source: {args.source_label}

See `ATTRIBUTION.md` and `datasets-v1.json` for provenance and data-source information.
"""
    (output / "release-notes.md").write_text(notes, encoding="utf-8")

    print(json.dumps(dataset, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
