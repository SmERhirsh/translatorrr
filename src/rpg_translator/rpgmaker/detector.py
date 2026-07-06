"""RPG Maker MV/MZ project detection."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from rpg_translator.core.errors import ProjectDetectionError
from rpg_translator.core.models import (
    FileFingerprint,
    GameProject,
    ProjectFile,
    RPGMakerEngine,
)
from rpg_translator.logging import get_logger
from rpg_translator.rpgmaker.file_registry import DataFileRegistry
from rpg_translator.rpgmaker.json_loader import load_json_file

logger = get_logger(__name__)


class ProjectDetector:
    """Detect RPG Maker MV/MZ projects from source or deployed game folders."""

    def detect(self, path: str | Path) -> GameProject:
        """Detect a project from a root, child directory, or data directory."""

        start = Path(path).expanduser()
        if not start.exists():
            raise ProjectDetectionError(
                f"Project path does not exist: {start}",
                details={"path": str(start)},
            )

        for root_path, data_path in self._candidate_roots(start.resolve()):
            try:
                project = self._detect_at(root_path, data_path)
            except ProjectDetectionError as exc:
                logger.debug(
                    "Rejected RPG Maker project candidate",
                    extra={
                        "candidate_root": str(root_path),
                        "candidate_data": str(data_path),
                        "reason": exc.message,
                    },
                )
                continue
            logger.info(
                "Detected RPG Maker project",
                extra={
                    "root_path": str(project.root_path),
                    "data_path": str(project.data_path),
                    "engine": project.engine.value,
                    "title": project.title,
                    "file_count": len(project.files),
                },
            )
            return project

        raise ProjectDetectionError(
            f"Could not detect an RPG Maker MV/MZ project at or above: {start}",
            details={"path": str(start)},
        )

    def _candidate_roots(self, start: Path) -> Iterable[tuple[Path, Path]]:
        base = start.parent if start.is_file() else start
        candidates: list[tuple[Path, Path]] = []

        for current in (base, *base.parents):
            if current.name.lower() == "data" and (current / "System.json").is_file():
                candidates.append((current.parent, current))
            if current.name.lower() == "www" and (current / "data" / "System.json").is_file():
                candidates.append((current.parent, current / "data"))
            if (current / "data" / "System.json").is_file():
                candidates.append((current, current / "data"))
            if (current / "www" / "data" / "System.json").is_file():
                candidates.append((current, current / "www" / "data"))

        seen: set[tuple[Path, Path]] = set()
        for root_path, data_path in candidates:
            key = (root_path.resolve(), data_path.resolve())
            if key not in seen:
                seen.add(key)
                yield key

    def _detect_at(self, root_path: Path, data_path: Path) -> GameProject:
        if not data_path.is_dir():
            raise ProjectDetectionError(
                "RPG Maker data directory is missing",
                details={"data_path": str(data_path)},
            )

        self._validate_required_files(data_path)
        system = load_json_file(data_path / "System.json")
        if not isinstance(system, dict):
            raise ProjectDetectionError(
                "System.json must contain a JSON object",
                details={"path": str(data_path / "System.json")},
            )

        engine = self._detect_engine(root_path, data_path, system)
        title = self._read_title(system, root_path)
        project_file = self._find_project_file(root_path, data_path)
        executable_path = self._find_executable(root_path)
        files = self._scan_data_files(root_path, data_path)

        return GameProject(
            root_path=root_path,
            data_path=data_path,
            engine=engine,
            title=title,
            files=files,
            project_file=project_file,
            executable_path=executable_path,
        )

    def _validate_required_files(self, data_path: Path) -> None:
        missing = [
            filename
            for filename in DataFileRegistry.required_filenames()
            if not (data_path / filename).is_file()
        ]
        if missing:
            raise ProjectDetectionError(
                "RPG Maker data directory is missing required files",
                details={"data_path": str(data_path), "missing": missing},
            )

    def _detect_engine(
        self,
        root_path: Path,
        data_path: Path,
        system: dict[str, Any],
    ) -> RPGMakerEngine:
        marker_engine = self._detect_engine_from_project_marker(root_path, data_path)
        if marker_engine:
            return marker_engine

        script_engine = self._detect_engine_from_scripts(root_path, data_path)
        if script_engine:
            return script_engine

        if any(key in system for key in ("advanced", "touchUI", "optAutosave")):
            return RPGMakerEngine.MZ

        return RPGMakerEngine.MV

    def _detect_engine_from_project_marker(
        self,
        root_path: Path,
        data_path: Path,
    ) -> RPGMakerEngine | None:
        marker_candidates = [
            root_path / "Game.rpgproject",
            data_path.parent / "Game.rpgproject",
        ]
        for marker_path in marker_candidates:
            if not marker_path.is_file():
                continue
            try:
                marker = marker_path.read_text(encoding="utf-8", errors="ignore").strip().upper()
            except OSError:
                continue
            if "RPGMZ" in marker:
                return RPGMakerEngine.MZ
            if "RPGMV" in marker:
                return RPGMakerEngine.MV
        return None

    def _detect_engine_from_scripts(
        self,
        root_path: Path,
        data_path: Path,
    ) -> RPGMakerEngine | None:
        script_dirs = [
            root_path / "js",
            root_path / "www" / "js",
            data_path.parent / "js",
        ]
        for script_dir in script_dirs:
            if not script_dir.is_dir():
                continue
            if (script_dir / "rmmz_core.js").is_file() or (script_dir / "rmmz_managers.js").is_file():
                return RPGMakerEngine.MZ
            if (script_dir / "rpg_core.js").is_file() or (script_dir / "rpg_managers.js").is_file():
                return RPGMakerEngine.MV
        return None

    def _read_title(self, system: dict[str, Any], root_path: Path) -> str:
        title = system.get("gameTitle")
        if isinstance(title, str) and title.strip():
            return title.strip()
        return root_path.name

    def _find_project_file(self, root_path: Path, data_path: Path) -> Path | None:
        candidates = [
            root_path / "Game.rpgproject",
            data_path.parent / "Game.rpgproject",
        ]
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        return None

    def _find_executable(self, root_path: Path) -> Path | None:
        candidates = [
            root_path / "Game.exe",
            root_path / f"{root_path.name}.exe",
        ]
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        return None

    def _scan_data_files(self, root_path: Path, data_path: Path) -> tuple[ProjectFile, ...]:
        json_files = sorted(data_path.glob("*.json"), key=DataFileRegistry.sort_key)
        project_files: list[ProjectFile] = []
        for absolute_path in json_files:
            kind, map_id = DataFileRegistry.classify(absolute_path)
            project_files.append(
                ProjectFile(
                    absolute_path=absolute_path,
                    relative_path=absolute_path.relative_to(root_path),
                    kind=kind,
                    fingerprint=FileFingerprint.from_path(absolute_path),
                    map_id=map_id,
                ),
            )
        return tuple(project_files)


def detect_project(path: str | Path) -> GameProject:
    """Convenience wrapper around :class:`ProjectDetector`."""

    return ProjectDetector().detect(path)

