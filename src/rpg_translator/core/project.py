"""Project-level core helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rpg_translator.core.models import GameProject, RPGMakerEngine


@dataclass(frozen=True, slots=True)
class ProjectSummary:
    """Compact project summary for UI lists and logs."""

    root_path: Path
    engine: RPGMakerEngine
    title: str
    data_file_count: int

    @classmethod
    def from_project(cls, project: GameProject) -> "ProjectSummary":
        return cls(
            root_path=project.root_path,
            engine=project.engine,
            title=project.title,
            data_file_count=len(project.files),
        )

