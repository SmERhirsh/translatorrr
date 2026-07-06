"""Ollama native chat provider."""

from __future__ import annotations

from typing import Any, Mapping

from rpg_translator.config.schema import ProviderProfile
from rpg_translator.core.errors import ProviderConnectionError
from rpg_translator.core.models import ProviderKind, ProviderUsage
from rpg_translator.providers.base import ChatRequest, ChatResponse, ProviderHealth, normalize_model_ids
from rpg_translator.providers.http_json import JsonHttpClient


class OllamaProvider:
    """Provider for Ollama's native `/api/chat` endpoint."""

    kind = ProviderKind.OLLAMA

    def __init__(self, profile: ProviderProfile) -> None:
        self.profile = profile
        self._client = JsonHttpClient(
            base_url=profile.base_url,
            timeout_seconds=profile.timeout_seconds,
            default_headers=profile.extra_headers,
        )

    @property
    def model(self) -> str:
        return self.profile.model

    @property
    def base_url(self) -> str:
        return self.profile.base_url

    def list_models(self) -> tuple[str, ...]:
        payload = self._client.get_json("/api/tags")
        if isinstance(payload, Mapping):
            models = payload.get("models")
            if isinstance(models, list):
                return normalize_model_ids(models)
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
        return ProviderHealth(
            ok=ok,
            provider=self.kind,
            base_url=self.base_url,
            model=self.model,
            available_models=models,
            message="ok" if ok else f"Model is not listed by Ollama: {self.model}",
        )

    def chat(self, request: ChatRequest) -> ChatResponse:
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": [{"role": item.role, "content": item.content} for item in request.messages],
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "top_p": request.top_p,
                "num_predict": request.max_tokens,
            },
        }
        response = self._client.post_json("/api/chat", payload)
        if not isinstance(response, Mapping):
            raise ProviderConnectionError("Ollama response must be a JSON object", recoverable=True)

        message = response.get("message")
        if not isinstance(message, Mapping) or not isinstance(message.get("content"), str):
            raise ProviderConnectionError("Ollama response has no message content", recoverable=True)

        usage = ProviderUsage(
            prompt_tokens=(
                response.get("prompt_eval_count") if isinstance(response.get("prompt_eval_count"), int) else None
            ),
            completion_tokens=(
                response.get("eval_count") if isinstance(response.get("eval_count"), int) else None
            ),
            total_tokens=_ollama_total_tokens(response),
        )
        return ChatResponse(
            content=message["content"],
            model=response.get("model") if isinstance(response.get("model"), str) else request.model,
            usage=usage,
            raw=response,
        )


def _ollama_total_tokens(response: Mapping[str, Any]) -> int | None:
    prompt = response.get("prompt_eval_count")
    completion = response.get("eval_count")
    if isinstance(prompt, int) and isinstance(completion, int):
        return prompt + completion
    return None

