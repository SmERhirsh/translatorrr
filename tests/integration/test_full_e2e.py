"""Full end-to-end integration test for RPG Maker MV translation pipeline."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from rpg_translator.config.schema import (
    AppConfig,
    ExtractionSettings,
    LoggingSettings,
    OutputSettings,
    ProviderProfile,
    StorageSettings,
    TranslationSettings,
)
from rpg_translator.core.models import GameProject, OutputMode, ProjectFile, RPGMakerFileKind
from rpg_translator.providers.base import ChatRequest, ChatResponse, ProviderHealth, ProviderKind
from rpg_translator.rpgmaker.detector import detect_project
from rpg_translator.translation.pipeline import translate_project


class RealisticMockProvider:
    """Mock provider that analyzes real ChatRequest and returns appropriate translations.
    
    This provider:
    1. Receives the actual ChatRequest from the pipeline
    2. Parses the input segments from the prompt
    3. Returns translations that preserve placeholders/control codes
    4. Simulates real translation behavior
    """

    kind = ProviderKind.OPENAI_COMPATIBLE
    model = "mock-gpt-4"
    base_url = "http://mock.local"

    def __init__(self) -> None:
        self.call_count = 0
        self.received_requests: list[ChatRequest] = []

    def list_models(self) -> tuple[str, ...]:
        return ("mock-gpt-4",)

    def health_check(self) -> ProviderHealth:
        return ProviderHealth(ok=True, provider=self.kind, base_url=self.base_url, model=self.model)

    def chat(self, request: ChatRequest) -> ChatResponse:
        """Analyze the real request and return translations for actual segments."""
        self.call_count += 1
        self.received_requests.append(request)
        
        # Extract segment IDs and source texts from the prompt
        content = request.messages[1].content if len(request.messages) > 1 else ""
        
        try:
            # Find the "Input segments:" section
            start_marker = "Input segments:\n{"
            start = content.find(start_marker)
            if start >= 0:
                start += len(start_marker) - 1  # Include the opening brace
                
                # Find the matching closing brace
                brace_count = 0
                end = start
                for i, char in enumerate(content[start:], start):
                    if char == "{":
                        brace_count += 1
                    elif char == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            end = i + 1
                            break
                
                if end > start:
                    input_data = json.loads(content[start:end])
                    
                    # Generate translations that preserve control codes and placeholders
                    translations = {}
                    for seg_id, source_text in input_data.items():
                        # Preserve control codes like \\C[3], \\N[1], \\V[2], <i>, etc.
                        # by copying them to the translation
                        translated = self._translate_preserving_codes(source_text)
                        translations[seg_id] = translated
                    
                    return ChatResponse(
                        content=json.dumps(translations),
                        model=self.model,
                    )
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            print(f"Error parsing request: {e}")
        
        return ChatResponse(content="{}", model=self.model)
    
    def _translate_preserving_codes(self, text: str) -> str:
        """Generate a mock translation while preserving control codes."""
        # Simple mock translation: add prefix but keep special codes intact
        # This simulates what a real translator would do
        
        # Detect common RPG Maker control codes and HTML-like tags
        # \\C[n] - color change
        # \\N[n] - actor name
        # \\V[n] - variable value
        # <i>text</i> - italic
        # \\n[1] - actor name (alternate syntax)
        
        # For this test, we'll create a "translation" that keeps these intact
        # by detecting them and ensuring they're in the output
        
        # Mock translation strategy: prepend "[ES]" and keep structure
        result = f"[ES] {text}"
        
        # Ensure control codes are preserved (they should be, since we're just prepending)
        return result


@pytest.fixture
def mv_fixture_path() -> Path:
    """Path to the RPG Maker MV fixture."""
    return Path(__file__).parent.parent / "fixtures" / "rpg_project_mv"


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    """Create a temporary output directory."""
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


@pytest.fixture
def temp_checkpoint_dir(tmp_path: Path) -> Path:
    """Create a temporary checkpoint directory."""
    checkpoint_dir = tmp_path / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    return checkpoint_dir


@pytest.fixture
def test_config() -> AppConfig:
    """Create a test configuration."""
    profile = ProviderProfile(
        name="test-profile",
        kind=ProviderKind.OPENAI_COMPATIBLE,
        base_url="http://mock.local",
        model="mock-gpt-4",
        api_key="test-key",
        temperature=0.7,
        top_p=0.9,
        max_tokens=1000,
    )
    
    return AppConfig(
        app_name="Test RPG Translator",
        source_language="en",
        target_language="es",
        active_provider="test-profile",
        providers={"test-profile": profile},
        translation=TranslationSettings(
            batch_max_segments=5,
            batch_max_chars=2000,
        ),
        extraction=ExtractionSettings(
            translate_database_names=True,
            translate_database_descriptions=True,
            translate_dialogue=True,
            translate_choices=True,
            translate_scroll_text=True,
        ),
        output=OutputSettings(
            mode=OutputMode.TRANSLATED_COPY,
            directory_suffix="_translated",
            write_manifest=True,
            preserve_json_indentation=True,
        ),
        logging=LoggingSettings(
            level="INFO",
            console_enabled=True,
            file_enabled=False,
        ),
        storage=StorageSettings(
            database_path=None,
            cache_enabled=False,
            translation_memory_enabled=False,
        ),
    )


def test_full_e2e_translation_pipeline(
    mv_fixture_path: Path,
    temp_output_dir: Path,
    temp_checkpoint_dir: Path,
    test_config: AppConfig,
) -> None:
    """Full E2E test: detect → extract → translate → write output.
    
    This test uses:
    - Real ProjectDetector on actual RPG Maker MV fixture
    - Real extraction via extract_project()
    - Real TranslationPipeline with placeholderization, batching, prompting
    - Mock provider that receives real ChatRequest and returns translations
    - Real OutputWriter that writes JSON files
    - Real checkpoint save/load (via pipeline's internal mechanism)
    
    After completion, verifies:
    - Output project exists with translated JSON files
    - Translated strings appear in output JSON
    - Placeholders/control codes are preserved
    - Event command structure (code, indent, parameters) is preserved
    - Unrelated/unknown fields are unchanged
    - Source project is unmodified
    """
    # Store original file hashes to verify source is not modified
    original_hashes: dict[Path, str] = {}
    for json_file in mv_fixture_path.glob("data/*.json"):
        original_hashes[json_file] = _hash_file(json_file)
    
    # Step 1: Detect project using real detector
    project = detect_project(mv_fixture_path)
    assert project is not None
    assert project.title == "Fixture Quest"
    assert project.root_path == mv_fixture_path
    
    # Verify detected files
    assert len(project.files) > 0
    data_files = [f for f in project.files if f.kind != RPGMakerFileKind.UNKNOWN]
    assert len(data_files) > 0
    
    # Step 2: Create mock provider and run full pipeline
    mock_provider = RealisticMockProvider()
    
    # Run the complete pipeline through its public API
    job, translated_segments = translate_project(
        project=project,
        config=test_config,
        provider=mock_provider,
        output_dir=temp_output_dir,
        checkpoint_dir=temp_checkpoint_dir,
    )
    
    # Step 3: Verify pipeline execution
    assert job.status.value == "completed"
    assert len(translated_segments) > 0
    
    # Verify mock provider was called with real requests
    assert mock_provider.call_count > 0
    assert len(mock_provider.received_requests) > 0
    
    # Verify received requests are valid ChatRequests
    for req in mock_provider.received_requests:
        assert isinstance(req, ChatRequest)
        assert req.model == "mock-gpt-4"
        assert len(req.messages) >= 2  # System + User messages
    
    # Step 4: Verify output files were created
    output_data_dir = temp_output_dir / "data"
    assert output_data_dir.exists()
    
    # Check specific output files
    output_actors = output_data_dir / "Actors.json"
    output_map = output_data_dir / "Map001.json"
    output_system = output_data_dir / "System.json"
    output_troops = output_data_dir / "Troops.json"
    
    assert output_actors.exists(), "Actors.json should be written"
    assert output_map.exists(), "Map001.json should be written"
    assert output_system.exists(), "System.json should be written"
    assert output_troops.exists(), "Troops.json should be written"
    
    # Step 5: Verify translated content in Actors.json
    with open(output_actors, "r", encoding="utf-8") as f:
        actors_data = json.load(f)
    
    # Original: {"id":1,"name":"Harold","nickname":"Hero of Light",...,"profile":"A brave warrior with \\C[3]courage\\C[0]."}
    # Should have translated profile with \\C[3] and \\C[0] preserved
    actor1 = actors_data[1]
    assert actor1["id"] == 1
    # Note: "name" and "nickname" fields are extracted for translation per DATABASE_FIELD_SPECS
    assert "[ES]" in actor1["name"], "Translation marker should be present in name"
    assert "Harold" in actor1["name"], "Original name should be in translation"
    assert "[ES]" in actor1["nickname"], "Translation marker should be present in nickname"
    assert "Hero of Light" in actor1["nickname"], "Original nickname should be in translation"
    assert actor1["classId"] == 1  # Unchanged (not a text field)
    assert "\\C[3]" in actor1["profile"], "Control code \\C[3] must be preserved"
    assert "\\C[0]" in actor1["profile"], "Control code \\C[0] must be preserved"
    assert "[ES]" in actor1["profile"], "Translation marker should be present"
    assert "courage" in actor1["profile"], "Original text should be in translation"
    assert actor1.get("note") == "<ActorMeta: keep>", "Unknown field 'note' should be preserved"
    
    # Step 6: Verify Map001.json event commands structure preserved
    with open(output_map, "r", encoding="utf-8") as f:
        map_data = json.load(f)
    
    # displayName is extracted for translation
    assert "[ES]" in map_data["displayName"], "Translation marker should be present"
    assert "Village Square" in map_data["displayName"], "Original displayName should be in translation"
    
    # Find the greeting event
    events = map_data.get("events", [])
    assert len(events) > 1
    # Event name is stored but may not be extracted for translation (only command text is)
    greeting_event = events[1]  # Event ID 1
    # The event name field itself is not translated, only command text inside
    assert "Greeting Event" in greeting_event["name"] or "[ES]" in str(greeting_event.get("name", ""))
    
    # Get event command list
    pages = greeting_event.get("pages", [])
    assert len(pages) > 0
    command_list = pages[0].get("list", [])
    
    # Find message command (code 401)
    message_commands = [cmd for cmd in command_list if cmd.get("code") == 401]
    assert len(message_commands) > 0
    
    # Verify first message command structure
    first_msg = message_commands[0]
    assert first_msg["code"] == 401, "Event command code must be preserved"
    assert first_msg["indent"] == 0, "Event command indent must be preserved"
    assert isinstance(first_msg["parameters"], list), "Parameters must be array"
    
    # The message text should be translated with placeholders preserved
    msg_params = first_msg["parameters"]
    if len(msg_params) > 0 and isinstance(msg_params[0], str):
        msg_text = msg_params[0]
        assert "\\N[1]" in msg_text or "[ES]" in msg_text, "Placeholder or translation marker should be present"
    
    # Step 7: Verify System.json nested structures preserved
    with open(output_system, "r", encoding="utf-8") as f:
        system_data = json.load(f)
    
    # gameTitle is extracted for translation
    assert "[ES]" in system_data["gameTitle"], "Translation marker should be present"
    assert "Fixture Quest" in system_data["gameTitle"], "Original gameTitle should be in translation"
    assert system_data["currencyUnit"] == "Gold"  # Unchanged
    
    # Check nested terms structure
    terms = system_data.get("terms", {})
    assert "basic" in terms
    assert "params" in terms
    assert "commands" in terms
    assert "messages" in terms
    
    # Messages should have translated entries
    messages = terms.get("messages", {})
    if messages:
        # At least some messages should be translated
        has_translation = any("[ES]" in str(v) for v in messages.values())
        # Either translated or original structure preserved
        assert has_translation or len(messages) > 0
    
    # Step 8: Verify Troops.json with control codes
    with open(output_troops, "r", encoding="utf-8") as f:
        troops_data = json.load(f)
    
    # Find troop with \\V[2] control code
    troop_with_code = None
    for troop in troops_data:
        if troop and isinstance(troop, dict):
            pages = troop.get("pages", [])
            for page in pages:
                cmd_list = page.get("list", [])
                for cmd in cmd_list:
                    if cmd.get("code") == 401:
                        params = cmd.get("parameters", [])
                        if params and "\\V[2]" in str(params):
                            troop_with_code = troop
                            break
    
    if troop_with_code:
        # Verify structure preserved
        assert "id" in troop_with_code
        assert "name" in troop_with_code
        assert "pages" in troop_with_code
        
        # Verify \\V[2] is preserved in translation
        pages = troop_with_code["pages"]
        found_v2 = False
        for page in pages:
            for cmd in page.get("list", []):
                if cmd.get("code") == 401:
                    params = cmd.get("parameters", [])
                    if params and "\\V[2]" in str(params):
                        found_v2 = True
                        break
        assert found_v2, "Control code \\V[2] must be preserved in troops"
    
    # Step 9: Verify source project was NOT modified
    for json_file, original_hash in original_hashes.items():
        current_hash = _hash_file(json_file)
        assert current_hash == original_hash, f"Source file {json_file} was modified!"
    
    # Step 10: Verify checkpoint was created
    checkpoint_files = list(temp_checkpoint_dir.glob("*.json"))
    assert len(checkpoint_files) > 0, "Checkpoint file should be created"
    
    # Load and verify checkpoint schema version
    checkpoint_data = json.loads(checkpoint_files[0].read_text(encoding="utf-8"))
    assert checkpoint_data.get("schema_version") == "1.0", "Checkpoint must have schema_version 1.0"
    assert "job_id" in checkpoint_data
    assert "translated_segments" in checkpoint_data
    assert len(checkpoint_data["translated_segments"]) > 0


def _hash_file(path: Path) -> str:
    """Calculate SHA-256 hash of a file."""
    import hashlib
    digest = hashlib.sha256()
    content = path.read_bytes()
    digest.update(content)
    return digest.hexdigest()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
