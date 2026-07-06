"""Extractor registry and project-level extraction entry points."""

from __future__ import annotations

from typing import Any

from rpg_translator.core.models import GameProject, ProjectFile, RPGMakerFileKind, TextSegment
from rpg_translator.rpgmaker.extractors.base import DataFileExtractor, ExtractionResult
from rpg_translator.rpgmaker.extractors.common_events import CommonEventsExtractor
from rpg_translator.rpgmaker.extractors.database import DatabaseArrayExtractor
from rpg_translator.rpgmaker.extractors.maps import MapExtractor, MapInfosExtractor
from rpg_translator.rpgmaker.extractors.system import SystemExtractor
from rpg_translator.rpgmaker.extractors.troops import TroopsExtractor
from rpg_translator.rpgmaker.json_loader import load_data_file, load_project_data_files


def default_extractors() -> dict[RPGMakerFileKind, DataFileExtractor]:
    """Return the default extractor registry."""

    return {
        RPGMakerFileKind.ACTORS: DatabaseArrayExtractor(RPGMakerFileKind.ACTORS, "actor"),
        RPGMakerFileKind.CLASSES: DatabaseArrayExtractor(RPGMakerFileKind.CLASSES, "class"),
        RPGMakerFileKind.ITEMS: DatabaseArrayExtractor(RPGMakerFileKind.ITEMS, "item"),
        RPGMakerFileKind.SKILLS: DatabaseArrayExtractor(RPGMakerFileKind.SKILLS, "skill"),
        RPGMakerFileKind.WEAPONS: DatabaseArrayExtractor(RPGMakerFileKind.WEAPONS, "weapon"),
        RPGMakerFileKind.ARMORS: DatabaseArrayExtractor(RPGMakerFileKind.ARMORS, "armor"),
        RPGMakerFileKind.STATES: DatabaseArrayExtractor(RPGMakerFileKind.STATES, "state"),
        RPGMakerFileKind.ENEMIES: DatabaseArrayExtractor(RPGMakerFileKind.ENEMIES, "enemy"),
        RPGMakerFileKind.SYSTEM: SystemExtractor(),
        RPGMakerFileKind.MAP_INFOS: MapInfosExtractor(),
        RPGMakerFileKind.MAP: MapExtractor(),
        RPGMakerFileKind.COMMON_EVENTS: CommonEventsExtractor(),
        RPGMakerFileKind.TROOPS: TroopsExtractor(),
    }


class ExtractorRegistry:
    """Dispatch decoded RPG Maker data files to the right extractor."""

    def __init__(self, extractors: dict[RPGMakerFileKind, DataFileExtractor] | None = None) -> None:
        self._extractors = extractors or default_extractors()

    def extract_file(self, project_file: ProjectFile, data: Any) -> tuple[TextSegment, ...]:
        extractor = self._extractors.get(project_file.kind)
        if extractor is None:
            return ()
        return extractor.extract(project_file, data)

    def extract_project(self, project: GameProject) -> ExtractionResult:
        segments: list[TextSegment] = []
        for loaded_file in load_project_data_files(project, include_unknown=False):
            segments.extend(self.extract_file(loaded_file.project_file, loaded_file.data))
        return ExtractionResult(segments=tuple(segments))


def extract_file(project_file: ProjectFile) -> tuple[TextSegment, ...]:
    """Load and extract a single project file."""

    loaded = load_data_file(project_file)
    return ExtractorRegistry().extract_file(loaded.project_file, loaded.data)


def extract_project(project: GameProject) -> ExtractionResult:
    """Load and extract all supported RPG Maker data files in a project."""

    return ExtractorRegistry().extract_project(project)

