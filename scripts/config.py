from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tomllib

SUPPORTED_LANGUAGES = ("cs", "de", "en", "es", "fr", "it", "pt")
CAPABILITY_ORDER = ("lexical", "semantic", "dictionary")


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
    min_lexemes: int = 0
    min_semantic_rows: int = 0
    min_entries: int = 0
    min_senses: int = 0
    min_frequency_lexemes: int = 0


@dataclass(frozen=True, slots=True)
class LanguageConfig:
    code: str
    enabled: bool
    validation: ValidationConfig


@dataclass(frozen=True, slots=True)
class SourceConfig:
    url: str
    label: str
    require_sha256_on_publish: bool


@dataclass(frozen=True, slots=True)
class DatasetConfig:
    manifest_version: int
    default_variant: str
    source: SourceConfig
    variants: dict[str, VariantConfig]
    languages: dict[str, LanguageConfig]

    @property
    def enabled_languages(self) -> tuple[LanguageConfig, ...]:
        return tuple(
            language for language in self.languages.values() if language.enabled
        )

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
    if probe is not None and not isinstance(probe, str):
        raise ValueError("validation.probe_word must be a string")
    if semantic_probe is not None and not isinstance(semantic_probe, str):
        raise ValueError("validation.semantic_probe must be a string")
    return ValidationConfig(
        probe_word=probe or None,
        semantic_probe=semantic_probe or None,
        min_lexemes=_int(values.get("min_lexemes", 0), field="min_lexemes"),
        min_semantic_rows=_int(
            values.get("min_semantic_rows", 0), field="min_semantic_rows"
        ),
        min_entries=_int(values.get("min_entries", 0), field="min_entries"),
        min_senses=_int(values.get("min_senses", 0), field="min_senses"),
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
    source_url = source_values.get("url")
    source_label = source_values.get("label")
    require_hash = source_values.get("require_sha256_on_publish", True)
    if not isinstance(source_url, str) or not source_url:
        raise ValueError("source.url must be a non-empty string")
    if not isinstance(source_label, str) or not source_label:
        raise ValueError("source.label must be a non-empty string")
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

    raw_languages = raw.get("languages", {})
    if not isinstance(raw_languages, dict):
        raise TypeError("languages must be a table")
    unknown_languages = set(raw_languages) - set(SUPPORTED_LANGUAGES)
    if unknown_languages:
        raise ValueError(f"unsupported language {min(unknown_languages)!r}")
    languages: dict[str, LanguageConfig] = {}
    for code, values in raw_languages.items():
        if not isinstance(values, dict):
            raise TypeError(f"languages.{code} must be a table")
        enabled = values.get("enabled", False)
        if not isinstance(enabled, bool):
            raise TypeError(f"languages.{code}.enabled must be boolean")
        validation_values = values.get("validation", {})
        if not isinstance(validation_values, dict):
            raise TypeError(f"languages.{code}.validation must be a table")
        languages[code] = LanguageConfig(code, enabled, _validation(validation_values))

    return DatasetConfig(
        manifest_version=manifest_version,
        default_variant=default_variant,
        source=SourceConfig(source_url, source_label, require_hash),
        variants=variants,
        languages=languages,
    )
