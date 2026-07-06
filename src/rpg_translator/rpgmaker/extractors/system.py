"""Extractor for System.json."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from rpg_translator.core.models import JsonPointer, ProjectFile
from rpg_translator.rpgmaker.extractors.base import SegmentBuilder


class SystemExtractor:
    """Extract player-facing text from RPG Maker System.json."""

    _top_level_fields = ("gameTitle", "currencyUnit")
    _array_fields = (
        "elements",
        "skillTypes",
        "weaponTypes",
        "armorTypes",
        "equipTypes",
        "switches",
        "variables",
    )
    _term_array_fields = ("basic", "params", "commands")

    def extract(self, project_file: ProjectFile, data: Any) -> tuple:
        if not isinstance(data, Mapping):
            return ()

        builder = SegmentBuilder(project_file)
        root = JsonPointer.root()

        for field_name in self._top_level_fields:
            value = data.get(field_name)
            if isinstance(value, str):
                builder.add(
                    text=value,
                    pointer=root.child(field_name),
                    field_name=field_name,
                    object_type="system",
                    metadata={"role": f"system_{field_name}"},
                )

        for field_name in self._array_fields:
            value = data.get(field_name)
            self._extract_string_array(
                builder,
                value,
                root.child(field_name),
                field_name=field_name,
                object_type=f"system_{field_name}",
                role=f"system_{field_name}",
            )

        terms = data.get("terms")
        if isinstance(terms, Mapping):
            terms_pointer = root.child("terms")
            for field_name in self._term_array_fields:
                value = terms.get(field_name)
                self._extract_string_array(
                    builder,
                    value,
                    terms_pointer.child(field_name),
                    field_name=field_name,
                    object_type="system_terms",
                    role=f"system_terms_{field_name}",
                )

            messages = terms.get("messages")
            if isinstance(messages, Mapping):
                for key, value in messages.items():
                    if not isinstance(key, str) or not isinstance(value, str):
                        continue
                    builder.add(
                        text=value,
                        pointer=terms_pointer.child("messages").child(key),
                        field_name=key,
                        object_type="system_messages",
                        metadata={"role": "system_message"},
                    )

        return builder.build()

    def _extract_string_array(
        self,
        builder: SegmentBuilder,
        value: Any,
        pointer: JsonPointer,
        *,
        field_name: str,
        object_type: str,
        role: str,
    ) -> None:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            return
        for index, item in enumerate(value):
            if not isinstance(item, str):
                continue
            builder.add(
                text=item,
                pointer=pointer.child(index),
                field_name=field_name,
                object_type=object_type,
                object_id=index,
                metadata={"role": role, "array_index": index},
            )

