"""Extractors for RPG Maker database arrays."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from rpg_translator.core.models import JsonPointer, ProjectFile, RPGMakerFileKind
from rpg_translator.rpgmaker.extractors.base import SegmentBuilder, object_id, object_name


@dataclass(frozen=True, slots=True)
class FieldSpec:
    """One translatable field in a database object."""

    name: str
    role: str


DATABASE_FIELD_SPECS: dict[RPGMakerFileKind, tuple[FieldSpec, ...]] = {
    RPGMakerFileKind.ACTORS: (
        FieldSpec("name", "actor_name"),
        FieldSpec("nickname", "actor_nickname"),
        FieldSpec("profile", "actor_profile"),
    ),
    RPGMakerFileKind.CLASSES: (FieldSpec("name", "class_name"),),
    RPGMakerFileKind.ITEMS: (
        FieldSpec("name", "item_name"),
        FieldSpec("description", "item_description"),
    ),
    RPGMakerFileKind.SKILLS: (
        FieldSpec("name", "skill_name"),
        FieldSpec("description", "skill_description"),
        FieldSpec("message1", "skill_message"),
        FieldSpec("message2", "skill_message"),
    ),
    RPGMakerFileKind.WEAPONS: (
        FieldSpec("name", "weapon_name"),
        FieldSpec("description", "weapon_description"),
    ),
    RPGMakerFileKind.ARMORS: (
        FieldSpec("name", "armor_name"),
        FieldSpec("description", "armor_description"),
    ),
    RPGMakerFileKind.STATES: (
        FieldSpec("name", "state_name"),
        FieldSpec("message1", "state_message"),
        FieldSpec("message2", "state_message"),
        FieldSpec("message3", "state_message"),
        FieldSpec("message4", "state_message"),
    ),
    RPGMakerFileKind.ENEMIES: (FieldSpec("name", "enemy_name"),),
}


class DatabaseArrayExtractor:
    """Extract translatable fields from RPG Maker database arrays."""

    def __init__(self, kind: RPGMakerFileKind, object_type: str) -> None:
        self.kind = kind
        self.object_type = object_type
        self.fields = DATABASE_FIELD_SPECS[kind]

    def extract(self, project_file: ProjectFile, data: Any) -> tuple:
        if not isinstance(data, Sequence) or isinstance(data, (str, bytes)):
            return ()

        builder = SegmentBuilder(project_file)
        for index, record in enumerate(data):
            if not isinstance(record, Mapping):
                continue
            record_id = object_id(record, fallback=index)
            record_name = object_name(record)
            record_pointer = JsonPointer.root().child(index)
            for field in self.fields:
                value = record.get(field.name)
                if isinstance(value, str):
                    builder.add(
                        text=value,
                        pointer=record_pointer.child(field.name),
                        field_name=field.name,
                        object_type=self.object_type,
                        object_id=record_id,
                        object_name=record_name,
                        metadata={"role": field.role},
                    )
        return builder.build()

