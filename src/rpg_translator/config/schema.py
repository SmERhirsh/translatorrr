"""Typed configuration schema."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from rpg_translator.core.errors import ConfigError
from rpg_translator.core.models import OutputMode, ProviderKind, stable_json_hash

_VALID_LOG_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}


def _as_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ConfigError(f"Configuration section must be a mapping: {name}")
    return value


def _as_str(value: Any, name: str, *, allow_empty: bool = True) -> str:
    if value is None:
        text = ""
    elif isinstance(value, str):
        text = value
    else:
        raise ConfigError(f"Configuration value must be a string: {name}")
    if not allow_empty and not text:
        raise ConfigError(f"Configuration value cannot be empty: {name}")
    return text


def _as_bool(value: Any, name: str) -> bool:
    if isinstance(value, bool):
        return value
    raise ConfigError(f"Configuration value must be a boolean: {name}")


def _as_int(value: Any, name: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"Configuration value must be an integer: {name}")
    if minimum is not None and value < minimum:
        raise ConfigError(f"Configuration value is too small: {name}", details={"minimum": minimum})
    return value


def _as_float(value: Any, name: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"Configuration value must be a number: {name}")
    number = float(value)
    if minimum is not None and number < minimum:
        raise ConfigError(f"Configuration value is too small: {name}", details={"minimum": minimum})
    return number


def _freeze_mapping(mapping: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(dict(mapping))


def _read_optional_str(mapping: Mapping[str, Any], key: str) -> str | None:
    value = mapping.get(key, "")
    text = _as_str(value, key)
    return text or None


@dataclass(frozen=True, slots=True)
class ProviderProfile:
    """One named provider profile."""

    name: str
    kind: ProviderKind
    base_url: str
    model: str
    api_key: str | None = None
    api_key_env: str | None = None
    timeout_seconds: float = 120.0
    max_retries: int = 2
    temperature: float = 0.2
    top_p: float = 0.9
    max_tokens: int = 4096
    extra_headers: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ConfigError("Provider timeout must be greater than zero")
        if self.max_retries < 0:
            raise ConfigError("Provider max_retries cannot be negative")
        if not 0 <= self.temperature <= 2:
            raise ConfigError("Provider temperature must be between 0 and 2")
        if not 0 < self.top_p <= 1:
            raise ConfigError("Provider top_p must be greater than 0 and at most 1")
        if self.max_tokens <= 0:
            raise ConfigError("Provider max_tokens must be greater than zero")
        object.__setattr__(self, "extra_headers", MappingProxyType(dict(self.extra_headers)))

    @classmethod
    def from_mapping(cls, name: str, value: Mapping[str, Any]) -> "ProviderProfile":
        kind_value = _as_str(value.get("kind"), f"provider.profiles.{name}.kind", allow_empty=False)
        try:
            kind = ProviderKind(kind_value)
        except ValueError as exc:
            raise ConfigError(
                f"Unsupported provider kind: {kind_value}",
                details={"profile": name, "kind": kind_value},
            ) from exc

        headers_raw = _as_mapping(value.get("extra_headers", {}), "extra_headers")
        headers = {
            _as_str(header_key, "extra_headers key", allow_empty=False): _as_str(
                header_value,
                f"extra_headers.{header_key}",
            )
            for header_key, header_value in headers_raw.items()
        }

        return cls(
            name=name,
            kind=kind,
            base_url=_as_str(value.get("base_url"), f"provider.profiles.{name}.base_url"),
            model=_as_str(value.get("model"), f"provider.profiles.{name}.model"),
            api_key=_read_optional_str(value, "api_key"),
            api_key_env=_read_optional_str(value, "api_key_env"),
            timeout_seconds=_as_float(value.get("timeout_seconds", 120), "timeout_seconds", minimum=1),
            max_retries=_as_int(value.get("max_retries", 2), "max_retries", minimum=0),
            temperature=_as_float(value.get("temperature", 0.2), "temperature", minimum=0),
            top_p=_as_float(value.get("top_p", 0.9), "top_p", minimum=0.0001),
            max_tokens=_as_int(value.get("max_tokens", 4096), "max_tokens", minimum=1),
            extra_headers=headers,
        )

    @property
    def effective_api_key(self) -> str | None:
        if self.api_key:
            return self.api_key
        if self.api_key_env:
            return os.environ.get(self.api_key_env) or None
        return None

    def to_dict(self, *, include_secrets: bool = False) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind.value,
            "base_url": self.base_url,
            "model": self.model,
            "api_key": self.api_key if include_secrets else bool(self.api_key),
            "api_key_env": self.api_key_env,
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_tokens,
            "extra_headers": dict(self.extra_headers),
        }


@dataclass(frozen=True, slots=True)
class TranslationSettings:
    """Provider-independent translation runtime settings."""

    batch_max_segments: int = 16
    batch_max_chars: int = 6000
    request_timeout_seconds: float = 120.0
    retry_failed_batches: bool = True
    max_batch_retries: int = 2

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "TranslationSettings":
        return cls(
            batch_max_segments=_as_int(value.get("batch_max_segments", 16), "batch_max_segments", minimum=1),
            batch_max_chars=_as_int(value.get("batch_max_chars", 6000), "batch_max_chars", minimum=100),
            request_timeout_seconds=_as_float(
                value.get("request_timeout_seconds", 120),
                "request_timeout_seconds",
                minimum=1,
            ),
            retry_failed_batches=_as_bool(value.get("retry_failed_batches", True), "retry_failed_batches"),
            max_batch_retries=_as_int(value.get("max_batch_retries", 2), "max_batch_retries", minimum=0),
        )


@dataclass(frozen=True, slots=True)
class ExtractionSettings:
    """Which RPG Maker fields are eligible for extraction."""

    translate_database_names: bool = True
    translate_database_descriptions: bool = True
    translate_dialogue: bool = True
    translate_choices: bool = True
    translate_scroll_text: bool = True
    translate_map_names: bool = False
    translate_notes: bool = False
    translate_comments: bool = False
    translate_plugin_parameters: bool = False

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExtractionSettings":
        return cls(
            translate_database_names=_as_bool(
                value.get("translate_database_names", True),
                "translate_database_names",
            ),
            translate_database_descriptions=_as_bool(
                value.get("translate_database_descriptions", True),
                "translate_database_descriptions",
            ),
            translate_dialogue=_as_bool(value.get("translate_dialogue", True), "translate_dialogue"),
            translate_choices=_as_bool(value.get("translate_choices", True), "translate_choices"),
            translate_scroll_text=_as_bool(
                value.get("translate_scroll_text", True),
                "translate_scroll_text",
            ),
            translate_map_names=_as_bool(value.get("translate_map_names", False), "translate_map_names"),
            translate_notes=_as_bool(value.get("translate_notes", False), "translate_notes"),
            translate_comments=_as_bool(value.get("translate_comments", False), "translate_comments"),
            translate_plugin_parameters=_as_bool(
                value.get("translate_plugin_parameters", False),
                "translate_plugin_parameters",
            ),
        )


@dataclass(frozen=True, slots=True)
class OutputSettings:
    """Output generation settings for later phases."""

    mode: OutputMode = OutputMode.TRANSLATED_COPY
    directory_suffix: str = "_ru"
    make_backups: bool = True
    write_manifest: bool = True
    preserve_json_indentation: bool = True

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "OutputSettings":
        mode_value = _as_str(value.get("mode", OutputMode.TRANSLATED_COPY.value), "output.mode")
        try:
            mode = OutputMode(mode_value)
        except ValueError as exc:
            raise ConfigError(f"Unsupported output mode: {mode_value}") from exc
        return cls(
            mode=mode,
            directory_suffix=_as_str(value.get("directory_suffix", "_ru"), "directory_suffix"),
            make_backups=_as_bool(value.get("make_backups", True), "make_backups"),
            write_manifest=_as_bool(value.get("write_manifest", True), "write_manifest"),
            preserve_json_indentation=_as_bool(
                value.get("preserve_json_indentation", True),
                "preserve_json_indentation",
            ),
        )


@dataclass(frozen=True, slots=True)
class LoggingSettings:
    """Logging configuration."""

    level: str = "INFO"
    console_enabled: bool = True
    file_enabled: bool = True
    json_file: bool = True
    max_bytes: int = 5_242_880
    backup_count: int = 5
    log_dir: str | None = None

    def __post_init__(self) -> None:
        normalized = self.level.upper()
        if normalized not in _VALID_LOG_LEVELS:
            raise ConfigError(f"Unsupported log level: {self.level}")
        object.__setattr__(self, "level", normalized)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "LoggingSettings":
        log_dir = _read_optional_str(value, "log_dir")
        return cls(
            level=_as_str(value.get("level", "INFO"), "logging.level", allow_empty=False),
            console_enabled=_as_bool(value.get("console_enabled", True), "console_enabled"),
            file_enabled=_as_bool(value.get("file_enabled", True), "file_enabled"),
            json_file=_as_bool(value.get("json_file", True), "json_file"),
            max_bytes=_as_int(value.get("max_bytes", 5_242_880), "max_bytes", minimum=1024),
            backup_count=_as_int(value.get("backup_count", 5), "backup_count", minimum=0),
            log_dir=log_dir,
        )


@dataclass(frozen=True, slots=True)
class StorageSettings:
    """Persistent storage configuration."""

    database_path: str | None = None
    cache_enabled: bool = True
    translation_memory_enabled: bool = True

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "StorageSettings":
        return cls(
            database_path=_read_optional_str(value, "database_path"),
            cache_enabled=_as_bool(value.get("cache_enabled", True), "cache_enabled"),
            translation_memory_enabled=_as_bool(
                value.get("translation_memory_enabled", True),
                "translation_memory_enabled",
            ),
        )


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Fully resolved application configuration."""

    app_name: str
    source_language: str
    target_language: str
    active_provider: str
    providers: Mapping[str, ProviderProfile]
    translation: TranslationSettings
    extraction: ExtractionSettings
    output: OutputSettings
    logging: LoggingSettings
    storage: StorageSettings

    def __post_init__(self) -> None:
        if self.active_provider not in self.providers:
            raise ConfigError(
                f"Active provider profile does not exist: {self.active_provider}",
                details={"active_provider": self.active_provider},
            )
        object.__setattr__(self, "providers", _freeze_mapping(self.providers))

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AppConfig":
        app = _as_mapping(value.get("app", {}), "app")
        provider = _as_mapping(value.get("provider", {}), "provider")
        profiles_raw = _as_mapping(provider.get("profiles", {}), "provider.profiles")
        if not profiles_raw:
            raise ConfigError("At least one provider profile must be configured")

        profiles = {
            _as_str(name, "provider profile name", allow_empty=False): ProviderProfile.from_mapping(
                str(name),
                _as_mapping(profile_value, f"provider.profiles.{name}"),
            )
            for name, profile_value in profiles_raw.items()
        }

        return cls(
            app_name=_as_str(app.get("name", "RPG Maker Translator"), "app.name", allow_empty=False),
            source_language=_as_str(app.get("source_language", "en"), "app.source_language", allow_empty=False),
            target_language=_as_str(app.get("target_language", "ru"), "app.target_language", allow_empty=False),
            active_provider=_as_str(
                provider.get("active_profile", "lm_studio"),
                "provider.active_profile",
                allow_empty=False,
            ),
            providers=profiles,
            translation=TranslationSettings.from_mapping(
                _as_mapping(value.get("translation", {}), "translation"),
            ),
            extraction=ExtractionSettings.from_mapping(
                _as_mapping(value.get("extraction", {}), "extraction"),
            ),
            output=OutputSettings.from_mapping(_as_mapping(value.get("output", {}), "output")),
            logging=LoggingSettings.from_mapping(_as_mapping(value.get("logging", {}), "logging")),
            storage=StorageSettings.from_mapping(_as_mapping(value.get("storage", {}), "storage")),
        )

    @property
    def active_provider_profile(self) -> ProviderProfile:
        return self.providers[self.active_provider]

    @property
    def stable_hash(self) -> str:
        return stable_json_hash(self.to_dict(include_secrets=False))

    def to_dict(self, *, include_secrets: bool = False) -> dict[str, Any]:
        return {
            "app": {
                "name": self.app_name,
                "source_language": self.source_language,
                "target_language": self.target_language,
            },
            "provider": {
                "active_profile": self.active_provider,
                "profiles": {
                    name: profile.to_dict(include_secrets=include_secrets)
                    for name, profile in self.providers.items()
                },
            },
            "translation": asdict(self.translation),
            "extraction": asdict(self.extraction),
            "output": {
                **asdict(self.output),
                "mode": self.output.mode.value,
            },
            "logging": asdict(self.logging),
            "storage": asdict(self.storage),
        }
