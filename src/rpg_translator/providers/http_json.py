"""Small stdlib JSON HTTP client for provider integrations."""

from __future__ import annotations

import json
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from rpg_translator.core.errors import ProviderConnectionError


def join_url(base_url: str, path: str) -> str:
    """Join a base URL and an API path without dropping path prefixes."""

    return urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


class JsonHttpClient:
    """Tiny blocking JSON client suited for CLI and worker-thread use."""

    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float,
        default_headers: Mapping[str, str] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.default_headers = dict(default_headers or {})

    def get_json(self, path: str) -> Any:
        request = Request(
            join_url(self.base_url, path),
            method="GET",
            headers=self._headers(),
        )
        return self._send(request)

    def post_json(self, path: str, payload: Mapping[str, Any]) -> Any:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            join_url(self.base_url, path),
            method="POST",
            data=body,
            headers=self._headers({"Content-Type": "application/json"}),
        )
        return self._send(request)

    def _headers(self, extra: Mapping[str, str] | None = None) -> dict[str, str]:
        headers = {"Accept": "application/json", **self.default_headers}
        if extra:
            headers.update(extra)
        return headers

    def _send(self, request: Request) -> Any:
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise ProviderConnectionError(
                f"Provider returned HTTP {exc.code}",
                details={"url": request.full_url, "status": exc.code, "body": body[:1000]},
                recoverable=500 <= exc.code < 600,
            ) from exc
        except URLError as exc:
            raise ProviderConnectionError(
                "Could not connect to provider",
                details={"url": request.full_url, "error": str(exc.reason)},
                recoverable=True,
            ) from exc
        except OSError as exc:
            raise ProviderConnectionError(
                "Provider request failed",
                details={"url": request.full_url, "error": str(exc)},
                recoverable=True,
            ) from exc

        try:
            return json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            raise ProviderConnectionError(
                "Provider returned malformed JSON",
                details={"url": request.full_url, "body": raw[:1000]},
                recoverable=True,
            ) from exc

