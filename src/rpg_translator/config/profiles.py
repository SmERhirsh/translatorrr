"""Configuration path conventions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rpg_translator.core.paths import user_config_dir


@dataclass(frozen=True, slots=True)
class ConfigPaths:
    """Resolved configuration file locations."""

    defaults: Path
    user: Path | None = None
    project: Path | None = None


def default_user_config_path() -> Path:
    """Return the default per-user configuration path."""

    return user_config_dir() / "config.toml"


def default_project_config_path(project_root: Path) -> Path:
    """Return the default per-project configuration path."""

    return project_root / ".rpg_translator.toml"

