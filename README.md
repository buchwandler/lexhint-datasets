# lexhint-datasets

Build and publish prebuilt dictionary datasets for
[`buchwandler/lexhint`](https://github.com/buchwandler/lexhint).

This repository contains **build automation and metadata**, not committed dictionary
databases. Generated SQLite databases are published as GitHub Release assets.

## Important licensing boundary

The scripts and workflow in this repository are MIT-licensed.

The generated dictionary datasets are derived from Wiktionary data via
Wiktextract/Kaikki and are **not covered by the repository's MIT license**.
See [`DATA_SOURCES.md`](DATA_SOURCES.md) before publishing or redistributing datasets.

## MVP scope

The first workflow intentionally builds **English only**.

It:

1. checks out this repository;
2. checks out a requested `buchwandler/lexhint` ref;
3. installs that Lexhint build;
4. streams the Kaikki raw Wiktextract source through Lexhint's own builder;
5. validates the resulting schema and several semantic smoke cases;
6. compresses the SQLite database;
7. creates `datasets-v1.json`, `SHA256SUMS`, and attribution metadata;
8. uploads the result as a GitHub Actions artifact;
9. optionally creates a GitHub Release.

No generated `.sqlite3` files are committed to Git.

## First run

Open:

**Actions → Build English dataset → Run workflow**

Recommended first run:

- `lexhint_ref`: `main`
- `dataset_version`: a date such as `2026.08.19`
- `publish`: **false**

The build is intentionally non-publishing by default. Inspect the workflow result and
download the Actions artifact first.

Once the build, validation, sizes, and output look correct, rerun with:

- the same `dataset_version` if no release exists yet;
- `publish`: **true**.

For the first official dataset release after Lexhint `v0.1.0` exists, prefer:

- `lexhint_ref`: `v0.1.0`

rather than a moving `main` branch.

## Release contents

A release named, for example:

```text
data-2026.08.19
```

contains:

```text
lexhint-dictionary-en-s4-2026.08.19.sqlite3.gz
datasets-v1.json
SHA256SUMS
ATTRIBUTION.md
```

The manifest records:

- dataset version;
- Lexhint ref and exact Git commit;
- Lexhint dictionary schema version;
- language;
- source URL and source label;
- word/sense counts;
- compressed and uncompressed sizes;
- SHA-256.

## Dataset manifest

Example shape:

```json
{
  "manifest_version": 1,
  "generated_at": "2026-08-19T19:00:00Z",
  "datasets": {
    "dictionary": {
      "en": {
        "dataset_version": "2026.08.19",
        "schema_version": "4",
        "format": "sqlite3-gzip",
        "asset": "lexhint-dictionary-en-s4-2026.08.19.sqlite3.gz",
        "sha256": "...",
        "language": "en",
        "coverage": "full",
        "lexhint_ref": "v0.1.0",
        "lexhint_commit": "...",
        "source_url": "...",
        "source_label": "...",
        "words": 0,
        "senses": 0,
        "compressed_size": 0,
        "uncompressed_size": 0
      }
    }
  }
}
```

Later, Lexhint can use the release manifest for a command such as:

```bash
lexhint dictionary install en
```

## Local validation

Given a built Lexhint database:

```bash
python scripts/validate.py path/to/en.sqlite3 --language en
```

For fixture/small-database testing, lower the count thresholds:

```bash
python scripts/validate.py path/to/en.sqlite3 \
  --language en \
  --min-words 1 \
  --min-senses 1
```

## Design notes

### Why the dataset repository does not implement dictionary parsing

`lexhint` owns the dictionary schema and extraction semantics. This repository calls the
Lexhint builder instead of copying its SQL/extraction logic.

This prevents the dataset pipeline and runtime from silently drifting apart.

### Why English only for the MVP

The current Lexhint builder scans the source once per language. Building all supported
languages independently would repeatedly scan the full upstream Wiktextract stream.

After the English pipeline is proven, Lexhint can add a multi-language maintainer builder
that routes one source scan into several SQLite databases.

### Why GitHub Releases

Generated databases should remain outside Git history. Releases give each dataset snapshot
a stable version and make the database, manifest, checksum, and attribution metadata
downloadable together.
