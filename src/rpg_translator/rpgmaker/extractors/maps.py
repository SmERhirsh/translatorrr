"""Extractors for MapInfos.json and MapXXX.json."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from rpg_translator.core.models import JsonPointer, ProjectFile
from rpg_translator.rpgmaker.extractors.base import SegmentBuilder, object_id, object_name
from rpg_translator.rpgmaker.parsers.event_commands import parse_event_commands


class MapInfosExtractor:
    """Extract map names from MapInfos.json."""

    def extract(self, project_file: ProjectFile, data: Any) -> tuple:
        if not isinstance(data, Sequence) or isinstance(data, (str, bytes)):
            return ()

        builder = SegmentBuilder(project_file)
        for index, record in enumerate(data):
            if not isinstance(record, Mapping):
                continue
            value = record.get("name")
            if isinstance(value, str):
                builder.add(
                    text=value,
                    pointer=JsonPointer.root().child(index).child("name"),
                    field_name="name",
                    object_type="map_info",
                    object_id=object_id(record, fallback=index),
                    object_name=object_name(record),
                    metadata={"role": "map_name"},
                )
        return builder.build()


class MapExtractor:
    """Extract map display names and event command text from MapXXX.json."""

    def extract(self, project_file: ProjectFile, data: Any) -> tuple:
        if not isinstance(data, Mapping):
            return ()

        builder = SegmentBuilder(project_file)
        display_name = data.get("displayName")
        if isinstance(display_name, str):
            builder.add(
                text=display_name,
                pointer=JsonPointer.root().child("displayName"),
                field_name="displayName",
                object_type="map",
                map_id=project_file.map_id,
                metadata={"role": "map_display_name"},
            )

        events = data.get("events")
        if not isinstance(events, Sequence) or isinstance(events, (str, bytes)):
            return builder.build()

        for event_index, event in enumerate(events):
            if not isinstance(event, Mapping):
                continue
            event_id = object_id(event, fallback=event_index)
            event_name = object_name(event)
            pages = event.get("pages")
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
                    .child("events")
                    .child(event_index)
                    .child("pages")
                    .child(page_index)
                    .child("list")
                )
                for occurrence in parse_event_commands(commands, base_pointer):
                    builder.add(
                        text=occurrence.text,
                        pointer=occurrence.pointer,
                        field_name=occurrence.field_name,
                        object_type="map_event",
                        object_id=event_id,
                        object_name=event_name,
                        map_id=project_file.map_id,
                        event_id=event_id,
                        page_index=page_index,
                        command_index=occurrence.command_index,
                        command_code=occurrence.command_code,
                        metadata=occurrence.metadata,
                    )
        return builder.build()

