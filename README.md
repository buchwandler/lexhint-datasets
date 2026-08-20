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
python scripts/download_source.py \
  --url https://kaikki.org/dictionary/raw-wiktextract-data.jsonl.gz \
  --output build/source/raw-wiktextract-data.jsonl.gz \
  --sha256 <source-sha256>
```

Build one rich artifact per language and project the smaller variants:

```bash
mkdir -p build dist
lexhint dictionary build en \
  --source build/source/raw-wiktextract-data.jsonl.gz \
  --output build/work/en.rich.sqlite3 \
  --profile rich
lexhint dictionary project build/work/en.rich.sqlite3 \
  --output build/en-runtime.sqlite3 \
  --profile runtime
lexhint dictionary project build/work/en.rich.sqlite3 \
  --output build/en-lexical.sqlite3 \
  --capabilities lexical
cp build/work/en.rich.sqlite3 build/en-rich.sqlite3
```

Validate an artifact:

```bash
python scripts/validate.py build/en-runtime.sqlite3 \
  --language en \
  --variant runtime
```

Assemble the release:

```bash
python scripts/package_release.py \
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

Run **Actions > Build Lexhint datasets** with `publish` set to `false` first. The
workflow validates the requested languages and variants, downloads and verifies one
source, builds rich artifacts, creates Lexhint-owned projections, validates every
artifact, and uploads one release candidate.

For `publish=true`, `source_sha256` is required. The workflow refuses to overwrite an
existing `data-<dataset-version>` release and checks every asset checksum before
creating the GitHub Release. Production publication should be staging-first.

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
