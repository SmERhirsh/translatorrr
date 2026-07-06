"""Typed application errors.

The application distinguishes recoverable data/provider problems from hard
failures so the GUI can later decide whether to pause, retry, or stop a job.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(slots=True)
class TranslatorError(Exception):
    """Base class for expected application errors."""

    message: str
    details: Mapping[str, Any] = field(default_factory=dict)
    recoverable: bool = False

    def __post_init__(self) -> None:
        Exception.__init__(self, self.message)

    @property
    def user_message(self) -> str:
        return self.message


class ConfigError(TranslatorError):
    """Raised when configuration cannot be loaded or validated."""


class ProjectDetectionError(TranslatorError):
    """Raised when a path cannot be recognized as an RPG Maker MV/MZ project."""


class JsonReadError(TranslatorError):
    """Raised when an RPG Maker JSON file cannot be decoded."""


class ExtractionError(TranslatorError):
    """Reserved for extractor failures in later phases."""


class ProviderConnectionError(TranslatorError):
    """Reserved for provider connectivity failures in later phases."""


class ProviderRateLimitError(TranslatorError):
    """Reserved for rate-limit handling in later phases."""


class InvalidTranslationError(TranslatorError):
    """Reserved for invalid provider responses in later phases."""


class PlaceholderMismatchError(TranslatorError):
    """Reserved for protected-token validation failures in later phases."""


class OutputWriteError(TranslatorError):
    """Reserved for output generation failures in later phases."""

