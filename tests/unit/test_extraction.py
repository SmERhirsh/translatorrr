import unittest
from collections import Counter
from pathlib import Path

from rpg_translator.core.models import RPGMakerFileKind
from rpg_translator.rpgmaker import detect_project, extract_project, load_project_data_files
from rpg_translator.translation import restore_placeholders, validate_control_codes_preserved

FIXTURE_PROJECT = Path(__file__).resolve().parents[1] / "fixtures" / "rpg_project_mv"


class ExtractionTests(unittest.TestCase):
    def test_loads_all_fixture_data_files(self) -> None:
        project = detect_project(FIXTURE_PROJECT)

        loaded = load_project_data_files(project)

        self.assertEqual(len(loaded), 13)
        self.assertEqual({loaded_file.project_file.absolute_path.name for loaded_file in loaded}, {
            "Actors.json",
            "Armors.json",
            "Classes.json",
            "CommonEvents.json",
            "Enemies.json",
            "Items.json",
            "Map001.json",
            "MapInfos.json",
            "Skills.json",
            "States.json",
            "System.json",
            "Troops.json",
            "Weapons.json",
        })

    def test_extracts_all_expected_translatable_segments_from_fixture_project(self) -> None:
        project = detect_project(FIXTURE_PROJECT)

        result = extract_project(project)
        segments = result.segments
        counts = Counter(segment.context.file_kind for segment in segments)

        self.assertEqual(len(segments), 67)
        self.assertEqual(counts[RPGMakerFileKind.ACTORS], 3)
        self.assertEqual(counts[RPGMakerFileKind.CLASSES], 1)
        self.assertEqual(counts[RPGMakerFileKind.ITEMS], 2)
        self.assertEqual(counts[RPGMakerFileKind.SKILLS], 4)
        self.assertEqual(counts[RPGMakerFileKind.WEAPONS], 2)
        self.assertEqual(counts[RPGMakerFileKind.ARMORS], 2)
        self.assertEqual(counts[RPGMakerFileKind.STATES], 5)
        self.assertEqual(counts[RPGMakerFileKind.ENEMIES], 1)
        self.assertEqual(counts[RPGMakerFileKind.SYSTEM], 27)
        self.assertEqual(counts[RPGMakerFileKind.MAP_INFOS], 1)
        self.assertEqual(counts[RPGMakerFileKind.COMMON_EVENTS], 8)
        self.assertEqual(counts[RPGMakerFileKind.TROOPS], 2)
        self.assertEqual(counts[RPGMakerFileKind.MAP], 9)

    def test_segments_have_stable_context_and_json_pointers(self) -> None:
        project = detect_project(FIXTURE_PROJECT)
        segments = extract_project(project).segments
        by_text = {segment.source_text: segment for segment in segments}

        self.assertEqual(by_text["Potion"].context.json_pointer.as_string(), "/1/name")
        self.assertEqual(by_text["Potion"].context.object_type, "item")
        self.assertEqual(
            by_text["Welcome, \\N[1]!"].context.json_pointer.as_string(),
            "/1/list/1/parameters/0",
        )
        self.assertEqual(by_text["Welcome, \\N[1]!"].context.command_code, 401)
        map_yes_choice = next(
            segment
            for segment in segments
            if segment.source_text == "Yes"
            and segment.context.file_kind is RPGMakerFileKind.MAP
            and segment.metadata["role"] == "choice"
        )
        self.assertEqual(
            map_yes_choice.context.json_pointer.as_string(),
            "/events/1/pages/0/list/3/parameters/0/0",
        )
        self.assertEqual(
            by_text["Long ago, heroes saved the world."].context.json_pointer.as_string(),
            "/events/1/pages/0/list/7/parameters/0",
        )
        self.assertEqual(
            by_text["There was no effect on %1!"].context.json_pointer.as_string(),
            "/terms/messages/actionFailure",
        )

    def test_extracted_segments_precompute_protected_tokens(self) -> None:
        project = detect_project(FIXTURE_PROJECT)
        segments = extract_project(project).segments
        segment = next(item for item in segments if item.source_text == "Restores %1 HP to \\N[1].")

        restored = restore_placeholders(segment.metadata["protected_source_text"], segment.protected_tokens)

        self.assertEqual(restored, segment.source_text)
        self.assertEqual(len(segment.protected_tokens), 2)

    def test_control_codes_survive_placeholder_roundtrip_for_every_segment(self) -> None:
        project = detect_project(FIXTURE_PROJECT)
        segments = extract_project(project).segments

        for segment in segments:
            restored = restore_placeholders(
                segment.metadata["protected_source_text"],
                segment.protected_tokens,
            )
            self.assertEqual(restored, segment.source_text)
            self.assertEqual(validate_control_codes_preserved(segment.source_text, restored), ())


if __name__ == "__main__":
    unittest.main()
