"""Layered TOML configuration loader."""

from __future__ import annotations

import shutil
import tomllib
from pathlib import Path
from typing import Any, Mapping

from rpg_translator.config.profiles import ConfigPaths, default_user_config_path
from rpg_translator.config.schema import AppConfig
from rpg_translator.core.errors import ConfigError

DEFAULT_CONFIG_PATH = Path(__file__).with_name("defaults.toml")


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively merge ``override`` into ``base`` without mutating either."""

    merged: dict[str, Any] = dict(base)
    for key, value in override.items():
        existing = merged.get(key)
        if isinstance(existing, Mapping) and isinstance(value, Mapping):
            merged[key] = deep_merge(existing, value)
        else:
            merged[key] = value
    return merged


def read_toml_file(path: Path, *, required: bool = False) -> dict[str, Any]:
    """Read a TOML file, returning an empty mapping for missing optional files."""

    resolved = path.expanduser()
    if not resolved.exists():
        if required:
            raise ConfigError(f"Configuration file does not exist: {resolved}")
        return {}
    if not resolved.is_file():
        raise ConfigError(f"Configuration path is not a file: {resolved}")
    try:
        with resolved.open("rb") as handle:
            return tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(
            f"Configuration file is not valid TOML: {resolved}",
            details={"path": str(resolved), "error": str(exc)},
        ) from exc
    except OSError as exc:
        raise ConfigError(
            f"Configuration file could not be read: {resolved}",
            details={"path": str(resolved), "error": str(exc)},
        ) from exc


class ConfigLoader:
    """Load configuration from defaults, user file, project file, and overrides."""

    def __init__(
        self,
        paths: ConfigPaths | None = None,
    ) -> None:
        self.paths = paths or ConfigPaths(defaults=DEFAULT_CONFIG_PATH, user=default_user_config_path())

    def load(
        self,
        *,
        project_config_path: Path | None = None,
        overrides: Mapping[str, Any] | None = None,
    ) -> AppConfig:
        default_values = read_toml_file(self.paths.defaults, required=True)
        user_values = read_toml_file(self.paths.user, required=False) if self.paths.user else {}

        effective_project_path = project_config_path or self.paths.project
        project_values = (
            read_toml_file(effective_project_path, required=False) if effective_project_path else {}
        )

        merged = deep_merge(default_values, user_values)
        merged = deep_merge(merged, project_values)
        if overrides:
            merged = deep_merge(merged, overrides)
        return AppConfig.from_mapping(merged)


def load_config(
    *,
    project_config_path: Path | None = None,
    overrides: Mapping[str, Any] | None = None,
) -> AppConfig:
    """Load application configuration with default path conventions."""

    return ConfigLoader().load(project_config_path=project_config_path, overrides=overrides)


def write_default_user_config(path: Path | None = None, *, overwrite: bool = False) -> Path:
    """Create a user configuration file from packaged defaults."""

    destination = (path or default_user_config_path()).expanduser()
    if destination.exists() and not overwrite:
        raise ConfigError(
            f"Configuration file already exists: {destination}",
            details={"path": str(destination)},
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(DEFAULT_CONFIG_PATH, destination)
    return destination

