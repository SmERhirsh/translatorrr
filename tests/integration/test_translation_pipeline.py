"""Integration tests for the translation pipeline."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest import mock

from rpg_translator.config.schema import AppConfig, ProviderProfile, TranslationSettings
from rpg_translator.core.models import (
    JsonPointer,
    ProviderKind,
    RPGMakerFileKind,
    SegmentContext,
    TextSegment,
)
from rpg_translator.providers.base import ChatRequest, ChatResponse, ProviderHealth
from rpg_translator.translation.batching import create_batches
from rpg_translator.translation.placeholderizer import protect_text, restore_placeholders
from rpg_translator.translation.prompt_builder import build_translation_prompt, parse_translation_response


class MockChatProvider:
    """Mock provider that returns predefined translations."""

    kind = ProviderKind.OPENAI_COMPATIBLE
    model = "test-model"
    base_url = "http://test.local"

    def __init__(self, translations: dict[str, str] | None = None) -> None:
        self._translations = translations or {}
        self.call_count = 0

    def list_models(self) -> tuple[str, ...]:
        return ("test-model",)

    def health_check(self) -> ProviderHealth:
        return ProviderHealth(ok=True, provider=self.kind, base_url=self.base_url, model=self.model)

    def chat(self, request: ChatRequest) -> ChatResponse:
        self.call_count += 1
        # Extract segment IDs from the prompt by finding the Input segments JSON block
        content = request.messages[1].content if len(request.messages) > 1 else ""
        try:
            # Find the "Input segments:" section and parse the JSON that follows
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
                    # Return translations for each segment
                    translations = {}
                    for seg_id in input_data.keys():
                        translations[seg_id] = self._translations.get(seg_id, f"Translated: {seg_id}")
                    return ChatResponse(
                        content=json.dumps(translations),
                        model=self.model,
                    )
        except (json.JSONDecodeError, KeyError, IndexError):
            pass
        return ChatResponse(content="{}", model=self.model)


def test_batching_basic() -> None:
    """Batching splits segments correctly."""
    segments = tuple(
        TextSegment(
            segment_id=f"seg_{i}",
            source_text=f"Text {i}",
            source_file=Path("/test.json"),
            context=SegmentContext(file_kind=RPGMakerFileKind.SYSTEM, json_pointer=JsonPointer.root()),
        )
        for i in range(5)
    )
    batches = create_batches(segments, max_segments=2)
    assert len(batches) == 3
    assert len(batches[0].segments) == 2
    assert len(batches[1].segments) == 2
    assert len(batches[2].segments) == 1


def test_placeholder_protection_roundtrip() -> None:
    """Placeholders are protected and restored correctly."""
    original = "\\C[1]Hello <b>World</b>"
    protected = protect_text(original)
    assert protected.protected_text != original
    assert "\\C[1]" not in protected.protected_text
    assert "<b>" not in protected.protected_text
    
    restored = restore_placeholders(protected.protected_text, protected.tokens)
    assert restored == original


def test_prompt_builder_creates_valid_request() -> None:
    """Prompt builder creates valid ChatRequest."""
    segments = (
        TextSegment(
            segment_id="seg_1",
            source_text="Hello",
            source_file=Path("/test.json"),
            context=SegmentContext(file_kind=RPGMakerFileKind.SYSTEM, json_pointer=JsonPointer.root()),
        ),
    )
    prompt = build_translation_prompt(segments, "en", "ru")
    request = prompt.to_chat_request(model="test")
    
    assert len(request.messages) == 2
    assert request.messages[0].role == "system"
    assert request.messages[1].role == "user"
    assert "Hello" in request.messages[1].content


def test_response_parser_valid() -> None:
    """Response parser handles valid responses."""
    response = json.dumps({"seg_1": "Translation 1", "seg_2": "Translation 2"})
    result = parse_translation_response(response, ("seg_1", "seg_2"))
    assert result == {"seg_1": "Translation 1", "seg_2": "Translation 2"}


def test_response_parser_missing_segment() -> None:
    """Response parser detects missing segments."""
    response = json.dumps({"seg_1": "Translation 1"})
    try:
        parse_translation_response(response, ("seg_1", "seg_2"))
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Missing" in str(e)


def test_mock_provider_integration() -> None:
    """Mock provider integrates correctly with prompt/response flow."""
    provider = MockChatProvider({"seg_1": "Привет", "seg_2": "Мир"})
    
    segments = tuple(
        TextSegment(
            segment_id=f"seg_{i}",
            source_text=f"Text {i}",
            source_file=Path("/test.json"),
            context=SegmentContext(file_kind=RPGMakerFileKind.SYSTEM, json_pointer=JsonPointer.root()),
        )
        for i in range(1, 3)
    )
    
    prompt = build_translation_prompt(segments, "en", "ru")
    request = prompt.to_chat_request(model="test")
    response = provider.chat(request)
    
    translations = parse_translation_response(response.content, ("seg_1", "seg_2"))
    assert translations["seg_1"] == "Привет"
    assert translations["seg_2"] == "Мир"


def test_checkpoint_save_load() -> None:
    """Checkpoint can be saved and loaded."""
    from rpg_translator.translation.pipeline import CheckpointState
    from rpg_translator.core.models import JobStatus, TranslationJob
    
    job = TranslationJob(
        job_id="test_job",
        project_root=Path("/test"),
        source_language="en",
        target_language="ru",
        status=JobStatus.RUNNING,
    )
    
    checkpoint = CheckpointState.from_job(
        job,
        translated={"seg_1": "Translation"},
        completed_ids={"seg_1"},
    )
    
    data = checkpoint.to_dict()
    loaded = CheckpointState.from_dict(data)
    
    assert loaded.job_id == "test_job"
    assert loaded.translated_segments == {"seg_1": "Translation"}
    assert "seg_1" in loaded.completed_segment_ids


def test_checkpoint_resume_scenario(tmp_path: Path) -> None:
    """Checkpoint resume scenario: batch 1/2 succeed, batch 3 fails, then resume skips 1/2."""
    import tempfile
    from rpg_translator.config.schema import (
        AppConfig,
        ProviderProfile,
        TranslationSettings,
        ExtractionSettings,
        OutputSettings,
        LoggingSettings,
        StorageSettings,
    )
    from rpg_translator.core.models import ProviderKind, JobStatus, TranslationJob
    from rpg_translator.translation.pipeline import TranslationPipeline, CheckpointState
    from rpg_translator.providers.base import ChatRequest, ChatResponse, ProviderHealth
    
    class FailingMockProvider:
        """Mock provider that fails on the third call."""
        kind = ProviderKind.OPENAI_COMPATIBLE
        model = "test-model"
        base_url = "http://test.local"
        
        def __init__(self) -> None:
            self.call_count = 0
            self.call_history: list[tuple[str, ...]] = []
        
        def list_models(self) -> tuple[str, ...]:
            return ("test-model",)
        
        def health_check(self) -> ProviderHealth:
            return ProviderHealth(ok=True, provider=self.kind, base_url=self.base_url, model=self.model)
        
        def chat(self, request: ChatRequest) -> ChatResponse:
            self.call_count += 1
            # Extract segment IDs
            content = request.messages[1].content if len(request.messages) > 1 else ""
            start_marker = "Input segments:\n{"
            start = content.find(start_marker)
            seg_ids = []
            if start >= 0:
                start += len(start_marker) - 1
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
                    try:
                        input_data = json.loads(content[start:end])
                        seg_ids = list(input_data.keys())
                    except (json.JSONDecodeError, KeyError):
                        pass
            
            self.call_history.append(tuple(seg_ids))
            
            # Fail on third call (batch 3)
            if self.call_count == 3:
                raise ValueError("Simulated provider failure on batch 3")
            
            translations = {seg_id: f"Translated: {seg_id}" for seg_id in seg_ids}
            return ChatResponse(content=json.dumps(translations), model=self.model)
    
    # Create config with all required fields
    profile = ProviderProfile(
        name="test",
        kind=ProviderKind.OPENAI_COMPATIBLE,
        base_url="http://test.local",
        model="test-model",
    )
    config = AppConfig(
        app_name="TestApp",
        source_language="en",
        target_language="ru",
        active_provider="test",
        providers={"test": profile},
        translation=TranslationSettings(batch_max_segments=2, batch_max_chars=500),
        extraction=ExtractionSettings(),
        output=OutputSettings(),
        logging=LoggingSettings(),
        storage=StorageSettings(),
    )
    
    # Create 5 segments (will be 3 batches with batch_size=2)
    segments = tuple(
        TextSegment(
            segment_id=f"seg_{i}",
            source_text=f"Text {i}",
            source_file=tmp_path / "test.json",
            context=SegmentContext(file_kind=RPGMakerFileKind.SYSTEM, json_pointer=JsonPointer.root()),
        )
        for i in range(5)
    )
    
    # Create job
    job = TranslationJob(
        job_id="resume_test_job",
        project_root=tmp_path,
        source_language="en",
        target_language="ru",
        status=JobStatus.RUNNING,
    )
    
    # First run - will fail on batch 3
    checkpoint_dir = tmp_path / "checkpoints"
    pipeline = TranslationPipeline(config, FailingMockProvider(), checkpoint_dir)
    
    try:
        pipeline.translate_segments(segments, job=job)
    except Exception:
        pass  # Expected to fail
    
    # Verify checkpoint was saved for batches 1 and 2
    checkpoint_path = checkpoint_dir / f"{job.job_id}.json"
    assert checkpoint_path.exists(), "Checkpoint should be saved after batches 1 and 2"
    
    checkpoint = CheckpointState.from_dict(json.loads(checkpoint_path.read_text()))
    # Batches 1 and 2 should have 4 segments completed (seg_1, seg_2, seg_3, seg_4)
    assert len(checkpoint.completed_segment_ids) == 4, f"Expected 4 completed segments, got {len(checkpoint.completed_segment_ids)}"
    
    # Second run - resume
    provider2 = FailingMockProvider()
    pipeline2 = TranslationPipeline(config, provider2, checkpoint_dir)
    
    result_segments = pipeline2.translate_segments(segments, job=job)
    
    # Provider should only be called for batch 3 (seg_5)
    assert provider2.call_count == 1, f"Expected 1 call (batch 3 only), got {provider2.call_count}"
    
    # All segments should now be translated
    translated_count = sum(1 for s in result_segments if s.translation is not None)
    assert translated_count == 5, f"Expected 5 translated segments, got {translated_count}"
    
    # Verify batch 1 and 2 segments were skipped (not in call history)
    all_called_ids = set()
    for call_ids in provider2.call_history:
        all_called_ids.update(call_ids)
    
    # Batch 1 (seg_1, seg_2) and Batch 2 (seg_3, seg_4) should be skipped
    # Only Batch 3 (seg_5) should be called
    assert "seg_1" not in all_called_ids, "seg_1 should have been skipped (from checkpoint)"
    assert "seg_2" not in all_called_ids, "seg_2 should have been skipped (from checkpoint)"
    assert "seg_3" not in all_called_ids, "seg_3 should have been skipped (from checkpoint)"
    assert "seg_4" not in all_called_ids, "seg_4 should have been skipped (from checkpoint)"
    # seg_5 should be the only one called in the resumed run
    assert all_called_ids == {"seg_5"}, f"Expected only seg_5 to be called, got {all_called_ids}"
