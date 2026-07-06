"""LM Studio provider."""

from __future__ import annotations

from rpg_translator.config.schema import ProviderProfile
from rpg_translator.core.models import ProviderKind
from rpg_translator.providers.openai_compatible import OpenAICompatibleProvider


class LMStudioProvider(OpenAICompatibleProvider):
    """LM Studio exposes an OpenAI-compatible local API."""

    def __init__(self, profile: ProviderProfile) -> None:
        super().__init__(profile, kind=ProviderKind.LM_STUDIO)

