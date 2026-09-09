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

The configured physical languages are the 41 enabled codes in [`datasets.toml`](datasets.toml): `ar`, `az`, `bg`, `ca`, `ceb`, `cs`, `de`, `el`, `en`, `es`, `fr`, `ga`, `he`, `hi`, `hu`, `hy`, `id`, `it`, `ja`, `ko`, `ku`, `la`, `lt`, `lv`, `mr`, `ms`, `nl`, `pl`, `pt`, `ro`, `ru`, `sv`, `ta`, `te`, `th`, `tl`, `tr`, `uk`, `ur`, `vi`, and `zh`. Each language has an explicit default source variant and may expose `native`, `english`, or both. Regional locale preferences do not expand this build matrix.

| Variant | languages |
| --- | --- |
| `english` |
ar,az,bg,ca,ceb,cs,de,el,es,fr,ga,he,hi,hu,hy,it,ja,ko,la,lt,lv,mr,nl,pl,pt,ro,ru,sv,ta,te,tl,tr,uk,ur,vi,zh
|
| `native` | cs,de,el,en,es,fr,id,it,ja,ko,ku,ms,pl,pt,ru,th,tr,vi,zh |


Official standard artifacts use configured pinned frequency enrichment when available. Languages without a vetted source have frequency disabled explicitly, and the manifest records the policy.
## Edition-aligned source model

Every release selects one source variant. Native variants use a verified native Wiktionary edition where configured. English variants use the shared Kaikki English-edition file, filter exact `lang_code`, and keep the language provenance page under `https://kaikki.org/dictionary/<Language>/`. The full mapping is in `datasets.toml`; this README intentionally does not duplicate a mutable source table.

The source URL, Wiktionary edition, metadata language, actual source SHA-256, deterministic filtered split SHA-256, and entry count are recorded in release provenance.

## Release assets

Assets use this format:

```text
lexhint-<language>-<source-variant>-<variant>-s<schema>-<dataset-version>.sqlite3.gz
```

For example:

```text
lexhint-de-native-runtime-s10-2026.08.31.sqlite3.gz
```

Every new release contains one language, one source variant, and a `datasets-v2.json` manifest. The manifest is accompanied by `SHA256SUMS`, `ATTRIBUTION.md`, `lexhint-contract.json`, and `release-notes.md`.

New release tags use:

```text
data-<language>-<source-variant>-<dataset-version>
```

For example, `data-de-native-2026.08.31`. Historical unqualified and combined tags remain immutable and discoverable by compatible clients.
Lexhint package version, dataset version, and SQLite schema version are
independent. Clients select artifacts by exact schema equality. A new schema
build does not replace historical releases for older clients.

## Dataset catalog

`catalog/datasets-v2.json` is the canonical source-qualified client discovery index. Historical `catalog/datasets.json` remains immutable for compatibility. GitHub Releases remain the immutable artifact store, and each release's `datasets-v2.json` remains the detailed provenance manifest. Catalog entries contain direct HTTPS asset URLs, source variant, SHA-256 values, and compressed/uncompressed sizes.

Several independent language and source-variant tags may target one builder commit:

```text
builder commit A
  data-de-native-2026.08.31 -> A
  data-de-english-2026.08.31 -> A
  data-en-native-2026.08.31 -> A
```

The catalog is regenerated only after publication. A no-op synchronization is byte-identical, existing release tags cannot be rewritten, and historical unqualified entries are not mutated.


## Local maintainer flow

Install the sibling Lexhint checkout, then resolve and acquire one source variant:

```bash
python -m pip install ../lexhint
python - <<'PY'
from scripts.config import load_config
source = load_config().source_for("de", "native")
print(source.url)
PY
python -m scripts.download_source \
  --url https://kaikki.org/dewiktionary/raw-wiktextract-data.jsonl.gz \
  --output build/source/de-native-raw-wiktextract-data.jsonl.gz \
  --json
```

An expected `--sha256` is optional for local acquisition. The actual digest is always computed. Build one explicit source-qualified language:

```bash
mkdir -p build dist
python -m scripts.build_release \
  --source build/source/de-native-raw-wiktextract-data.jsonl.gz \
  --build-dir build \
  --language de \
  --source-variant native \
  --variants lexical,runtime,dictionary
```

Validate an artifact with:

```bash
python -m scripts.validate build/de-native-runtime.sqlite3 \
  --language de \
  --variant runtime \
  --expected-source-variant native
```


Package a candidate with the selected source provenance:

```bash
python -m scripts.package_release \
  --build-dir build \
  --output-dir dist \
  --dataset-version 2026.08.31 \
  --lexhint-ref v0.4.7 \
  --lexhint-commit "$(git -C ../lexhint rev-parse HEAD)" \
  --source-variant native \
  --source-url https://kaikki.org/dewiktionary/raw-wiktextract-data.jsonl.gz \
  --source-label "Kaikki raw Wiktextract from German Wiktionary edition" \
  --source-edition dewiktionary \
  --source-metadata-language de \
  --source-sha256 <source-sha256> \
  --source-splits build/source/native/source-splits-v1.json \
  --expected-language de \
  --expected-source-variant native \
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

Run **Actions > Build Lexhint datasets** with one language and an explicit `native` or `english` source variant. The workflow resolves source provenance from `datasets.toml`, uses Lexhint 0.4.7, downloads the configured raw source, filters exact `lang_code`, builds the selected variants, and uploads a candidate named `lexhint-datasets-<language>-<source-variant>-<dataset-version>`.

Set `publish` to `false` to inspect a candidate. Set it to `true` only after the candidate has been checked. The optional expected source SHA-256 pins the acquired bytes, while the computed digest is recorded in the manifest. The workflow refuses to overwrite an existing source-qualified release.

The separate **Publish Lexhint dataset candidate** workflow asks for the same language and source variant. It downloads the exact candidate, verifies its language, source identity, variants, checksums, provenance, and asset sizes, then publishes it as `data-<language>-<source-variant>-<dataset-version>`. It never reacquires source bytes or rebuilds dictionaries.

For independent releases, use **Actions > Refresh dataset catalog** with one or more exact published tags. It runs with serialized catalog concurrency, verifies the result, rebases before pushing, and never force-pushes.

For a batch, use **Actions > Release selected Lexhint datasets**: select languages such as `de,en,es` and one source variant, or run separate batches for `native` and `english`. The workflow captures one builder commit, builds one candidate per language/source pair, publishes one qualified tag per pair, then synchronizes the catalog once.

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
