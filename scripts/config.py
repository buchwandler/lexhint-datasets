from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import tomllib

SOURCE_VARIANTS = ("native", "english")
SUPPORTED_BASE_LANGUAGES = (
    "ar",
    "az",
    "bg",
    "ca",
    "ceb",
    "cs",
    "de",
    "el",
    "en",
    "es",
    "fr",
    "ga",
    "he",
    "hi",
    "hu",
    "hy",
    "id",
    "it",
    "ja",
    "ko",
    "ku",
    "la",
    "lt",
    "lv",
    "mr",
    "ms",
    "nl",
    "pl",
    "pt",
    "ro",
    "ru",
    "sv",
    "ta",
    "te",
    "th",
    "tl",
    "tr",
    "uk",
    "ur",
    "vi",
    "zh",
)
SUPPORTED_LANGUAGES = SUPPORTED_BASE_LANGUAGES
EXPECTED_WIKTIONARY_EDITIONS = {
    code: f"{code}wiktionary"
    for code in (
        "ar",
        "az",
        "bg",
        "ca",
        "cs",
        "de",
        "el",
        "en",
        "es",
        "fr",
        "ga",
        "he",
        "hi",
        "hu",
        "hy",
        "id",
        "it",
        "ja",
        "ko",
        "ku",
        "la",
        "lt",
        "lv",
        "mr",
        "ms",
        "nl",
        "pl",
        "pt",
        "ro",
        "ru",
        "sv",
        "ta",
        "te",
        "th",
        "tl",
        "tr",
        "uk",
        "ur",
        "vi",
        "zh",
    )
}
EXPECTED_WIKTIONARY_EDITIONS.update({"ceb": "cebwiktionary"})
EXPECTED_KAIKKI_RAW_PATHS = {
    code: f"/{edition}/raw-wiktextract-data.jsonl.gz"
    for code, edition in EXPECTED_WIKTIONARY_EDITIONS.items()
}
EXPECTED_KAIKKI_RAW_PATHS["en"] = "/dictionary/raw-wiktextract-data.jsonl.gz"
ENGLISH_RAW_URL = "https://kaikki.org/dictionary/raw-wiktextract-data.jsonl.gz"
ENGLISH_PAGE_NAMES = {
    "ar": "Arabic",
    "az": "Azerbaijani",
    "bg": "Bulgarian",
    "ca": "Catalan",
    "ceb": "Cebuano",
    "cs": "Czech",
    "de": "German",
    "el": "Greek",
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "ga": "Irish",
    "he": "Hebrew",
    "hi": "Hindi",
    "hu": "Hungarian",
    "hy": "Armenian",
    "id": "Indonesian",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "ku": "Kurdish",
    "la": "Latin",
    "lt": "Lithuanian",
    "lv": "Latvian",
    "mr": "Marathi",
    "ms": "Malay",
    "nl": "Dutch",
    "pl": "Polish",
    "pt": "Portuguese",
    "ro": "Romanian",
    "ru": "Russian",
    "sv": "Swedish",
    "ta": "Tamil",
    "te": "Telugu",
    "th": "Thai",
    "tl": "Tagalog",
    "tr": "Turkish",
    "uk": "Ukrainian",
    "ur": "Urdu",
    "vi": "Vietnamese",
    "zh": "Chinese",
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
class FrequencyConfig:
    enabled: bool
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class LanguageSourceConfig:
    source_variant: str
    wiktionary_edition: str
    metadata_language: str
    url: str
    label: str
    page_url: str | None = None
    validation: ValidationConfig | None = None

    @property
    def edition(self) -> str:
        return self.wiktionary_edition


@dataclass(frozen=True, slots=True)
class LanguageConfig:
    code: str
    enabled: bool
    default_source_variant: str
    sources: dict[str, LanguageSourceConfig]
    validation: ValidationConfig
    frequency: FrequencyConfig

    @property
    def source(self) -> LanguageSourceConfig:
        return self.sources[self.default_source_variant]


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

    def source_for(
        self, language: str, source_variant: str | None = None
    ) -> LanguageSourceConfig:
        try:
            language_config = self.languages[language]
            variant = source_variant or language_config.default_source_variant
            return language_config.sources[variant]
        except KeyError as exc:
            if language not in self.languages:
                raise ValueError(f"unknown dataset language: {language!r}") from exc
            raise ValueError(
                f"source variant {source_variant!r} is not configured for {language!r}"
            ) from exc

    def source_variants_for(self, language: str) -> tuple[str, ...]:
        try:
            return tuple(self.languages[language].sources)
        except KeyError as exc:
            raise ValueError(f"unknown dataset language: {language!r}") from exc

    def default_source_variant_for(self, language: str) -> str:
        try:
            return self.languages[language].default_source_variant
        except KeyError as exc:
            raise ValueError(f"unknown dataset language: {language!r}") from exc

    def validation_for(
        self, language: str, source_variant: str | None = None
    ) -> ValidationConfig:
        language_config = self.languages[language]
        source = self.source_for(language, source_variant)
        return source.validation or language_config.validation

    def variant(self, name: str) -> VariantConfig:
        try:
            return self.variants[name]
        except KeyError as exc:
            raise ValueError(f"unknown dataset variant: {name!r}") from exc


def _int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _validation(values: object, *, prefix: str) -> ValidationConfig:
    if values is None:
        return ValidationConfig()
    if not isinstance(values, dict):
        raise TypeError(f"{prefix} must be a table")
    strings = {}
    for field in (
        "probe_word",
        "semantic_probe",
        "dictionary_probe",
        "relation_probe_word",
        "relation_probe_target",
    ):
        value = values.get(field)
        if value is not None and not isinstance(value, str):
            raise ValueError(f"{prefix}.{field} must be a string")
        strings[field] = value.strip() if value else None
    if strings["relation_probe_target"] and not strings["relation_probe_word"]:
        raise ValueError(f"{prefix}.relation_probe_target requires relation_probe_word")
    return ValidationConfig(
        **strings,
        min_lexemes=_int(values.get("min_lexemes", 0), field=f"{prefix}.min_lexemes"),
        min_semantic_rows=_int(
            values.get("min_semantic_rows", 0), field=f"{prefix}.min_semantic_rows"
        ),
        min_entries=_int(values.get("min_entries", 0), field=f"{prefix}.min_entries"),
        min_senses=_int(values.get("min_senses", 0), field=f"{prefix}.min_senses"),
        min_relations=_int(
            values.get("min_relations", 0), field=f"{prefix}.min_relations"
        ),
        min_frequency_lexemes=_int(
            values.get("min_frequency_lexemes", 0),
            field=f"{prefix}.min_frequency_lexemes",
        ),
    )


def _required_text(values: dict[str, Any], field: str, *, prefix: str) -> str:
    value = values.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{prefix}.{field} must be a non-empty string")
    return value.strip()


def _frequency(code: str, values: object) -> FrequencyConfig:
    if values is None:
        return FrequencyConfig(enabled=True)
    if not isinstance(values, dict):
        raise TypeError(f"languages.{code}.frequency must be a table")
    enabled = values.get("enabled", True)
    if not isinstance(enabled, bool):
        raise TypeError(f"languages.{code}.frequency.enabled must be boolean")
    reason = values.get("reason")
    if reason is not None and (not isinstance(reason, str) or not reason.strip()):
        raise ValueError(
            f"languages.{code}.frequency.reason must be a non-empty string"
        )
    if not enabled and reason is None:
        raise ValueError(
            f"languages.{code}.frequency.reason is required when frequency is disabled"
        )
    return FrequencyConfig(enabled, reason.strip() if reason else None)


def _source(code: str, variant: str, values: object) -> LanguageSourceConfig:
    prefix = f"languages.{code}.sources.{variant}"
    if variant not in SOURCE_VARIANTS:
        raise ValueError(f"unknown source variant {variant!r}")
    if not isinstance(values, dict):
        raise TypeError(f"{prefix} must be a table")
    edition = _required_text(values, "wiktionary_edition", prefix=prefix)
    metadata_language = _required_text(values, "metadata_language", prefix=prefix)
    url = _required_text(values, "url", prefix=prefix)
    label = _required_text(values, "label", prefix=prefix)
    page_url = values.get("page_url")
    if page_url is not None and (not isinstance(page_url, str) or not page_url.strip()):
        raise ValueError(f"{prefix}.page_url must be a non-empty string")
    source = LanguageSourceConfig(
        variant,
        edition,
        metadata_language,
        url,
        label,
        page_url.strip() if page_url else None,
        _validation(values["validation"], prefix=f"{prefix}.validation")
        if "validation" in values
        else None,
    )
    parsed = urlsplit(source.url)
    if parsed.scheme != "https" or parsed.hostname != "kaikki.org":
        raise ValueError(f"{prefix}.url must use the kaikki.org HTTPS host")
    if variant == "english":
        if source.wiktionary_edition != "enwiktionary":
            raise ValueError(f"{prefix}.wiktionary_edition must be 'enwiktionary'")
        if source.metadata_language != "en":
            raise ValueError(f"{prefix}.metadata_language must be 'en'")
        if source.url != ENGLISH_RAW_URL:
            raise ValueError(
                f"{prefix}.url must use the English raw Wiktextract endpoint"
            )
        expected_page = f"https://kaikki.org/dictionary/{ENGLISH_PAGE_NAMES[code]}/"
        if source.page_url != expected_page:
            raise ValueError(f"{prefix}.page_url must be {expected_page!r}")
    else:
        expected_edition = EXPECTED_WIKTIONARY_EDITIONS.get(code)
        if (
            expected_edition is not None
            and source.wiktionary_edition != expected_edition
        ):
            raise ValueError(
                f"{prefix}.wiktionary_edition must be {expected_edition!r}"
            )
        if source.metadata_language != code:
            raise ValueError(f"{prefix}.metadata_language must be {code!r}")
        expected_path = EXPECTED_KAIKKI_RAW_PATHS.get(code)
        if expected_path is not None and parsed.path != expected_path:
            raise ValueError(f"{prefix}.url must use path {expected_path!r}")
    return source


def load_config(path: str | Path | None = None) -> DatasetConfig:
    config_path = (
        Path(path) if path is not None else Path(__file__).parents[1] / "datasets.toml"
    )
    with config_path.open("rb") as handle:
        raw = tomllib.load(handle)
    if raw.get("manifest_version") != 2:
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
    variants: dict[str, VariantConfig] = {}
    for name, values in raw_variants.items():
        if not isinstance(name, str) or not isinstance(values, dict):
            raise TypeError("each variant must be a table")
        raw_capabilities = values.get("capabilities")
        if not isinstance(raw_capabilities, list) or not raw_capabilities:
            raise ValueError(f"variants.{name}.capabilities must be a non-empty list")
        if any(not isinstance(value, str) for value in raw_capabilities):
            raise ValueError(f"variants.{name}.capabilities must contain strings")
        unknown = set(raw_capabilities) - set(CAPABILITY_ORDER)
        if unknown:
            raise ValueError(f"variants.{name} has unknown capability {min(unknown)!r}")
        capabilities = tuple(
            value for value in CAPABILITY_ORDER if value in raw_capabilities
        )
        if capabilities[0] != "lexical":
            raise ValueError(f"variants.{name} must include lexical capability")
        profile = values.get("profile")
        if profile is not None and not isinstance(profile, str):
            raise ValueError(f"variants.{name}.profile must be a string")
        recommended = values.get("recommended", False)
        if not isinstance(recommended, bool):
            raise TypeError(f"variants.{name}.recommended must be boolean")
        variants[name] = VariantConfig(name, capabilities, profile, recommended)
    if default_variant not in variants:
        raise ValueError(f"default_variant {default_variant!r} is not configured")
    release_values = raw.get("release", {})
    if not isinstance(release_values, dict):
        raise TypeError("release must be a table")
    raw_defaults = release_values.get("default_variants")
    if raw_defaults is None:
        default_release_variants = tuple(variants)
    elif not isinstance(raw_defaults, list) or not raw_defaults:
        raise ValueError("release.default_variants must be a non-empty list")
    else:
        if any(not isinstance(value, str) or not value for value in raw_defaults):
            raise ValueError("release.default_variants must contain non-empty strings")
        default_release_variants = tuple(raw_defaults)
        if len(set(default_release_variants)) != len(default_release_variants):
            raise ValueError("release.default_variants must not contain duplicates")
        unknown = set(default_release_variants) - set(variants)
        if unknown:
            raise ValueError(
                f"release.default_variants contains unknown variant {min(unknown)!r}"
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
        raw_sources = values.get("sources")
        if not isinstance(raw_sources, dict) or not raw_sources:
            raise ValueError(
                f"languages.{code}.source must be a table; languages.{code}.sources must be a non-empty table"
            )
        sources = {
            variant: _source(code, variant, source_values)
            for variant, source_values in raw_sources.items()
        }
        raw_default = values.get("default_source_variant")
        if not isinstance(raw_default, str) or raw_default not in sources:
            raise ValueError(
                f"languages.{code}.default_source_variant must be configured"
            )
        languages[code] = LanguageConfig(
            code,
            enabled,
            raw_default,
            sources,
            _validation(
                values.get("validation"), prefix=f"languages.{code}.validation"
            ),
            _frequency(code, values.get("frequency")),
        )
    if tuple(languages) != SUPPORTED_BASE_LANGUAGES:
        raise ValueError(
            "configured languages must match the Lexhint base-language registry"
        )
    return DatasetConfig(
        manifest_version=2,
        default_variant=default_variant,
        default_release_variants=default_release_variants,
        source_policy=SourcePolicy(require_hash),
        variants=variants,
        languages=languages,
    )
