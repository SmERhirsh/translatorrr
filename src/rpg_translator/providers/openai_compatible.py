"""OpenAI-compatible chat-completions provider."""

from __future__ import annotations

from typing import Any, Mapping

from rpg_translator.config.schema import ProviderProfile
from rpg_translator.core.errors import ProviderConnectionError
from rpg_translator.core.models import ProviderKind, ProviderUsage
from rpg_translator.providers.base import (
    ChatRequest,
    ChatResponse,
    ProviderHealth,
    normalize_model_ids,
)
from rpg_translator.providers.http_json import JsonHttpClient


class OpenAICompatibleProvider:
    """Provider for `/v1/chat/completions` compatible APIs."""

    kind = ProviderKind.OPENAI_COMPATIBLE

    def __init__(self, profile: ProviderProfile, *, kind: ProviderKind | None = None) -> None:
        self.profile = profile
        self._kind = kind or self.kind
        headers = dict(profile.extra_headers)
        api_key = profile.effective_api_key
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._client = JsonHttpClient(
            base_url=profile.base_url,
            timeout_seconds=profile.timeout_seconds,
            default_headers=headers,
        )

    @property
    def kind(self) -> ProviderKind:  # type: ignore[override]
        return self._kind

    @property
    def model(self) -> str:
        return self.profile.model

    @property
    def base_url(self) -> str:
        return self.profile.base_url

    def list_models(self) -> tuple[str, ...]:
        payload = self._client.get_json("/models")
        if isinstance(payload, Mapping):
            data = payload.get("data")
            if isinstance(data, list):
                return normalize_model_ids(data)
            models = payload.get("models")
            if isinstance(models, list):
                return normalize_model_ids(models)
        if isinstance(payload, list):
            return normalize_model_ids(payload)
        return ()

    def health_check(self) -> ProviderHealth:
        try:
            models = self.list_models()
        except ProviderConnectionError as exc:
            return ProviderHealth(
                ok=False,
                provider=self.kind,
                base_url=self.base_url,
                model=self.model,
                message=exc.message,
            )

        ok = not models or not self.model or self.model in models
        message = "ok" if ok else f"Model is not listed by provider: {self.model}"
        return ProviderHealth(
            ok=ok,
            provider=self.kind,
            base_url=self.base_url,
            model=self.model,
            available_models=models,
            message=message,
        )

    def chat(self, request: ChatRequest) -> ChatResponse:
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": [{"role": item.role, "content": item.content} for item in request.messages],
            "temperature": request.temperature,
            "top_p": request.top_p,
            "max_tokens": request.max_tokens,
        }
        if request.response_format:
            payload["response_format"] = {"type": request.response_format}

        response = self._client.post_json("/chat/completions", payload)
        if not isinstance(response, Mapping):
            raise ProviderConnectionError("Provider response must be a JSON object", recoverable=True)

        content = _extract_openai_content(response)
        usage = _extract_usage(response.get("usage"))
        response_model = response.get("model") if isinstance(response.get("model"), str) else request.model
        return ChatResponse(content=content, model=response_model, usage=usage, raw=response)


def _extract_openai_content(response: Mapping[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ProviderConnectionError("Provider response has no choices", recoverable=True)
    first = choices[0]
    if not isinstance(first, Mapping):
        raise ProviderConnectionError("Provider choice is malformed", recoverable=True)
    message = first.get("message")
    if isinstance(message, Mapping) and isinstance(message.get("content"), str):
        return message["content"]
    text = first.get("text")
    if isinstance(text, str):
        return text
    raise ProviderConnectionError("Provider response has no text content", recoverable=True)


def _extract_usage(value: Any) -> ProviderUsage | None:
    if not isinstance(value, Mapping):
        return None
    return ProviderUsage(
        prompt_tokens=value.get("prompt_tokens") if isinstance(value.get("prompt_tokens"), int) else None,
        completion_tokens=(
            value.get("completion_tokens") if isinstance(value.get("completion_tokens"), int) else None
        ),
        total_tokens=value.get("total_tokens") if isinstance(value.get("total_tokens"), int) else None,
    )

