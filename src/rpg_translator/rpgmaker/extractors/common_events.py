"""Extractor for CommonEvents.json."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from rpg_translator.core.models import JsonPointer, ProjectFile
from rpg_translator.rpgmaker.extractors.base import SegmentBuilder, object_id, object_name
from rpg_translator.rpgmaker.parsers.event_commands import parse_event_commands


class CommonEventsExtractor:
    """Extract text from common event command lists."""

    def extract(self, project_file: ProjectFile, data: Any) -> tuple:
        if not isinstance(data, Sequence) or isinstance(data, (str, bytes)):
            return ()

        builder = SegmentBuilder(project_file)
        for index, event in enumerate(data):
            if not isinstance(event, Mapping):
                continue
            commands = event.get("list")
            if not isinstance(commands, Sequence) or isinstance(commands, (str, bytes)):
                continue
            event_id = object_id(event, fallback=index)
            event_name = object_name(event)
            base_pointer = JsonPointer.root().child(index).child("list")
            for occurrence in parse_event_commands(commands, base_pointer):
                builder.add(
                    text=occurrence.text,
                    pointer=occurrence.pointer,
                    field_name=occurrence.field_name,
                    object_type="common_event",
                    object_id=event_id,
                    object_name=event_name,
                    command_index=occurrence.command_index,
                    command_code=occurrence.command_code,
                    metadata=occurrence.metadata,
                )
        return builder.build()

