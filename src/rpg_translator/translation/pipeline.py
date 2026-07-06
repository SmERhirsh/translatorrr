"""Translation pipeline."""

from __future__ import annotations

from collections.abc import Sequence

from rpg_translator.config.schema import AppConfig
from rpg_translator.core.models import TextSegment
from rpg_translator.providers.base import ChatProvider


class TranslationPipeline:
    """Coordinates the end-to-end translation process."""

    def __init__(
        self,
        config: AppConfig,
        provider: ChatProvider,
    ) -> None:
        self._config = config
        self._provider = provider

    def translate_segments(
        self,
        segments: Sequence[TextSegment],
    ) -> list[TextSegment]:
        """Translate extracted text segments."""
        raise NotImplementedError