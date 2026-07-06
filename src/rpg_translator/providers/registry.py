"""Provider factory."""

from __future__ import annotations

from dataclasses import replace

from rpg_translator.config.schema import AppConfig, ProviderProfile
from rpg_translator.core.errors import ConfigError
from rpg_translator.core.models import ProviderKind
from rpg_translator.providers.base import ChatProvider
from rpg_translator.providers.lm_studio import LMStudioProvider
from rpg_translator.providers.ollama import OllamaProvider
from rpg_translator.providers.openai import OpenAIProvider
from rpg_translator.providers.openai_compatible import OpenAICompatibleProvider

PROVIDER_ALIASES = {
    "lmstudio": "lm_studio",
    "lm_studio": "lm_studio",
    "ollama": "ollama",
    "openai": "openai",
    "openai-compatible": "openai_compatible",
    "openai_compatible": "openai_compatible",
    "compatible": "openai_compatible",
}


def normalize_provider_name(value: str) -> str:
    return PROVIDER_ALIASES.get(value.strip().lower(), value.strip())


def create_provider(profile: ProviderProfile) -> ChatProvider:
    if profile.kind is ProviderKind.LM_STUDIO:
        return LMStudioProvider(profile)
    if profile.kind is ProviderKind.OLLAMA:
        return OllamaProvider(profile)
    if profile.kind is ProviderKind.OPENAI:
        return OpenAIProvider(profile)
    if profile.kind is ProviderKind.OPENAI_COMPATIBLE:
        return OpenAICompatibleProvider(profile)
    raise ConfigError(f"Unsupported provider kind: {profile.kind.value}")


def provider_profile_from_config(
    config: AppConfig,
    *,
    provider_name: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> ProviderProfile:
    selected = normalize_provider_name(provider_name or config.active_provider)
    if selected in config.providers:
        profile = config.providers[selected]
    else:
        try:
            kind = ProviderKind(selected)
        except ValueError as exc:
            raise ConfigError(f"Unknown provider profile or kind: {selected}") from exc
        profile = _default_profile_for_kind(kind)

    return replace(
        profile,
        model=model or profile.model,
        base_url=base_url or profile.base_url,
        api_key=api_key if api_key is not None else profile.api_key,
    )


def _default_profile_for_kind(kind: ProviderKind) -> ProviderProfile:
    if kind is ProviderKind.LM_STUDIO:
        return ProviderProfile(
            name="lm_studio",
            kind=kind,
            base_url="http://localhost:1234/v1",
            model="local-model",
        )
    if kind is ProviderKind.OLLAMA:
        return ProviderProfile(
            name="ollama",
            kind=kind,
            base_url="http://localhost:11434",
            model="llama3.1",
        )
    if kind is ProviderKind.OPENAI:
        return ProviderProfile(
            name="openai",
            kind=kind,
            base_url="https://api.openai.com/v1",
            model="gpt-4.1-mini",
            api_key_env="OPENAI_API_KEY",
        )
    return ProviderProfile(
        name="openai_compatible",
        kind=ProviderKind.OPENAI_COMPATIBLE,
        base_url="http://localhost:8000/v1",
        model="local-model",
    )

