# Data sources and dataset licensing

The build scripts and workflow in this repository are MIT-licensed. Generated
SQLite databases are separate data artifacts and are not covered by that
software license.

## Dictionary sources

Every official language release has an explicit source variant. `native` uses a verified language-specific Wiktionary edition where configured. `english` always uses the shared Kaikki raw Wiktextract English-edition source, filters exact `lang_code`, and retains the language page under `https://kaikki.org/dictionary/<Language>/` as provenance. The complete 41-language mapping, native availability, metadata language, and frequency policy live in `datasets.toml`.

```text
<language> + native  -> matching native Wiktionary edition when verified
<language> + english -> https://kaikki.org/dictionary/raw-wiktextract-data.jsonl.gz + exact lang_code filter
```

The English raw source is downloaded once per source-variant build and is never replaced by a deprecated per-language download. Languages without a verified native endpoint are explicitly English-only. Source variant is part of artifact identity and cannot be inferred from the base language.
The official release workflow resolves this table from `datasets.toml`. It accepts one language and one source variant, resolves the source URL from configuration, filters one exact `lang_code`, and creates one source-qualified release. It never accepts an arbitrary source URL or silently falls back from native to English.
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

Official `lexical`, `runtime`, and `rich` artifacts use the configured pinned frequency
enrichment when a vetted source is available. Frequency is enrichment, not a public
capability variant. The v2 manifest preserves the provider, corpus, revision, source URL,
and SHA-256 when enrichment is used. Kurdish is explicitly configured with frequency
disabled because its source path is absent at the pinned FrequencyWords revision. Local
fixture and custom builds may also disable frequency with `--no-frequency`.

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

- one base language and source variant (`native` or `english`);
- the Wiktionary edition and provenance page for that source variant;
- dataset version and generation time;
- exact Lexhint ref and commit (Lexhint 0.4.7 for the target release line);
- exact lexhint-datasets builder repository and commit;
- schema version, public variant, capabilities, and full-coverage status;
- source URL, edition, metadata language, and SHA-256;
- FrequencyWords provider, corpus, revision, and SHA-256 when enabled;
- original upstream SHA-256 plus filtered split SHA-256 and entry count;
- compressed artifact SHA-256 and sizes.

New releases contain exactly one language and source variant. Tags use the form
`data-<language>-<source-variant>-<dataset-version>`, such as
`data-de-native-2026.08.31`. Assets use names such as
`lexhint-de-native-runtime-s10-2026.08.31.sqlite3.gz`.

Candidate promotion consumes already-built files. It does not download a new source or rebuild an artifact. Historical combined releases and unqualified historical tags remain immutable and are interpreted as native by compatibility clients.

`catalog/datasets-v2.json` indexes source-qualified published release metadata for client discovery. It preserves historical `catalog/datasets.json` and never rewrites immutable legacy entries. Each release-level `datasets-v2.json` remains authoritative for source hashes, edition mapping, split manifests, attribution, and other provenance records.

A multi-language batch publishes independent source-qualified tags that all target one captured lexhint-datasets builder commit. Every release still contains exactly one language and source variant, its own manifest, SHA256SUMS, attribution, Lexhint contract, and database assets.

Do not commit generated SQLite databases to Git history.
