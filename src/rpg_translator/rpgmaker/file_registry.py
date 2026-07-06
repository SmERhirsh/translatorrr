"""RPG Maker data-file classification."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from rpg_translator.core.models import RPGMakerFileKind

MAP_FILE_RE = re.compile(r"^Map(?P<id>\d{3,})\.json$", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class RPGMakerDataFileSpec:
    """Known data file metadata."""

    filename: str
    kind: RPGMakerFileKind
    required: bool = False


class DataFileRegistry:
    """Classifies RPG Maker MV/MZ JSON files."""

    _known_files: dict[str, RPGMakerDataFileSpec] = {
        "Actors.json": RPGMakerDataFileSpec("Actors.json", RPGMakerFileKind.ACTORS),
        "Armors.json": RPGMakerDataFileSpec("Armors.json", RPGMakerFileKind.ARMORS),
        "Classes.json": RPGMakerDataFileSpec("Classes.json", RPGMakerFileKind.CLASSES),
        "CommonEvents.json": RPGMakerDataFileSpec(
            "CommonEvents.json",
            RPGMakerFileKind.COMMON_EVENTS,
        ),
        "Enemies.json": RPGMakerDataFileSpec("Enemies.json", RPGMakerFileKind.ENEMIES),
        "Items.json": RPGMakerDataFileSpec("Items.json", RPGMakerFileKind.ITEMS),
        "MapInfos.json": RPGMakerDataFileSpec("MapInfos.json", RPGMakerFileKind.MAP_INFOS),
        "Skills.json": RPGMakerDataFileSpec("Skills.json", RPGMakerFileKind.SKILLS),
        "States.json": RPGMakerDataFileSpec("States.json", RPGMakerFileKind.STATES),
        "System.json": RPGMakerDataFileSpec("System.json", RPGMakerFileKind.SYSTEM, required=True),
        "Troops.json": RPGMakerDataFileSpec("Troops.json", RPGMakerFileKind.TROOPS),
        "Weapons.json": RPGMakerDataFileSpec("Weapons.json", RPGMakerFileKind.WEAPONS),
        "Animations.json": RPGMakerDataFileSpec("Animations.json", RPGMakerFileKind.ANIMATIONS),
        "Tilesets.json": RPGMakerDataFileSpec("Tilesets.json", RPGMakerFileKind.TILESETS),
    }

    @classmethod
    def classify(cls, path: Path) -> tuple[RPGMakerFileKind, int | None]:
        """Return file kind and optional map ID."""

        name = path.name
        spec = cls._known_files.get(name)
        if spec:
            return spec.kind, None

        map_match = MAP_FILE_RE.match(name)
        if map_match:
            return RPGMakerFileKind.MAP, int(map_match.group("id"))

        if name.lower() == "plugins.js":
            return RPGMakerFileKind.PLUGINS, None

        return RPGMakerFileKind.UNKNOWN, None

    @classmethod
    def required_filenames(cls) -> tuple[str, ...]:
        return tuple(spec.filename for spec in cls._known_files.values() if spec.required)

    @classmethod
    def sort_key(cls, project_file: Path) -> tuple[int, str]:
        """Stable order: System first, registry files, then maps/unknown files."""

        kind, map_id = cls.classify(project_file)
        if kind is RPGMakerFileKind.SYSTEM:
            return (0, project_file.name)
        if kind is RPGMakerFileKind.MAP_INFOS:
            return (1, project_file.name)
        if kind is RPGMakerFileKind.MAP:
            return (20 + (map_id or 0), project_file.name)
        if kind is RPGMakerFileKind.UNKNOWN:
            return (10_000, project_file.name)
        return (10, project_file.name)

