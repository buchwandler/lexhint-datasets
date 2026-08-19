# Data sources and dataset licensing

This repository contains build scripts and workflow files licensed under the MIT License.

**Generated dictionary datasets are separate data artifacts and are not licensed under
the repository's MIT License.**

## Dictionary source

The MVP builds Lexhint dictionary indexes from the Kaikki raw Wiktextract stream:

```text
https://kaikki.org/dictionary/raw-wiktextract-data.jsonl.gz
```

Relevant upstream projects:

- Wiktionary: https://www.wiktionary.org/
- Wiktextract: https://github.com/tatuylonen/wiktextract
- Kaikki: https://kaikki.org/

Lexhint stores a compact derivative containing selected dictionary information:

- normalized word key;
- display spelling;
- part of speech;
- dictionary glosses;
- explicit semantic topics.

It intentionally does not mirror all raw Wiktionary metadata.

## Licensing

Wiktionary entry text is made available under CC BY-SA 4.0 and GFDL terms.
Kaikki/Wiktextract extracts and transforms Wiktionary content.

Before publishing generated datasets, review the current upstream licensing and
attribution requirements and ensure each release carries the required notices.

Useful references:

- https://en.wiktionary.org/wiki/Wiktionary:Copyrights
- https://kaikki.org/dictionary/index.html
- https://creativecommons.org/licenses/by-sa/4.0/
- https://www.gnu.org/licenses/fdl-1.3.html

## Release provenance

Every official dataset release should record:

- dataset version;
- exact Lexhint Git commit used to build it;
- Lexhint schema version;
- source URL;
- a human-readable source label/snapshot identifier;
- generation timestamp;
- language;
- word/sense counts;
- SHA-256 of the compressed artifact.

The MVP workflow accepts `source_label` as an explicit input because the default Kaikki
raw URL is a moving upstream target. For reproducible official releases, prefer a pinned
or otherwise unambiguously identified upstream snapshot when one is available.
