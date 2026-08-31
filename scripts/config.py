from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import tomllib

SUPPORTED_BASE_LANGUAGES = ("cs", "de", "en", "es", "fr", "it", "pt")
SUPPORTED_LANGUAGES = SUPPORTED_BASE_LANGUAGES
EXPECTED_WIKTIONARY_EDITIONS = {
    "cs": "cswiktionary",
    "de": "dewiktionary",
    "en": "enwiktionary",
    "es": "eswiktionary",
    "fr": "frwiktionary",
    "it": "itwiktionary",
    "pt": "ptwiktionary",
}
EXPECTED_KAIKKI_RAW_PATHS = {
    "cs": "/cswiktionary/raw-wiktextract-data.jsonl.gz",
    "de": "/dewiktionary/raw-wiktextract-data.jsonl.gz",
    "en": "/dictionary/raw-wiktextract-data.jsonl.gz",
    "es": "/eswiktionary/raw-wiktextract-data.jsonl.gz",
    "fr": "/frwiktionary/raw-wiktextract-data.jsonl.gz",
    "it": "/itwiktionary/raw-wiktextract-data.jsonl.gz",
    "pt": "/ptwiktionary/raw-wiktextract-data.jsonl.gz",
}
CAPABILITY_ORDER = ("lexical", "semantic", "dictionary", "search")


@dataclass(frozen=True, slots=True)
class VariantConfig:
    name: str
    capabilities: tuple[str, ...]
    profile: str | None
    recommended: bool


@dataclass(frozen=True, slots=True)
class ValidationConfig:
    probe_word: str | None = None
    semantic_probe: str | None = None
    dictionary_probe: str | None = None
    relation_probe_word: str | None = None
    relation_probe_target: str | None = None
    min_lexemes: int = 0
    min_semantic_rows: int = 0
    min_entries: int = 0
    min_senses: int = 0
    min_relations: int = 0
    min_frequency_lexemes: int = 0


@dataclass(frozen=True, slots=True)
class SourcePolicy:
    require_sha256_on_publish: bool


@dataclass(frozen=True, slots=True)
class LanguageSourceConfig:
    edition: str
    url: str
    label: str
    page_url: str | None = None


@dataclass(frozen=True, slots=True)
class LanguageConfig:
    code: str
    enabled: bool
    source: LanguageSourceConfig
    validation: ValidationConfig


@dataclass(frozen=True, slots=True)
class DatasetConfig:
    manifest_version: int
    default_variant: str
    default_release_variants: tuple[str, ...]
    source_policy: SourcePolicy
    variants: dict[str, VariantConfig]
    languages: dict[str, LanguageConfig]

    @property
    def enabled_languages(self) -> tuple[LanguageConfig, ...]:
        return tuple(
            language for language in self.languages.values() if language.enabled
        )

    def source_for(self, language: str) -> LanguageSourceConfig:
        try:
            return self.languages[language].source
        except KeyError as exc:
            raise ValueError(f"unknown dataset language: {language!r}") from exc

    def variant(self, name: str) -> VariantConfig:
        try:
            return self.variants[name]
        except KeyError as exc:
            raise ValueError(f"unknown dataset variant: {name!r}") from exc


def _int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _validation(values: dict[str, Any]) -> ValidationConfig:
    probe = values.get("probe_word")
    semantic_probe = values.get("semantic_probe")
    dictionary_probe = values.get("dictionary_probe")
    relation_probe_word = values.get("relation_probe_word")
    relation_probe_target = values.get("relation_probe_target")
    if probe is not None and not isinstance(probe, str):
        raise ValueError("validation.probe_word must be a string")
    if semantic_probe is not None and not isinstance(semantic_probe, str):
        raise ValueError("validation.semantic_probe must be a string")
    if dictionary_probe is not None and not isinstance(dictionary_probe, str):
        raise ValueError("validation.dictionary_probe must be a string")
    if relation_probe_word is not None and not isinstance(relation_probe_word, str):
        raise ValueError("validation.relation_probe_word must be a string")
    if relation_probe_target is not None and not isinstance(relation_probe_target, str):
        raise ValueError("validation.relation_probe_target must be a string")
    if relation_probe_target and not relation_probe_word:
        raise ValueError(
            "validation.relation_probe_target requires relation_probe_word"
        )
    return ValidationConfig(
        probe_word=probe or None,
        semantic_probe=semantic_probe or None,
        dictionary_probe=dictionary_probe or None,
        relation_probe_word=relation_probe_word or None,
        relation_probe_target=relation_probe_target or None,
        min_lexemes=_int(values.get("min_lexemes", 0), field="min_lexemes"),
        min_semantic_rows=_int(
            values.get("min_semantic_rows", 0), field="min_semantic_rows"
        ),
        min_entries=_int(values.get("min_entries", 0), field="min_entries"),
        min_senses=_int(values.get("min_senses", 0), field="min_senses"),
        min_relations=_int(values.get("min_relations", 0), field="min_relations"),
        min_frequency_lexemes=_int(
            values.get("min_frequency_lexemes", 0), field="min_frequency_lexemes"
        ),
    )


def _variant(name: str, values: dict[str, Any]) -> VariantConfig:
    raw_capabilities = values.get("capabilities")
    if not isinstance(raw_capabilities, list) or not raw_capabilities:
        raise ValueError(f"variants.{name}.capabilities must be a non-empty list")
    if any(not isinstance(value, str) for value in raw_capabilities):
        raise ValueError(f"variants.{name}.capabilities must contain strings")
    unknown = set(raw_capabilities) - set(CAPABILITY_ORDER)
    if unknown:
        raise ValueError(f"variants.{name} has unknown capability {min(unknown)!r}")
    capabilities = tuple(
        capability for capability in CAPABILITY_ORDER if capability in raw_capabilities
    )
    if capabilities[0] != "lexical":
        raise ValueError(f"variants.{name} must include lexical capability")
    profile = values.get("profile")
    if profile is not None and not isinstance(profile, str):
        raise ValueError(f"variants.{name}.profile must be a string")
    recommended = values.get("recommended", False)
    if not isinstance(recommended, bool):
        raise TypeError(f"variants.{name}.recommended must be boolean")
    return VariantConfig(name, capabilities, profile, recommended)


def _default_release_variants(
    values: object, variants: dict[str, VariantConfig]
) -> tuple[str, ...]:
    if values is None:
        return tuple(variants)
    if not isinstance(values, list) or not values:
        raise ValueError("release.default_variants must be a non-empty list")
    if any(not isinstance(value, str) or not value for value in values):
        raise ValueError("release.default_variants must contain non-empty strings")
    selected = tuple(values)
    if len(set(selected)) != len(selected):
        raise ValueError("release.default_variants must not contain duplicates")
    unknown = set(selected) - set(variants)
    if unknown:
        raise ValueError(
            f"release.default_variants contains unknown variant {min(unknown)!r}"
        )
    order = {name: index for index, name in enumerate(variants)}
    if tuple(sorted(selected, key=order.__getitem__)) != selected:
        raise ValueError(
            "release.default_variants must follow configured variant order"
        )
    return selected


def _required_text(values: dict[str, Any], field: str, *, prefix: str) -> str:
    value = values.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{prefix}.{field} must be a non-empty string")
    return value.strip()


def _language_source(code: str, values: object) -> LanguageSourceConfig:
    if not isinstance(values, dict):
        raise TypeError(f"languages.{code}.source must be a table")
    edition = _required_text(values, "edition", prefix=f"languages.{code}.source")
    url = _required_text(values, "url", prefix=f"languages.{code}.source")
    label = _required_text(values, "label", prefix=f"languages.{code}.source")
    page_url = values.get("page_url")
    if page_url is not None and (not isinstance(page_url, str) or not page_url.strip()):
        raise ValueError(f"languages.{code}.source.page_url must be a non-empty string")
    source = LanguageSourceConfig(
        edition, url, label, page_url.strip() if page_url else None
    )
    expected_edition = EXPECTED_WIKTIONARY_EDITIONS.get(code)
    if expected_edition is not None and source.edition != expected_edition:
        raise ValueError(
            f"languages.{code}.source.edition must be {expected_edition!r}, "
            f"got {source.edition!r}"
        )
    parsed = urlsplit(source.url)
    expected_path = EXPECTED_KAIKKI_RAW_PATHS.get(code)
    if parsed.scheme != "https" or parsed.hostname != "kaikki.org":
        raise ValueError(
            f"languages.{code}.source.url must use the kaikki.org HTTPS host"
        )
    if expected_path is not None and parsed.path != expected_path:
        raise ValueError(
            f"languages.{code}.source.url must use path {expected_path!r}, "
            f"got {parsed.path!r}"
        )
    return source


def load_config(path: str | Path | None = None) -> DatasetConfig:
    config_path = (
        Path(path) if path is not None else Path(__file__).parents[1] / "datasets.toml"
    )
    with config_path.open("rb") as handle:
        raw = tomllib.load(handle)

    manifest_version = raw.get("manifest_version")
    if manifest_version != 2:
        raise ValueError("manifest_version must be 2")
    default_variant = raw.get("default_variant")
    if not isinstance(default_variant, str):
        raise TypeError("default_variant must be a string")

    source_values = raw.get("source", {})
    if not isinstance(source_values, dict):
        raise TypeError("source must be a table")
    require_hash = source_values.get("require_sha256_on_publish", True)
    if not isinstance(require_hash, bool):
        raise TypeError("source.require_sha256_on_publish must be boolean")

    raw_variants = raw.get("variants", {})
    if not isinstance(raw_variants, dict) or not raw_variants:
        raise ValueError("variants must be a non-empty table")
    variants = {
        name: _variant(name, values)
        for name, values in raw_variants.items()
        if isinstance(name, str) and isinstance(values, dict)
    }
    if len(variants) != len(raw_variants):
        raise ValueError("each variant must be a table")
    if default_variant not in variants:
        raise ValueError(f"default_variant {default_variant!r} is not configured")

    release_values = raw.get("release", {})
    if not isinstance(release_values, dict):
        raise TypeError("release must be a table")
    default_release_variants = _default_release_variants(
        release_values.get("default_variants"), variants
    )

    raw_languages = raw.get("languages", {})
    if not isinstance(raw_languages, dict):
        raise TypeError("languages must be a table")
    unknown_languages = set(raw_languages) - set(SUPPORTED_BASE_LANGUAGES)
    if unknown_languages:
        raise ValueError(f"unsupported base language {min(unknown_languages)!r}")
    languages: dict[str, LanguageConfig] = {}
    for code, values in raw_languages.items():
        if not isinstance(values, dict):
            raise TypeError(f"languages.{code} must be a table")
        enabled = values.get("enabled", False)
        if not isinstance(enabled, bool):
            raise TypeError(f"languages.{code}.enabled must be boolean")
        source = _language_source(code, values.get("source"))
        validation_values = values.get("validation", {})
        if not isinstance(validation_values, dict):
            raise TypeError(f"languages.{code}.validation must be a table")
        languages[code] = LanguageConfig(
            code, enabled, source, _validation(validation_values)
        )

    return DatasetConfig(
        manifest_version=manifest_version,
        default_variant=default_variant,
        default_release_variants=default_release_variants,
        source_policy=SourcePolicy(require_hash),
        variants=variants,
        languages=languages,
    )
