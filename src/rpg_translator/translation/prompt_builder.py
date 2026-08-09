"""Prompt builder for translation requests."""

from __future__ import annotations

import json
from dataclasses import dataclass

from rpg_translator.core.models import TextSegment
from rpg_translator.providers.base import ChatMessage, ChatRequest


@dataclass(frozen=True, slots=True)
class TranslationPrompt:
    """A prepared prompt for translating a batch of segments."""

    system_message: str
    user_message: str
    segment_ids: tuple[str, ...]

    def to_chat_request(
        self,
        model: str,
        temperature: float = 0.2,
        top_p: float = 0.9,
        max_tokens: int = 4096,
    ) -> ChatRequest:
        """Convert this prompt to a ChatRequest."""
        return ChatRequest(
            messages=(
                ChatMessage(role="system", content=self.system_message),
                ChatMessage(role="user", content=self.user_message),
            ),
            model=model,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            response_format="json_object",
        )


def build_translation_prompt(
    segments: tuple[TextSegment, ...],
    source_language: str,
    target_language: str,
    *,
    include_context: bool = False,
) -> TranslationPrompt:
    """Build a translation prompt for a batch of segments.

    Args:
        segments: Segments to translate (already protected).
        source_language: Source language name or code.
        target_language: Target language name or code.
        include_context: Whether to include segment context in the prompt.

    Returns:
        TranslationPrompt ready to be converted to ChatRequest.
    """
    segment_ids = tuple(segment.segment_id for segment in segments)

    system_message = (
        f"You are a professional translator specializing in video game localization. "
        f"Translate the following text from {source_language} to {target_language}. "
        f"Preserve all placeholders, formatting codes, and special syntax exactly as they appear. "
        f"Return ONLY a valid JSON object with segment IDs as keys and translations as values."
    )

    # Build the input structure for translation
    if include_context:
        input_data = {
            seg_id: {
                "text": segment.source_text,
                "context": segment.context.field_name or "",
            }
            for seg_id, segment in zip(segment_ids, segments)
        }
    else:
        input_data = {seg_id: segment.source_text for seg_id, segment in zip(segment_ids, segments)}

    user_message = (
        f"Please translate the following segments from {source_language} to {target_language}.\n"
        f"IMPORTANT: Return your response as a JSON object where keys are segment IDs and values are translations.\n"
        f"Do not add any extra text, explanations, or formatting outside the JSON object.\n\n"
        f"Input segments:\n{json.dumps(input_data, ensure_ascii=False, indent=2)}\n\n"
        f"Response format example:\n{{\n  \"segment_1\": \"translated text 1\",\n  \"segment_2\": \"translated text 2\"\n}}"
    )

    return TranslationPrompt(
        system_message=system_message,
        user_message=user_message,
        segment_ids=segment_ids,
    )


def parse_translation_response(
    response_content: str,
    expected_segment_ids: tuple[str, ...],
) -> dict[str, str]:
    """Parse and validate a translation response from the provider.

    Args:
        response_content: Raw content string from provider response.
        expected_segment_ids: Expected segment IDs that should be present.

    Returns:
        Dictionary mapping segment IDs to translated text.

    Raises:
        ValueError: If response is malformed or missing expected segments.
    """
    try:
        parsed = json.loads(response_content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in response: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ValueError("Response must be a JSON object")

    # Validate all expected segments are present
    missing_ids = set(expected_segment_ids) - set(parsed.keys())
    if missing_ids:
        raise ValueError(f"Missing translations for segments: {missing_ids}")

    # Validate no extra segments
    extra_ids = set(parsed.keys()) - set(expected_segment_ids)
    if extra_ids:
        raise ValueError(f"Unexpected translations for segments: {extra_ids}")

    # Validate all values are strings
    for seg_id, translation in parsed.items():
        if not isinstance(translation, str):
            raise ValueError(f"Translation for {seg_id} must be a string")
        if not translation.strip():
            raise ValueError(f"Translation for {seg_id} is empty")

    return parsed