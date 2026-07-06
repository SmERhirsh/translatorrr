"""Shared extraction primitives."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Protocol

from rpg_translator.core.models import (
    JsonPointer,
    ProjectFile,
    RPGMakerFileKind,
    SegmentContext,
    TextSegment,
)
from rpg_translator.translation.placeholderizer import protect_text


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    """Segments extracted from one or more RPG Maker data files."""

    segments: tuple[TextSegment, ...] = ()

    def by_file_kind(self, kind: RPGMakerFileKind) -> tuple[TextSegment, ...]:
        return tuple(segment for segment in self.segments if segment.context.file_kind is kind)


class DataFileExtractor(Protocol):
    """Extractor interface for one RPG Maker data-file kind."""

    def extract(self, project_file: ProjectFile, data: Any) -> tuple[TextSegment, ...]:
        """Extract translatable segments from decoded JSON data."""


@dataclass(slots=True)
class SegmentBuilder:
    """Build stable TextSegment objects for one project file."""

    project_file: ProjectFile
    _segments: list[TextSegment] = field(default_factory=list)

    def add(
        self,
        *,
        text: str,
        pointer: JsonPointer,
        field_name: str,
        object_type: str | None = None,
        object_id: int | None = None,
        object_name: str | None = None,
        map_id: int | None = None,
        event_id: int | None = None,
        page_index: int | None = None,
        command_index: int | None = None,
        command_code: int | None = None,
        notes: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        """Add a non-empty segment."""

        if not is_translatable_text(text):
            return

        protected = protect_text(text)
        segment_metadata = {
            "relative_path": self.project_file.relative_path.as_posix(),
            "json_pointer": pointer.as_string(),
            "protected_source_text": protected.protected_text,
        }
        if metadata:
            segment_metadata.update(metadata)

        context = SegmentContext(
            file_kind=self.project_file.kind,
            json_pointer=pointer,
            field_name=field_name,
            object_type=object_type,
            object_id=object_id,
            object_name=object_name,
            map_id=map_id if map_id is not None else self.project_file.map_id,
            event_id=event_id,
            page_index=page_index,
            command_index=command_index,
            command_code=command_code,
            notes=notes,
        )
        self._segments.append(
            TextSegment(
                segment_id=make_segment_id(
                    self.project_file.relative_path,
                    pointer,
                    field_name,
                ),
                source_text=text,
                source_file=self.project_file.absolute_path,
                context=context,
                protected_tokens=protected.tokens,
                metadata=segment_metadata,
            ),
        )

    def build(self) -> tuple[TextSegment, ...]:
        return tuple(self._segments)


def make_segment_id(relative_path: Path, pointer: JsonPointer, field_name: str) -> str:
    """Build a stable ID from file path, JSON pointer, and field role."""

    raw = f"{relative_path.as_posix()}|{pointer.as_string()}|{field_name}"
    return f"seg_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:24]}"


def is_translatable_text(value: Any) -> bool:
    """Return whether a value is a non-empty string in a translatable field."""

    return isinstance(value, str) and bool(value.strip())


def object_id(record: Mapping[str, Any], fallback: int | None = None) -> int | None:
    value = record.get("id")
    if isinstance(value, int):
        return value
    return fallback


def object_name(record: Mapping[str, Any]) -> str | None:
    value = record.get("name")
    if isinstance(value, str) and value.strip():
        return value
    return None

