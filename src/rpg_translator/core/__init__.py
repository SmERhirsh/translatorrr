"""Core domain types and errors."""

from rpg_translator.core.errors import (
    ConfigError,
    JsonReadError,
    ProjectDetectionError,
    TranslatorError,
)
from rpg_translator.core.models import (
    FileFingerprint,
    GameProject,
    JsonPointer,
    ProjectFile,
    RPGMakerEngine,
    RPGMakerFileKind,
    SegmentStatus,
    TextSegment,
)

__all__ = [
    "ConfigError",
    "FileFingerprint",
    "GameProject",
    "JsonPointer",
    "JsonReadError",
    "ProjectDetectionError",
    "ProjectFile",
    "RPGMakerEngine",
    "RPGMakerFileKind",
    "SegmentStatus",
    "TextSegment",
    "TranslatorError",
]

