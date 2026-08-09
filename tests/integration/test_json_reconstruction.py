"""Regression tests for JSON reconstruction after translation output."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from rpg_translator.config.schema import (
    AppConfig,
    OutputMode,
    OutputSettings,
    TranslationSettings,
    ExtractionSettings,
    LoggingSettings,
    StorageSettings,
)
from rpg_translator.core.models import (
    GameProject,
    JobStatus,
    JsonPointer,
    ProviderKind,
    ProjectFile,
    RPGMakerFileKind,
    SegmentContext,
    SegmentStatus,
    TextSegment,
    TranslationJob,
)
from rpg_translator.output.writer import write_translated_project
from rpg_translator.rpgmaker.detector import detect_project


FIXTURE_PATH = Path("/workspace/tests/fixtures/rpg_project_mv")


def _create_basic_config() -> AppConfig:
    """Create a basic config for testing."""
    from rpg_translator.config.schema import ProviderProfile
    
    profile = ProviderProfile(
        name="test",
        kind=ProviderKind.OPENAI_COMPATIBLE,
        base_url="http://test.local",
        model="test-model",
    )
    
    return AppConfig(
        app_name="TestApp",
        source_language="en",
        target_language="ru",
        active_provider="test",
        providers={"test": profile},
        translation=TranslationSettings(batch_max_segments=10, batch_max_chars=1000),
        extraction=ExtractionSettings(),
        output=OutputSettings(mode=OutputMode.TRANSLATED_COPY, write_manifest=False),
        logging=LoggingSettings(),
        storage=StorageSettings(),
    )


def _create_segment(
    segment_id: str,
    source_text: str,
    translation: str,
    source_file: Path,
    json_pointer: JsonPointer,
    file_kind: RPGMakerFileKind,
) -> TextSegment:
    """Helper to create a translated TextSegment."""
    return TextSegment(
        segment_id=segment_id,
        source_text=source_text,
        translation=translation,
        status=SegmentStatus.TRANSLATED,
        source_file=source_file,
        context=SegmentContext(file_kind=file_kind, json_pointer=json_pointer),
    )


def test_json_reconstruction_actors_profile(tmp_path: Path) -> None:
    """Test JSON reconstruction preserves all fields except translated value in Actors.json.
    
    This test verifies:
    - Translated value changes
    - Untranslated values preserved (id, name, nickname, classId, etc.)
    - Unknown fields preserved (note field with custom metadata)
    - Nested structures preserved
    """
    # Use existing RPG Maker MV fixture
    project = detect_project(FIXTURE_PATH)
    
    # Find Actors.json
    actors_file = project.root_path / "data" / "Actors.json"
    assert actors_file.exists(), f"Actors.json not found at {actors_file}"
    
    # Load original data
    original_data = json.loads(actors_file.read_text(encoding="utf-8"))
    
    # Create translated segment for actor profile
    # Original: "A brave warrior with \\C[3]courage\\C[0]."
    # We'll translate it to Russian
    translated_profile = "Храбрый воин с \\\\C[3]мужеством\\\\C[0]."
    
    # The profile is at index 1 (first element is null), key "profile"
    pointer = JsonPointer(parts=[1, "profile"])
    
    segment = _create_segment(
        segment_id="actor_1_profile",
        source_text="A brave warrior with \\C[3]courage\\C[0].",
        translation=translated_profile,
        source_file=actors_file,
        json_pointer=pointer,
        file_kind=RPGMakerFileKind.ACTORS,
    )
    
    # Write translated output
    output_dir = tmp_path / "output"
    config = _create_basic_config()
    
    manifest_entries = write_translated_project(
        project=project,
        translated_segments=(segment,),
        output_dir=output_dir,
        config=config,
    )
    
    # Verify manifest entry was created
    assert len(manifest_entries) == 1
    
    # Read the output file
    output_file = output_dir / "data" / "Actors.json"
    assert output_file.exists(), f"Output file not created at {output_file}"
    
    output_data = json.loads(output_file.read_text(encoding="utf-8"))
    
    # Verify translated value changed
    assert output_data[1]["profile"] == translated_profile, \
        f"Expected translated profile '{translated_profile}', got '{output_data[1]['profile']}'"
    
    # Verify untranslated values preserved
    assert output_data[1]["id"] == 1, "Actor id should be preserved"
    assert output_data[1]["name"] == "Harold", "Actor name should be preserved"
    assert output_data[1]["nickname"] == "Hero of Light", "Actor nickname should be preserved"
    assert output_data[1]["classId"] == 1, "Actor classId should be preserved"
    assert output_data[1]["initialLevel"] == 1, "Actor initialLevel should be preserved"
    assert output_data[1]["maxLevel"] == 99, "Actor maxLevel should be preserved"
    
    # Verify unknown/custom fields preserved (note field)
    assert output_data[1]["note"] == "<ActorMeta: keep>", \
        f"Custom note field should be preserved, got '{output_data[1]['note']}'"


def test_json_reconstruction_map_event_commands(tmp_path: Path) -> None:
    """Test JSON reconstruction preserves event command structure except translated text.
    
    This test verifies:
    - Event command code preserved
    - Event command indent preserved
    - Event command parameters preserved (except translated string)
    - Array structure preserved
    - Nested structures preserved
    """
    project = detect_project(FIXTURE_PATH)
    
    # Find Map001.json
    map_file = project.root_path / "data" / "Map001.json"
    assert map_file.exists(), f"Map001.json not found at {map_file}"
    
    # Load original data
    original_data = json.loads(map_file.read_text(encoding="utf-8"))
    
    # Original event has commands like:
    # {"code":401,"indent":0,"parameters":["Hello there, \\N[1]."]}
    # Translate the first message
    original_text = "Hello there, \\N[1]."
    translated_text = "Привет, \\N[1]."
    
    # Pointer to first event (index 1), first page (index 0), command list [1], parameters [0]
    # Root data dict -> events[1]['pages'][0]['list'][1]['parameters'][0]
    # So pointer parts: ['events', 1, 'pages', 0, 'list', 1, 'parameters', 0]
    pointer = JsonPointer(parts=['events', 1, 'pages', 0, 'list', 1, 'parameters', 0])
    
    segment = _create_segment(
        segment_id="map001_event_msg1",
        source_text=original_text,
        translation=translated_text,
        source_file=map_file,
        json_pointer=pointer,
        file_kind=RPGMakerFileKind.MAP,
    )
    
    output_dir = tmp_path / "output_map"
    config = _create_basic_config()
    
    manifest_entries = write_translated_project(
        project=project,
        translated_segments=(segment,),
        output_dir=output_dir,
        config=config,
    )
    
    assert len(manifest_entries) == 1
    
    output_file = output_dir / "data" / "Map001.json"
    assert output_file.exists()
    
    output_data = json.loads(output_file.read_text(encoding="utf-8"))
    
    # Get the event command
    event_command = output_data["events"][1]["pages"][0]["list"][1]
    
    # Verify translated value changed
    assert event_command["parameters"][0] == translated_text, \
        f"Expected translated text '{translated_text}', got '{event_command['parameters'][0]}'"
    
    # Verify command structure preserved
    assert event_command["code"] == 401, "Event command code should be preserved"
    assert event_command["indent"] == 0, "Event command indent should be preserved"
    
    # Verify parameters array structure preserved (should still have 1 element)
    assert isinstance(event_command["parameters"], list), "Parameters should remain an array"
    assert len(event_command["parameters"]) == 1, "Parameters array length should be preserved"
    
    # Verify surrounding event structure preserved
    event = output_data["events"][1]
    assert event["id"] == 1, "Event id should be preserved"
    assert event["name"] == "Greeting Event", "Event name should be preserved"
    assert event["x"] == 5, "Event x position should be preserved"
    assert event["y"] == 6, "Event y position should be preserved"
    
    # Verify map metadata preserved
    assert output_data["displayName"] == "Village Square", "Map displayName should be preserved"
    assert output_data["width"] == 17, "Map width should be preserved"
    assert output_data["height"] == 13, "Map height should be preserved"


def test_json_reconstruction_system_terms_nested(tmp_path: Path) -> None:
    """Test JSON reconstruction preserves deeply nested structures in System.json.
    
    This test verifies:
    - Deeply nested objects preserved
    - Arrays preserved
    - Multiple translations in same file work correctly
    - Untranslated nested values preserved
    """
    project = detect_project(FIXTURE_PATH)
    
    system_file = project.root_path / "data" / "System.json"
    assert system_file.exists(), f"System.json not found at {system_file}"
    
    original_data = json.loads(system_file.read_text(encoding="utf-8"))
    
    # Translate a term from messages.actionFailure
    # Original: "There was no effect on %1!"
    original_text = "There was no effect on %1!"
    translated_text = "Не было эффекта на %1!"
    
    # Pointer: terms.messages.actionFailure (index 0 in the messages object's values)
    # Actually need to navigate: terms -> messages -> actionFailure
    # In JSON pointer: /terms/messages/actionFailure
    # But our JsonPointer uses integer indices for arrays and string keys for objects
    # Let's check the actual structure first
    # terms is an object with keys: basic, params, commands, messages
    # messages is an object with keys: actionFailure, actorDamage, actorRecovery
    
    # The pointer should be: ["terms", "messages", "actionFailure"]
    pointer = JsonPointer(parts=["terms", "messages", "actionFailure"])
    
    segment = _create_segment(
        segment_id="system_term_action_failure",
        source_text=original_text,
        translation=translated_text,
        source_file=system_file,
        json_pointer=pointer,
        file_kind=RPGMakerFileKind.SYSTEM,
    )
    
    output_dir = tmp_path / "output_system"
    config = _create_basic_config()
    
    manifest_entries = write_translated_project(
        project=project,
        translated_segments=(segment,),
        output_dir=output_dir,
        config=config,
    )
    
    assert len(manifest_entries) == 1
    
    output_file = output_dir / "data" / "System.json"
    assert output_file.exists()
    
    output_data = json.loads(output_file.read_text(encoding="utf-8"))
    
    # Verify translated value changed
    assert output_data["terms"]["messages"]["actionFailure"] == translated_text, \
        f"Expected translated text '{translated_text}', got '{output_data['terms']['messages']['actionFailure']}'"
    
    # Verify other message terms preserved
    assert output_data["terms"]["messages"]["actorDamage"] == "%1 took %2 damage!", \
        "Other message terms should be preserved"
    assert output_data["terms"]["messages"]["actorRecovery"] == "%1 recovered %2 %3!", \
        "Other message terms should be preserved"
    
    # Verify terms.basic array preserved
    assert output_data["terms"]["basic"] == ["Level", "Lv", "HP", "MP"], \
        "Terms basic array should be preserved"
    
    # Verify terms.params array preserved
    assert output_data["terms"]["params"] == ["Max HP", "Max MP", "Attack"], \
        "Terms params array should be preserved"
    
    # Verify top-level fields preserved
    assert output_data["gameTitle"] == "Fixture Quest", "Game title should be preserved"
    assert output_data["currencyUnit"] == "Gold", "Currency unit should be preserved"
    
    # Verify elements array preserved
    assert output_data["elements"] == ["", "Physical", "Fire"], \
        "Elements array should be preserved"
    
    # Verify skillTypes array preserved
    assert output_data["skillTypes"] == ["", "Magic"], \
        "Skill types array should be preserved"


def test_json_reconstruction_troops_with_control_codes(tmp_path: Path) -> None:
    """Test JSON reconstruction preserves control codes and special characters.
    
    This test verifies:
    - Control codes (\\V, \\N, etc.) preserved in untranslated parts
    - Special characters preserved
    - Array structure with null elements preserved
    """
    project = detect_project(FIXTURE_PATH)
    
    troops_file = project.root_path / "data" / "Troops.json"
    assert troops_file.exists(), f"Troops.json not found at {troops_file}"
    
    original_data = json.loads(troops_file.read_text(encoding="utf-8"))
    
    # Original: "Gloop \\V[2]!"
    original_text = "Gloop \\V[2]!"
    translated_text = "Хлюп \\V[2]!"
    
    # Pointer: [1, "pages", 0, "list", 1, "parameters", 0]
    # Root data is array: [null, troop1]
    # So pointer parts: [1, 'pages', 0, 'list', 1, 'parameters', 0]
    pointer = JsonPointer(parts=[1, 'pages', 0, 'list', 1, 'parameters', 0])
    
    segment = _create_segment(
        segment_id="troops_msg_slime",
        source_text=original_text,
        translation=translated_text,
        source_file=troops_file,
        json_pointer=pointer,
        file_kind=RPGMakerFileKind.TROOPS,
    )
    
    output_dir = tmp_path / "output_troops"
    config = _create_basic_config()
    
    manifest_entries = write_translated_project(
        project=project,
        translated_segments=(segment,),
        output_dir=output_dir,
        config=config,
    )
    
    assert len(manifest_entries) == 1
    
    output_file = output_dir / "data" / "Troops.json"
    assert output_file.exists()
    
    output_data = json.loads(output_file.read_text(encoding="utf-8"))
    
    # Verify translated value changed
    troop_command = output_data[1]["pages"][0]["list"][1]
    assert troop_command["parameters"][0] == translated_text, \
        f"Expected translated text '{translated_text}', got '{troop_command['parameters'][0]}'"
    
    # Verify command structure preserved
    assert troop_command["code"] == 401, "Command code should be preserved"
    assert troop_command["indent"] == 0, "Command indent should be preserved"
    
    # Verify first command (Show Face/Name) preserved with control codes
    first_command = output_data[1]["pages"][0]["list"][0]
    assert first_command["code"] == 101, "First command code should be preserved"
    # The parameters should still contain the original control codes
    assert first_command["parameters"][0] == "", "First command param 0 should be preserved"
    assert first_command["parameters"][3] == 2, "First command param 3 should be preserved"
    
    # Verify array structure with null element preserved
    assert output_data[0] is None, "Null element at index 0 should be preserved"
    assert len(output_data) == 2, "Array length should be preserved"
    
    # Verify troop metadata preserved
    assert output_data[1]["id"] == 1, "Troop id should be preserved"
    assert output_data[1]["name"] == "Slime*2", "Troop name should be preserved"
    assert output_data[1]["members"] == [], "Troop members array should be preserved"
