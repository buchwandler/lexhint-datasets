# Data sources and dataset licensing

The build scripts and workflow in this repository are MIT-licensed. Generated
SQLite databases are separate data artifacts and are not covered by that
software license.

## Dictionary sources

Every official language release uses the matching Wiktionary edition. A Kaikki
raw edition file contains entries for many lexical languages. The pipeline
therefore selects records whose `lang_code` matches the release language after
choosing the edition:

```text
selected language -> matching Wiktionary edition -> lang_code filter -> release
```

| Lexhint language | Wiktionary edition | Kaikki source page                           | Raw compressed source                                         |
| ---------------- | ------------------ | -------------------------------------------- | ------------------------------------------------------------- |
| `cs`             | `cswiktionary`     | https://kaikki.org/cswiktionary/rawdata.html | https://kaikki.org/cswiktionary/raw-wiktextract-data.jsonl.gz |
| `de`             | `dewiktionary`     | https://kaikki.org/dewiktionary/rawdata.html | https://kaikki.org/dewiktionary/raw-wiktextract-data.jsonl.gz |
| `en`             | `enwiktionary`     | https://kaikki.org/dictionary/rawdata.html   | https://kaikki.org/dictionary/raw-wiktextract-data.jsonl.gz   |
| `es`             | `eswiktionary`     | https://kaikki.org/eswiktionary/rawdata.html | https://kaikki.org/eswiktionary/raw-wiktextract-data.jsonl.gz |
| `fr`             | `frwiktionary`     | https://kaikki.org/frwiktionary/rawdata.html | https://kaikki.org/frwiktionary/raw-wiktextract-data.jsonl.gz |
| `it`             | `itwiktionary`     | https://kaikki.org/itwiktionary/rawdata.html | https://kaikki.org/itwiktionary/raw-wiktextract-data.jsonl.gz |
| `pt`             | `ptwiktionary`     | https://kaikki.org/ptwiktionary/rawdata.html | https://kaikki.org/ptwiktionary/raw-wiktextract-data.jsonl.gz |
| `ja`             | `jawiktionary`     | https://kaikki.org/jawiktionary/rawdata.html | https://kaikki.org/jawiktionary/raw-wiktextract-data.jsonl.gz |
| `ko`             | `kowiktionary`     | https://kaikki.org/kowiktionary/rawdata.html | https://kaikki.org/kowiktionary/raw-wiktextract-data.jsonl.gz |
| `ru`             | `ruwiktionary`     | https://kaikki.org/ruwiktionary/rawdata.html | https://kaikki.org/ruwiktionary/raw-wiktextract-data.jsonl.gz |
| `th`             | `thwiktionary`     | https://kaikki.org/thwiktionary/rawdata.html | https://kaikki.org/thwiktionary/raw-wiktextract-data.jsonl.gz |
| `vi`             | `viwiktionary`     | https://kaikki.org/viwiktionary/rawdata.html | https://kaikki.org/viwiktionary/raw-wiktextract-data.jsonl.gz |
| `zh`             | `zhwiktionary`     | https://kaikki.org/zhwiktionary/rawdata.html | https://kaikki.org/zhwiktionary/raw-wiktextract-data.jsonl.gz |

This distinction is semantic, not only operational. `de` is built from
`dewiktionary`, never from the English-edition `/dictionary/` source filtered
to `lang_code == "de"`. The same rule applies to every supported language.
Edition-dependent glosses and metadata therefore remain aligned with the
physical dataset language. A `zh` release is built from `zhwiktionary`; a `ja`
release is built from `jawiktionary`; and the other physical languages likewise
use their matching editions. The English `dictionary` dump is never used as a
fallback for a language whose matching edition is unavailable.

The official release workflow resolves this table from `datasets.toml`. It does
not accept an arbitrary source URL or a multi-language selection. One action run
selects one language, downloads one edition-specific source, filters that source
to the matching language, and creates one release.

The source is downloaded atomically and verified before any database is built.
The workflow accepts an optional expected SHA-256 for byte pinning and always
computes the actual SHA-256. The manifest records:

- Wiktionary edition, source URL, and human-readable label;
- actual SHA-256 of the exact downloaded raw bytes;
- SHA-256 and entry count for the deterministic filtered language split;
- source SHA-256 embedded by Lexhint when available.

## Derived data

Lexhint stores a compact derivative containing selected dictionary information:

- normalized word key and display spelling;
- part of speech and dictionary glosses in dictionary-capable artifacts;
- semantic topics in runtime and dictionary-capable artifacts;
- forms, examples, pronunciations, and relations retained by the extractor;
- optional FrequencyWords enrichment on official standard variants.

Lexhint metadata remains the runtime source of truth for schema version,
language, coverage, capabilities, counts, builder version, dictionary source
identity, and frequency provenance. The dataset packager reads that public
artifact contract rather than querying Lexhint tables directly.

## Frequency enrichment

Official `lexical`, `runtime`, and `rich` artifacts use Lexhint's default pinned
FrequencyWords enrichment. Frequency is enrichment, not a public capability
variant. The v2 manifest preserves the provider, corpus, revision, and source
SHA-256. Local fixture and custom builds may disable frequency with
`--no-frequency`.

The physical English dataset is shared by all runtime English locale
preferences. This repository does not build `en-US` or `en-GB` artifacts.

## Licensing and attribution

Wiktionary entry text is available under CC BY-SA 4.0 and GFDL terms. Kaikki and
Wiktextract extract and transform Wiktionary content. Before publishing
generated artifacts, independently review current upstream licensing and
attribution requirements and ensure every release includes the required notices.

Useful references:

- Wiktionary: https://www.wiktionary.org/
- Wiktionary copyrights: https://en.wiktionary.org/wiki/Wiktionary:Copyrights
- Wiktextract: https://github.com/tatuylonen/wiktextract
- Kaikki dictionary data: https://kaikki.org/dictionary/index.html
- Creative Commons Attribution 4.0: https://creativecommons.org/licenses/by-sa/4.0/
- GNU Free Documentation License: https://www.gnu.org/licenses/fdl-1.3.html

Every release carries `ATTRIBUTION.md`. Generated SQLite files must not be
described as covered by this repository's MIT license. Every compressed SQLite
asset must remain below GitHub's 2 GiB per-asset release limit.

## Release provenance and topology

Every official release records:

- one base language and its Wiktionary edition;
- dataset version and generation time;
- exact Lexhint ref and commit;
- exact lexhint-datasets builder repository and commit;
- schema version, public variant, capabilities, and full-coverage status;
- source URL, edition, label, and SHA-256;
- FrequencyWords provider, corpus, revision, and SHA-256;
- original upstream SHA-256 plus filtered split SHA-256 and entry count;
- compressed artifact SHA-256 and sizes.

New releases contain exactly one language and use tags of the form
`data-<language>-<dataset-version>`, such as `data-de-2026.08.31`. Assets use
names such as `lexhint-de-runtime-s10-2026.08.31.sqlite3.gz`.

Candidate promotion consumes already-built files. It does not download a new
source or rebuild an artifact. Historical combined releases with tags such as
`data-2026.08.25` remain immutable and discoverable by compatible Lexhint
clients. New Lexhint clients understand both release layouts.

`catalog/datasets.json` indexes published release metadata for client discovery. It does not replace the release-level `datasets-v2.json`, source hashes, Wiktionary edition mapping, attribution, or other provenance records. Catalog synchronization reads the small manifest and GitHub asset metadata, records direct immutable download URLs and sizes, and does not reacquire dictionary sources or rewrite release assets.

A multi-language batch may publish independent `data-de`, `data-en`, and `data-es` tags that all target one captured lexhint-datasets builder commit. The shared builder commit does not combine the datasets: every release still contains exactly one language and retains its own manifest, SHA256SUMS, attribution, Lexhint contract, and database assets.

Do not commit generated SQLite databases to Git history.
