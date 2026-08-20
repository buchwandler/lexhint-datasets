# lexhint-datasets

Build and publish prebuilt SQLite artifacts for
[`buchwandler/lexhint`](https://github.com/buchwandler/lexhint).

This repository contains build automation and release metadata. Generated SQLite
artifacts are published as GitHub Release assets and are never committed to Git.

## Release variants

The standard catalog is data-driven in [`datasets.toml`](datasets.toml):

| Variant   | Lexhint selection        | Capabilities                  | Use                                   |
| --------- | ------------------------ | ----------------------------- | ------------------------------------- |
| `lexical` | `--capabilities lexical` | lexical                       | membership, frequency, segmentation   |
| `runtime` | `--profile runtime`      | lexical, semantic             | normal runtime evidence               |
| `rich`    | `--profile rich`         | lexical, semantic, dictionary | dictionary inspection and development |

The currently configured languages are `cs`, `de`, `en`, `es`, `fr`, `it`, and `pt`.
FrequencyWords enrichment is the official default enrichment for all standard variants,
not a separate release axis.

## Release assets

Assets use this format:

```text
lexhint-<language>-<variant>-s<schema>-<dataset-version>.sqlite3.gz
```

For example:

```text
lexhint-en-runtime-s7-2026.08.20.sqlite3.gz
```

Each release contains one [`datasets-v2.json`](datasets-v2.json) manifest with an
`artifacts` array. Each record includes the actual Lexhint capabilities and metadata,
capability-aware counts, frequency provenance, source provenance, compressed and
uncompressed sizes, and an asset SHA-256. `SHA256SUMS`, `ATTRIBUTION.md`, and
`release-notes.md` accompany the database assets.

## Local maintainer flow

Install the sibling Lexhint checkout, then acquire one local source snapshot:

```bash
python -m pip install ../lexhint
python -m scripts.download_source \
  --url https://kaikki.org/dictionary/raw-wiktextract-data.jsonl.gz \
  --output build/source/raw-wiktextract-data.jsonl.gz \
  --json
```

The default Kaikki current endpoint is mutable. Supplying --sha256 is an
optional expected-byte assertion; acquisition always computes the actual digest.

Build the configured language and variant matrix with one streaming source split,
one rich build per language, and Lexhint-owned projections:

```bash
mkdir -p build dist
python -m scripts.build_release \
  --source build/source/raw-wiktextract-data.jsonl.gz \
  --build-dir build \
  --languages en \
  --variants lexical,runtime,rich
```

Validate an artifact:

```bash
python -m scripts.validate build/en-runtime.sqlite3 \
  --language en \
  --variant runtime
```

Assemble the release:

```bash
python -m scripts.package_release \
  --build-dir build \
  --output-dir dist \
  --dataset-version 2026.08.20 \
  --lexhint-ref main \
  --lexhint-commit "$(git -C ../lexhint rev-parse HEAD)" \
  --source-url https://kaikki.org/dictionary/raw-wiktextract-data.jsonl.gz \
  --source-label "Kaikki raw Wiktextract snapshot" \
  --source-sha256 <source-sha256>

sha256sum -c dist/SHA256SUMS
```

Tests use tiny checked-in Lexhint fixtures and do not download production data:

```bash
python -m pytest -q tests
python -m pytest -q ../lexhint/tests
```

## GitHub Actions

Run **Actions > Build Lexhint datasets** with `publish` set to `false` to inspect a
candidate, or `true` to publish that exact verified candidate. The workflow validates the requested languages and variants, downloads and verifies one
source, builds rich artifacts, creates Lexhint-owned projections, validates every
artifact, and uploads one release candidate.

The workflow accepts an optional expected source_sha256. It always computes the
actual digest of the bytes acquired and records that digest in the manifest; a
published candidate therefore remains provenance-safe even when the mutable default
URL was used. The workflow refuses to overwrite an existing
data-<dataset-version> release, checks every asset checksum and the GitHub
2 GiB per-asset limit, and publishes the exact candidate assembled by the build job.

For a later approval window, run the separate Publish Lexhint dataset candidate
workflow with the completed build run ID, dataset version, and candidate commit. It
downloads and verifies the existing candidate artifact and never reacquires the
source or rebuilds dictionaries.

## Design boundary

Lexhint owns artifact schema, extraction semantics, capabilities, status reporting, and
the `dictionary project` operation. This repository owns source acquisition, configured
validation policy, release assembly, manifests, checksums, attribution, and publication.
It does not copy Lexhint's SQLite schema or dictionary parsing logic.

## Licensing boundary

The scripts and workflow are MIT-licensed. Generated dictionary artifacts are separate
data products derived from Wiktionary through Wiktextract and Kaikki. They are not
covered by the repository's software license. See [`DATA_SOURCES.md`](DATA_SOURCES.md)
before publishing or redistributing a release.

## Provenance and candidate promotion

datasets-v2.json records the actual upstream source SHA-256, exact Lexhint commit,
the lexhint-datasets builder commit, artifact checksums, and FrequencyWords
provenance. When the raw source is split, build_sources records each deterministic
language input with its own SHA-256, entry count, and upstream SHA-256. Artifact
metadata is checked against the language split hash; the manifest source hash remains
the hash of the original downloaded source.

The build job produces an immutable candidate before publication. The publication
job or the separate promotion workflow verifies that candidate, including its
complete language/variant matrix, checksums, attribution, source digest, and asset
sizes. Ordinary Lexhint runtime lookup is not changed here and no Lexhint
installer/download feature is implemented by this repository.
