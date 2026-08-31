# lexhint-datasets

Build and publish prebuilt SQLite artifacts for
[`buchwandler/lexhint`](https://github.com/buchwandler/lexhint).

This repository contains build automation and release metadata. Generated SQLite
artifacts are published as GitHub Release assets and are never committed to Git.

## Release variants

The standard catalog is data-driven in [`datasets.toml`](datasets.toml):

| Variant | Lexhint selection | Capabilities | Use |
| --- | --- | --- | --- |
| `lexical` | `--capabilities lexical` | lexical | membership, frequency, segmentation |
| `runtime` | `--profile runtime` | lexical, semantic | normal runtime evidence |
| `dictionary` | `--capabilities lexical,semantic,dictionary` | lexical, semantic, dictionary | dictionary lookup without search indexes |
| `rich` | `--profile rich` | lexical, semantic, dictionary, search | dictionary plus fuzzy suggestions and indexed text search |

The normal release matrix is `lexical,runtime,dictionary`. `runtime` is the
recommended client download. `rich` is an explicit search and development tier.

The configured physical base languages are `cs`, `de`, `en`, `es`, `fr`, `it`,
and `pt`. Regional locale preferences do not expand this build matrix.
FrequencyWords enrichment is the official default enrichment, not a release axis.

## Edition-aligned source model

Each physical language is built from the matching Wiktionary edition. The raw
Kaikki file for an edition contains many lexical languages, so the build still
filters records by the selected `lang_code`:

| Language | Wiktionary edition | Raw source |
| --- | --- | --- |
| `cs` | `cswiktionary` | `https://kaikki.org/cswiktionary/raw-wiktextract-data.jsonl.gz` |
| `de` | `dewiktionary` | `https://kaikki.org/dewiktionary/raw-wiktextract-data.jsonl.gz` |
| `en` | `enwiktionary` | `https://kaikki.org/dictionary/raw-wiktextract-data.jsonl.gz` |
| `es` | `eswiktionary` | `https://kaikki.org/eswiktionary/raw-wiktextract-data.jsonl.gz` |
| `fr` | `frwiktionary` | `https://kaikki.org/frwiktionary/raw-wiktextract-data.jsonl.gz` |
| `it` | `itwiktionary` | `https://kaikki.org/itwiktionary/raw-wiktextract-data.jsonl.gz` |
| `pt` | `ptwiktionary` | `https://kaikki.org/ptwiktionary/raw-wiktextract-data.jsonl.gz` |

In particular, `de` is built from `dewiktionary`, not `enwiktionary`, and `es`
is built from `eswiktionary`, not `enwiktionary`. Edition, exact source URL,
actual source SHA-256, filtered split SHA-256, and filtered entry count are
recorded in release provenance.

## Release assets

Assets use this format:

```text
lexhint-<language>-<variant>-s<schema>-<dataset-version>.sqlite3.gz
```

For example:

```text
lexhint-de-runtime-s10-2026.08.31.sqlite3.gz
```

Every new release contains one language and a `datasets-v2.json` manifest. The
manifest is accompanied by `SHA256SUMS`, `ATTRIBUTION.md`,
`lexhint-contract.json`, and `release-notes.md`.

New release tags use:

```text
data-<language>-<dataset-version>
```

For example, `data-de-2026.08.31`. Historical combined releases using
`data-<dataset-version>` remain immutable and discoverable by compatible Lexhint
clients.

Lexhint package version, dataset version, and SQLite schema version are
independent. Clients select artifacts by exact schema equality. A new schema
build does not replace historical releases for older clients.

## Dataset catalog

`catalog/datasets.json` is the canonical client discovery index. GitHub Releases remain the immutable artifact store, and each release's `datasets-v2.json` remains the detailed provenance manifest. Catalog entries contain direct HTTPS asset URLs, SHA-256 values, and compressed/uncompressed sizes, so clients do not need to enumerate GitHub Releases.

Several independent language tags may target one builder commit:

```text
builder commit A
  data-de-2026.08.31 -> A
  data-en-2026.08.31 -> A
  data-es-2026.08.31 -> A
```

The catalog is regenerated only after publication. A no-op synchronization is byte-identical, and an existing release tag cannot be rewritten to point to different catalog metadata. Historical combined tags remain supported during bootstrap; a qualified release is preferred when both tags claim the same language, variant, schema, and dataset-version slot.


## Local maintainer flow

Install the sibling Lexhint checkout, then acquire the source for one language:

```bash
python -m pip install ../lexhint
python -m scripts.download_source \
  --url https://kaikki.org/dewiktionary/raw-wiktextract-data.jsonl.gz \
  --output build/source/de-raw-wiktextract-data.jsonl.gz \
  --json
```

An expected `--sha256` is optional for local acquisition. The actual digest is
always computed. Build one explicit language:

```bash
mkdir -p build dist
python -m scripts.build_release \
  --source build/source/de-raw-wiktextract-data.jsonl.gz \
  --build-dir build \
  --language de \
  --variants lexical,runtime,dictionary
```

Use `--variants rich` only when the explicit search tier is required. Validate
an artifact with:

```bash
python -m scripts.validate build/de-runtime.sqlite3 \
  --language de \
  --variant runtime
```

Package a candidate with the selected source provenance:

```bash
python -m scripts.package_release \
  --build-dir build \
  --output-dir dist \
  --dataset-version 2026.08.31 \
  --lexhint-ref main \
  --lexhint-commit "$(git -C ../lexhint rev-parse HEAD)" \
  --source-url https://kaikki.org/dewiktionary/raw-wiktextract-data.jsonl.gz \
  --source-label "Kaikki raw Wiktextract from German Wiktionary edition" \
  --source-edition dewiktionary \
  --source-sha256 <source-sha256> \
  --expected-language de \
  --expected-variant lexical \
  --expected-variant runtime \
  --expected-variant dictionary

sha256sum -c dist/SHA256SUMS
```

Tests use small fixtures and do not download production data:

```bash
python -m pytest -q
cd ../lexhint && python -m pytest -q
```

## GitHub Actions

Run **Actions > Build Lexhint datasets** with `Language release to build` set
to one language. The official workflow has no source URL override and no
multi-language input. It resolves the source URL, label, edition, and release
selection from `datasets.toml`, downloads one language-specific raw file, filters
its matching `lang_code`, builds the selected variants, and uploads a candidate
named `lexhint-datasets-<language>-<dataset-version>`.

Set `publish` to `false` to inspect a candidate. Set it to `true` only after the
candidate has been checked. The optional expected source SHA-256 pins the
acquired bytes, while the computed digest is recorded in the manifest. The
workflow refuses to overwrite an existing language-qualified release.

The separate **Publish Lexhint dataset candidate** workflow asks for the same
language choice. It downloads the exact candidate, verifies its language,
variants, checksums, provenance, and asset sizes, then publishes it as
`data-<language>-<dataset-version>`. It never reacquires source bytes or rebuilds
dictionaries.

For independent releases, use **Actions > Refresh dataset catalog** with one or more exact published tags. It runs with serialized catalog concurrency, verifies the result, rebases before pushing, and never force-pushes.

For a batch, use **Actions > Release selected Lexhint datasets**: select `de,en,es` (or another unique list of enabled languages), capture one builder commit, build one candidate per language from that commit, publish `data-<language>-<dataset-version>` tags with the same `--target`, then synchronize the catalog once after all matrix publications succeed. Each candidate still contains one language and its own manifest, checksums, attribution, contract, and database assets.

The catalog synchronization job checks only release metadata and the small `datasets-v2.json` manifest. It does not reacquire dictionary sources or download multi-gigabyte database assets.

## Design boundary

Lexhint owns artifact schema, extraction semantics, capabilities, status
reporting, and the `dictionary project` operation. This repository owns source
acquisition, source mapping, validation policy, release assembly, manifests,
checksums, attribution, and publication. It does not copy Lexhint's SQLite
schema or dictionary parsing logic.

## Licensing boundary

The scripts and workflow are MIT-licensed. Generated dictionary artifacts are
separate data products derived from Wiktionary through Wiktextract and Kaikki.
They are not covered by the repository's software license. See
[`DATA_SOURCES.md`](DATA_SOURCES.md) before publishing or redistributing a
release.

## Provenance and candidate promotion

`datasets-v2.json` records the selected language and Wiktionary edition, the
actual upstream source SHA-256, the exact Lexhint commit, the lexhint-datasets
builder commit, artifact checksums, and FrequencyWords provenance. When the raw
source is split, `build_sources` records the deterministic language input with
its split SHA-256, entry count, and upstream SHA-256.

Candidate promotion consumes these already-built files. It does not download a
new source or rebuild an artifact. Keep old GitHub Release assets immutable so
older Lexhint clients can continue discovering their newest compatible release.
