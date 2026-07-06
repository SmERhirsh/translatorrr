"""Provider abstraction and concrete chat backends."""

from rpg_translator.providers.base import ChatMessage, ChatProvider, ChatRequest, ChatResponse, ProviderHealth
from rpg_translator.providers.lm_studio import LMStudioProvider
from rpg_translator.providers.ollama import OllamaProvider
from rpg_translator.providers.openai import OpenAIProvider
from rpg_translator.providers.openai_compatible import OpenAICompatibleProvider
from rpg_translator.providers.registry import (
    create_provider,
    normalize_provider_name,
    provider_profile_from_config,
)

__all__ = [
    "ChatMessage",
    "ChatProvider",
    "ChatRequest",
    "ChatResponse",
    "LMStudioProvider",
    "OllamaProvider",
    "OpenAICompatibleProvider",
    "OpenAIProvider",
    "ProviderHealth",
    "create_provider",
    "normalize_provider_name",
    "provider_profile_from_config",
]
