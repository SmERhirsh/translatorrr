"""Filesystem path helpers."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from rpg_translator.core.errors import TranslatorError

APP_DIR_NAME = "RPGMakerTranslator"


def user_config_dir(app_dir_name: str = APP_DIR_NAME) -> Path:
    """Return the platform-appropriate user configuration directory."""

    if sys.platform == "win32":
        base = os.environ.get("APPDATA")
        if base:
            return Path(base) / app_dir_name
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / app_dir_name
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / app_dir_name


def user_data_dir(app_dir_name: str = APP_DIR_NAME) -> Path:
    """Return the platform-appropriate user data directory."""

    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / app_dir_name
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / app_dir_name
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / app_dir_name


def ensure_directory(path: Path) -> Path:
    """Create a directory if needed and return the resolved path."""

    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def resolve_existing_directory(path: Path) -> Path:
    """Resolve and validate a directory path."""

    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise TranslatorError(f"Directory does not exist: {resolved}")
    if not resolved.is_dir():
        raise TranslatorError(f"Path is not a directory: {resolved}")
    return resolved


def safe_relative_to(path: Path, root: Path) -> Path:
    """Return ``path`` relative to ``root`` or raise a typed error."""

    try:
        return path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise TranslatorError(
            f"Path is outside the expected root: {path}",
            details={"path": str(path), "root": str(root)},
        ) from exc

