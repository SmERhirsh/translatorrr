"""Provider contracts for chat-completion LLM backends."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence

from rpg_translator.core.models import ProviderKind, ProviderUsage


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """One chat message passed to a provider."""

    role: str
    content: str


@dataclass(frozen=True, slots=True)
class ChatRequest:
    """Provider-independent chat completion request."""

    messages: tuple[ChatMessage, ...]
    model: str
    temperature: float = 0.2
    top_p: float = 0.9
    max_tokens: int = 4096
    response_format: str | None = "json_object"


@dataclass(frozen=True, slots=True)
class ChatResponse:
    """Provider-independent chat completion response."""

    content: str
    model: str
    usage: ProviderUsage | None = None
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProviderHealth:
    """Health-check result."""

    ok: bool
    provider: ProviderKind
    base_url: str
    model: str | None = None
    available_models: tuple[str, ...] = ()
    message: str = ""


class ChatProvider(Protocol):
    """Provider interface used by the translation pipeline."""

    @property
    def kind(self) -> ProviderKind:
        """Provider kind."""

    @property
    def model(self) -> str:
        """Current model name."""

    @property
    def base_url(self) -> str:
        """Provider base URL."""

    def list_models(self) -> tuple[str, ...]:
        """Return available model IDs when supported."""

    def health_check(self) -> ProviderHealth:
        """Validate that the provider is reachable and model is usable."""

    def chat(self, request: ChatRequest) -> ChatResponse:
        """Run one chat completion request."""


def normalize_model_ids(values: Sequence[Any]) -> tuple[str, ...]:
    """Extract stable model IDs from provider-specific model payloads."""

    model_ids: list[str] = []
    for value in values:
        if isinstance(value, str):
            model_ids.append(value)
        elif isinstance(value, Mapping):
            model_id = value.get("id") or value.get("name") or value.get("model")
            if isinstance(model_id, str):
                model_ids.append(model_id)
    return tuple(dict.fromkeys(model_ids))

