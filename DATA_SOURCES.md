# Data sources and dataset licensing

The build scripts and workflow in this repository are MIT-licensed. Generated SQLite
databases are separate data artifacts and are not covered by that software license.

## Dictionary source

The release workflow consumes one verified Wiktextract JSONL snapshot for every
language build. The default source URL is:

```text
https://kaikki.org/dictionary/raw-wiktextract-data.jsonl.gz
```

The workflow records:

- source URL, which may be a mutable current endpoint;
- human-readable source label or snapshot identifier;
- optional expected source SHA-256 supplied by the operator;
- actual source SHA-256 computed from the exact acquired bytes;
- the source SHA-256 embedded by Lexhint when available.

The source is acquired once, atomically verified before any database is built, and
split once into deterministic per-language JSONL inputs. An expected digest adds
pre-build pinning, but is not required for acquisition or publication. The actual
digest is always required in an official release manifest.

Relevant upstream projects:

- Wiktionary: https://www.wiktionary.org/
- Wiktextract: https://github.com/tatuylonen/wiktextract
- Kaikki: https://kaikki.org/

Lexhint stores a compact derivative containing selected dictionary information:

- normalized word key and display spelling;
- part of speech and dictionary glosses in rich artifacts;
- explicit semantic topics in runtime and rich artifacts;
- forms, examples, pronunciations, and relations retained by the current extractor;
- optional frequency enrichment on all official standard variants.

Lexhint's metadata remains the runtime source of truth for schema version, language,
coverage, capabilities, counts, builder version, dictionary source identity, and
frequency provenance. The dataset packager reads that public artifact contract rather
than querying Lexhint tables directly.

## Frequency enrichment

Official `lexical`, `runtime`, and `rich` artifacts use Lexhint's default pinned
FrequencyWords enrichment. Frequency is enrichment, not a public capability variant.
The v2 manifest preserves the provider, corpus, revision, and source SHA-256. Local
fixture and custom builds may disable frequency with `--no-frequency`.

The physical English dataset is shared by all runtime English locale preferences.
Current frequency enrichment is base-English data, not separate US or British corpora.
Locale interpretation, regional tag preference, and rendering remain runtime behavior
owned by Lexhint. This repository does not build `en-US` or `en-GB` artifacts.

## Licensing and attribution

Wiktionary entry text is available under CC BY-SA 4.0 and GFDL terms. Kaikki and
Wiktextract extract and transform Wiktionary content. Before publishing generated
artifacts, independently review current upstream licensing and attribution requirements
and ensure every release includes the required notices.

Useful references:

- Wiktionary copyrights: https://en.wiktionary.org/wiki/Wiktionary:Copyrights
- Kaikki dictionary data: https://kaikki.org/dictionary/index.html
- Creative Commons Attribution 4.0: https://creativecommons.org/licenses/by-sa/4.0/
- GNU Free Documentation License: https://www.gnu.org/licenses/fdl-1.3.html

Every release must carry `ATTRIBUTION.md` and must not describe generated SQLite files
as covered by the repository's MIT license.

Every compressed SQLite asset must remain below GitHub's 2 GiB per-asset release limit; the workflow refuses incomplete or oversized candidates.

## Release provenance

Every official release records:

- dataset version and generation time;
- exact Lexhint ref and commit;
- exact lexhint-datasets builder repository and commit;
- schema version;
- language and public variant;
- canonical capabilities from artifact metadata;
- full-coverage status;
- dictionary source URL, label, and SHA-256;
- FrequencyWords provider, corpus, revision, and SHA-256;
- original upstream source SHA-256 plus per-language split build-source SHA-256
  and entry count when splitting is used;
- compressed asset SHA-256 and sizes.

Candidate promotion consumes these already-built files. It does not download a new
source or rebuild an artifact, and normal Lexhint lookup remains offline and
read-only. A Lexhint consumer installer is a separate repository concern.

Keep old GitHub Release assets immutable. Schema-specific historical releases are
required for older Lexhint clients and must remain discoverable after a newer schema
becomes current. Do not commit generated SQLite databases to Git history.
