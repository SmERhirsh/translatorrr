"""JSON loading helpers for RPG Maker data files."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from rpg_translator.core.errors import JsonReadError
from rpg_translator.core.models import GameProject, ProjectFile, RPGMakerFileKind


@dataclass(frozen=True, slots=True)
class LoadedDataFile:
    """Decoded JSON content paired with project-file metadata."""

    project_file: ProjectFile
    data: Any

    @property
    def kind(self) -> RPGMakerFileKind:
        return self.project_file.kind


def load_json_file(path: Path) -> Any:
    """Load a JSON file using UTF-8 with BOM tolerance."""

    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise JsonReadError(
            f"Could not read JSON file: {path}",
            details={"path": str(path), "error": str(exc)},
        ) from exc

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise JsonReadError(
            f"Could not parse JSON file: {path}",
            details={
                "path": str(path),
                "line": exc.lineno,
                "column": exc.colno,
                "error": exc.msg,
            },
        ) from exc


def load_data_file(project_file: ProjectFile) -> LoadedDataFile:
    """Load a detected RPG Maker data file."""

    return LoadedDataFile(project_file=project_file, data=load_json_file(project_file.absolute_path))


def load_project_data_files(
    project: GameProject,
    *,
    include_unknown: bool = True,
) -> tuple[LoadedDataFile, ...]:
    """Load all JSON data files detected for a project."""

    loaded: list[LoadedDataFile] = []
    for project_file in project.files:
        if not include_unknown and project_file.kind is RPGMakerFileKind.UNKNOWN:
            continue
        loaded.append(load_data_file(project_file))
    return tuple(loaded)
