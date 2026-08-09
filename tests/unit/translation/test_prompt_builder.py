"""Unit tests for prompt builder."""

from __future__ import annotations

import json

import pytest

from rpg_translator.core.models import JsonPointer, RPGMakerFileKind, SegmentContext, TextSegment
from rpg_translator.translation.prompt_builder import (
    TranslationPrompt,
    build_translation_prompt,
    parse_translation_response,
)


class TestBuildTranslationPrompt:
    """Tests for build_translation_prompt function."""

    def test_basic_prompt_structure(self) -> None:
        """Prompt has required structure."""
        segments = (
            TextSegment(
                segment_id="seg_1",
                source_text="Hello world",
                source_file=None,  # type: ignore[arg-type]
                context=SegmentContext(file_kind=RPGMakerFileKind.SYSTEM, json_pointer=JsonPointer.root()),
            ),
        )
        prompt = build_translation_prompt(segments, "en", "ru")

        assert "system_message" in dir(prompt)
        assert "user_message" in dir(prompt)
        assert prompt.segment_ids == ("seg_1",)
        assert "Hello world" in prompt.user_message
        assert "en" in prompt.system_message.lower() or "English" in prompt.system_message
        assert "ru" in prompt.system_message.lower() or "Russian" in prompt.system_message

    def test_multiple_segments(self) -> None:
        """Multiple segments are included."""
        segments = tuple(
            TextSegment(
                segment_id=f"seg_{i}",
                source_text=f"Text {i}",
                source_file=None,  # type: ignore[arg-type]
                context=SegmentContext(file_kind=RPGMakerFileKind.SYSTEM, json_pointer=JsonPointer.root()),
            )
            for i in range(3)
        )
        prompt = build_translation_prompt(segments, "en", "fr")

        assert prompt.segment_ids == ("seg_0", "seg_1", "seg_2")
        assert "Text 0" in prompt.user_message
        assert "Text 1" in prompt.user_message
        assert "Text 2" in prompt.user_message

    def test_to_chat_request(self) -> None:
        """Prompt converts to ChatRequest correctly."""
        segments = (
            TextSegment(
                segment_id="seg_1",
                source_text="Test",
                source_file=None,  # type: ignore[arg-type]
                context=SegmentContext(file_kind=RPGMakerFileKind.SYSTEM, json_pointer=JsonPointer.root()),
            ),
        )
        prompt = build_translation_prompt(segments, "en", "de")
        request = prompt.to_chat_request(model="test-model", temperature=0.5)

        assert request.model == "test-model"
        assert request.temperature == 0.5
        assert len(request.messages) == 2
        assert request.messages[0].role == "system"
        assert request.messages[1].role == "user"
        assert request.response_format == "json_object"


class TestParseTranslationResponse:
    """Tests for parse_translation_response function."""

    def test_valid_response(self) -> None:
        """Valid JSON response parses correctly."""
        response_content = json.dumps({
            "seg_1": "Translation 1",
            "seg_2": "Translation 2",
        })
        result = parse_translation_response(response_content, ("seg_1", "seg_2"))

        assert result == {"seg_1": "Translation 1", "seg_2": "Translation 2"}

    def test_invalid_json(self) -> None:
        """Invalid JSON raises ValueError."""
        with pytest.raises(ValueError, match="Invalid JSON"):
            parse_translation_response("not json", ("seg_1",))

    def test_not_object(self) -> None:
        """Non-object JSON raises ValueError."""
        with pytest.raises(ValueError, match="must be a JSON object"):
            parse_translation_response("[\"array\"]", ("seg_1",))

    def test_missing_segment(self) -> None:
        """Missing segment raises ValueError."""
        response_content = json.dumps({"seg_1": "Translation 1"})
        with pytest.raises(ValueError, match="Missing translations"):
            parse_translation_response(response_content, ("seg_1", "seg_2"))

    def test_extra_segment(self) -> None:
        """Extra segment raises ValueError."""
        response_content = json.dumps({
            "seg_1": "Translation 1",
            "seg_2": "Translation 2",
            "seg_3": "Extra",
        })
        with pytest.raises(ValueError, match="Unexpected translations"):
            parse_translation_response(response_content, ("seg_1", "seg_2"))

    def test_non_string_value(self) -> None:
        """Non-string translation raises ValueError."""
        response_content = json.dumps({"seg_1": 123})
        with pytest.raises(ValueError, match="must be a string"):
            parse_translation_response(response_content, ("seg_1",))

    def test_empty_translation(self) -> None:
        """Empty translation raises ValueError."""
        response_content = json.dumps({"seg_1": "   "})
        with pytest.raises(ValueError, match="is empty"):
            parse_translation_response(response_content, ("seg_1",))

    def test_order_independent(self) -> None:
        """Key order doesn't matter."""
        response_content = json.dumps({"seg_2": "Two", "seg_1": "One"})
        result = parse_translation_response(response_content, ("seg_1", "seg_2"))

        assert result == {"seg_1": "One", "seg_2": "Two"}
