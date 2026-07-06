"""Extractor for Troops.json."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from rpg_translator.core.models import JsonPointer, ProjectFile
from rpg_translator.rpgmaker.extractors.base import SegmentBuilder, object_id, object_name
from rpg_translator.rpgmaker.parsers.event_commands import parse_event_commands


class TroopsExtractor:
    """Extract text from troop battle event pages."""

    def extract(self, project_file: ProjectFile, data: Any) -> tuple:
        if not isinstance(data, Sequence) or isinstance(data, (str, bytes)):
            return ()

        builder = SegmentBuilder(project_file)
        for troop_index, troop in enumerate(data):
            if not isinstance(troop, Mapping):
                continue
            troop_id = object_id(troop, fallback=troop_index)
            troop_name = object_name(troop)
            pages = troop.get("pages")
            if not isinstance(pages, Sequence) or isinstance(pages, (str, bytes)):
                continue

            for page_index, page in enumerate(pages):
                if not isinstance(page, Mapping):
                    continue
                commands = page.get("list")
                if not isinstance(commands, Sequence) or isinstance(commands, (str, bytes)):
                    continue
                base_pointer = (
                    JsonPointer.root()
                    .child(troop_index)
                    .child("pages")
                    .child(page_index)
                    .child("list")
                )
                for occurrence in parse_event_commands(commands, base_pointer):
                    builder.add(
                        text=occurrence.text,
                        pointer=occurrence.pointer,
                        field_name=occurrence.field_name,
                        object_type="troop",
                        object_id=troop_id,
                        object_name=troop_name,
                        page_index=page_index,
                        command_index=occurrence.command_index,
                        command_code=occurrence.command_code,
                        metadata=occurrence.metadata,
                    )
        return builder.build()

