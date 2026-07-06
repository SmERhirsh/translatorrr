"""Core domain models shared by scanners, translators, storage, and output."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence


class RPGMakerEngine(str, Enum):
    """Supported RPG Maker runtimes."""

    MV = "mv"
    MZ = "mz"


class RPGMakerFileKind(str, Enum):
    """Known RPG Maker data file categories."""

    ACTORS = "actors"
    ARMORS = "armors"
    CLASSES = "classes"
    COMMON_EVENTS = "common_events"
    ENEMIES = "enemies"
    ITEMS = "items"
    MAP = "map"
    MAP_INFOS = "map_infos"
    SKILLS = "skills"
    STATES = "states"
    SYSTEM = "system"
    TROOPS = "troops"
    WEAPONS = "weapons"
    ANIMATIONS = "animations"
    TILESETS = "tilesets"
    PLUGINS = "plugins"
    UNKNOWN = "unknown"


class SegmentStatus(str, Enum):
    """Lifecycle state for an extracted text segment."""

    PENDING = "pending"
    CACHED = "cached"
    TRANSLATED = "translated"
    FAILED = "failed"
    SKIPPED = "skipped"
    NEEDS_REVIEW = "needs_review"


class PlaceholderKind(str, Enum):
    """Kinds of protected syntax that must survive translation unchanged."""

    RPGMAKER_CONTROL_CODE = "rpgmaker_control_code"
    FORMAT_ARGUMENT = "format_argument"
    HTML_TAG = "html_tag"
    ESCAPE_SEQUENCE = "escape_sequence"
    PLUGIN_TAG = "plugin_tag"
    LINE_BREAK = "line_break"
    UNKNOWN = "unknown"


class ProviderKind(str, Enum):
    """LLM provider families supported by the planned provider abstraction."""

    LM_STUDIO = "lm_studio"
    OLLAMA = "ollama"
    OPENAI = "openai"
    OPENAI_COMPATIBLE = "openai_compatible"


class JobStatus(str, Enum):
    """Persistent translation job state."""

    CREATED = "created"
    SCANNING = "scanning"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OutputMode(str, Enum):
    """How translated files should be produced in later phases."""

    TRANSLATED_COPY = "translated_copy"
    DATA_TRANSLATED = "data_translated"
    PATCH_WITH_BACKUP = "patch_with_backup"
    MANIFEST_ONLY = "manifest_only"


class ValidationSeverity(str, Enum):
    """Severity for validation and quality issues."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class JsonPointer:
    """RFC 6901-like JSON pointer with typed parts for arrays."""

    parts: tuple[str | int, ...] = ()

    @classmethod
    def root(cls) -> "JsonPointer":
        return cls(())

    @classmethod
    def from_parts(cls, parts: Sequence[str | int]) -> "JsonPointer":
        return cls(tuple(parts))

    def child(self, part: str | int) -> "JsonPointer":
        return JsonPointer((*self.parts, part))

    def as_string(self) -> str:
        if not self.parts:
            return ""
        encoded = []
        for part in self.parts:
            text = str(part).replace("~", "~0").replace("/", "~1")
            encoded.append(text)
        return "/" + "/".join(encoded)

    def __str__(self) -> str:
        return self.as_string()


@dataclass(frozen=True, slots=True)
class FileFingerprint:
    """Stable identity for a source file at scan time."""

    size_bytes: int
    modified_at: datetime
    sha256: str

    @classmethod
    def from_path(cls, path: Path) -> "FileFingerprint":
        stat = path.stat()
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return cls(
            size_bytes=stat.st_size,
            modified_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
            sha256=digest.hexdigest(),
        )


@dataclass(frozen=True, slots=True)
class ProjectFile:
    """One JSON data file belonging to a detected RPG Maker project."""

    absolute_path: Path
    relative_path: Path
    kind: RPGMakerFileKind
    fingerprint: FileFingerprint
    map_id: int | None = None


@dataclass(frozen=True, slots=True)
class GameProject:
    """Detected RPG Maker MV/MZ project metadata."""

    root_path: Path
    data_path: Path
    engine: RPGMakerEngine
    title: str
    files: tuple[ProjectFile, ...]
    project_file: Path | None = None
    executable_path: Path | None = None
    detected_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))

    def file_by_kind(self, kind: RPGMakerFileKind) -> tuple[ProjectFile, ...]:
        return tuple(project_file for project_file in self.files if project_file.kind is kind)


@dataclass(frozen=True, slots=True)
class SegmentContext:
    """Location and semantic context for an extracted text segment."""

    file_kind: RPGMakerFileKind
    json_pointer: JsonPointer
    field_name: str | None = None
    object_type: str | None = None
    object_id: int | None = None
    object_name: str | None = None
    map_id: int | None = None
    event_id: int | None = None
    page_index: int | None = None
    command_index: int | None = None
    command_code: int | None = None
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class ProtectedToken:
    """A token replaced before translation and restored afterward."""

    placeholder: str
    original: str
    kind: PlaceholderKind
    index: int


def stable_text_hash(text: str) -> str:
    """Return a stable SHA-256 hash for normalized text identity."""

    normalized = "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").split("\n")).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class TextSegment:
    """A unit of text eligible for translation."""

    segment_id: str
    source_text: str
    source_file: Path
    context: SegmentContext
    status: SegmentStatus = SegmentStatus.PENDING
    translation: str | None = None
    protected_tokens: tuple[ProtectedToken, ...] = ()
    source_hash: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source_hash:
            object.__setattr__(self, "source_hash", stable_text_hash(self.source_text))


@dataclass(frozen=True, slots=True)
class GlossaryEntry:
    """Project or global glossary constraint."""

    source: str
    target: str
    forbidden_targets: tuple[str, ...] = ()
    note: str | None = None
    case_sensitive: bool = False
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class GlossaryHit:
    """Glossary match found in a segment."""

    entry: GlossaryEntry
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class ProviderModel:
    """Provider/model identity captured for auditability."""

    provider: ProviderKind
    model: str
    base_url: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderUsage:
    """Token usage returned by a provider when available."""

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class TranslationAttempt:
    """Metadata for one provider attempt."""

    provider_model: ProviderModel
    started_at: datetime
    finished_at: datetime | None = None
    usage: ProviderUsage | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class TranslationBatch:
    """Batch of segment IDs scheduled together."""

    batch_id: str
    segment_ids: tuple[str, ...]
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    attempts: tuple[TranslationAttempt, ...] = ()


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """Validation result attached to a segment or batch."""

    severity: ValidationSeverity
    message: str
    segment_id: str | None = None
    code: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class JobProgress:
    """Progress counters persisted for resumable jobs."""

    total_segments: int = 0
    pending_segments: int = 0
    translated_segments: int = 0
    failed_segments: int = 0
    skipped_segments: int = 0
    needs_review_segments: int = 0

    @property
    def completed_segments(self) -> int:
        return self.translated_segments + self.skipped_segments


@dataclass(frozen=True, slots=True)
class TranslationJob:
    """Persistent job identity and high-level state."""

    job_id: str
    project_root: Path
    source_language: str
    target_language: str
    status: JobStatus = JobStatus.CREATED
    progress: JobProgress = field(default_factory=JobProgress)
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    config_hash: str | None = None


@dataclass(frozen=True, slots=True)
class OutputManifestEntry:
    """One changed output file entry."""

    source_path: Path
    output_path: Path
    source_sha256: str
    output_sha256: str
    changed_segments: int


def stable_json_hash(value: Any) -> str:
    """Hash structured data with deterministic key ordering."""

    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

