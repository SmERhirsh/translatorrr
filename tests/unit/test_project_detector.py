import json
import tempfile
import unittest
from pathlib import Path

from rpg_translator.core.errors import ProjectDetectionError
from rpg_translator.core.models import RPGMakerEngine, RPGMakerFileKind
from rpg_translator.rpgmaker import detect_project


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


class ProjectDetectorTests(unittest.TestCase):
    def test_detects_mv_project_from_project_marker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "Game"
            data = root / "data"
            data.mkdir(parents=True)
            (root / "Game.rpgproject").write_text("RPGMV", encoding="utf-8")
            (root / "js").mkdir()
            (root / "js" / "rpg_core.js").write_text("", encoding="utf-8")
            _write_json(data / "System.json", {"gameTitle": "Test MV"})
            _write_json(data / "MapInfos.json", [None, {"id": 1, "name": "Town"}])
            _write_json(data / "Map001.json", {"displayName": "Town"})

            project = detect_project(data)

        self.assertIs(project.engine, RPGMakerEngine.MV)
        self.assertEqual(project.title, "Test MV")
        self.assertEqual(project.root_path, root)
        self.assertEqual(project.data_path, data)
        self.assertTrue(any(file.kind is RPGMakerFileKind.SYSTEM for file in project.files))
        self.assertTrue(
            any(file.kind is RPGMakerFileKind.MAP and file.map_id == 1 for file in project.files),
        )

    def test_detects_deployed_mz_project_from_runtime_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "DeployedGame"
            data = root / "www" / "data"
            scripts = root / "www" / "js"
            scripts.mkdir(parents=True)
            (scripts / "rmmz_core.js").write_text("", encoding="utf-8")
            _write_json(data / "System.json", {"gameTitle": "Test MZ", "advanced": {}})

            project = detect_project(root / "www")

        self.assertIs(project.engine, RPGMakerEngine.MZ)
        self.assertEqual(project.title, "Test MZ")
        self.assertEqual(project.root_path, root)
        self.assertEqual(project.data_path, data)

    def test_detection_fails_for_non_project_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ProjectDetectionError):
                detect_project(Path(directory))


if __name__ == "__main__":
    unittest.main()
