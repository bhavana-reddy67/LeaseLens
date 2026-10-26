"""Local Gemma 4 through the Ollama chat API (POST /api/chat).

Docs: https://docs.ollama.com/api/chat
"""

from __future__ import annotations

import base64
import logging
from typing import Any

import httpx

from app.core.errors import ModelNotFoundError, ProviderResponseError, ProviderUnavailableError
from app.providers.base import AIProvider, ImageInput
from app.schemas.system import ProviderStatus

logger = logging.getLogger("leaselens.providers.ollama")


class OllamaProvider(AIProvider):
    name = "ollama"
    label = "Local Ollama"
    is_local = True

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        timeout_seconds: float = 300,
        think: bool | None = False,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.think = think
        self._transport = transport  # injected in tests

    def _client(self, timeout: float) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.base_url, timeout=timeout, transport=self._transport)

    async def generate(
        self,
        system: str,
        prompt: str,
        *,
        json_schema: dict[str, Any] | None = None,
        images: list[ImageInput] | None = None,
    ) -> str:
        user_message: dict[str, Any] = {"role": "user", "content": prompt}
        if images:
            user_message["images"] = [base64.b64encode(image.data).decode("ascii") for image in images]

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, user_message],
            "stream": False,
            "options": {"temperature": 0.1},
        }
        if json_schema is not None:
            payload["format"] = json_schema
        if self.think is not None:
            payload["think"] = self.think

        response = await self._post_chat(payload)

        # Some models reject the "think" field. Retry once without it.
        if response.status_code == 400 and "think" in payload and "thinking" in _error_text(response).lower():
            payload.pop("think")
            response = await self._post_chat(payload)

        if response.status_code == 404:
            raise ModelNotFoundError(
                f"The model '{self.model}' is not installed in Ollama. "
                f"Run 'ollama pull {self.model}' and try again."
            )
        if response.status_code >= 400:
            logger.warning("ollama error status=%s", response.status_code)
            raise ProviderResponseError(
                f"Ollama returned an error (HTTP {response.status_code}): {_error_text(response)[:200]}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderResponseError("Ollama returned a response that is not valid JSON.") from exc

        message = data.get("message") if isinstance(data, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise ProviderResponseError("Ollama returned an empty answer.")
        return content

    async def _post_chat(self, payload: dict[str, Any]) -> httpx.Response:
        try:
            async with self._client(self.timeout_seconds) as client:
                return await client.post("/api/chat", json=payload)
        except httpx.TimeoutException as exc:
            raise ProviderUnavailableError(
                f"Ollama did not answer within {int(self.timeout_seconds)} seconds. "
                "Large documents on slower computers can take longer; try a shorter document "
                "or raise OLLAMA_TIMEOUT_SECONDS.",
                code="provider_timeout",
                status_code=504,
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(
                f"Cannot reach Ollama at {self.base_url}. Make sure Ollama is installed and running."
            ) from exc

    async def status(self) -> ProviderStatus:
        def result(available: bool, detail: str, capabilities: list[str] | None = None) -> ProviderStatus:
            return ProviderStatus(
                name=self.name,
                label=self.label,
                model=self.model,
                local=True,
                configured=True,
                available=available,
                capabilities=capabilities or [],
                detail=detail,
            )

        try:
            async with self._client(5) as client:
                tags = await client.get("/api/tags")
                if tags.status_code >= 400:
                    return result(False, f"Ollama answered with HTTP {tags.status_code}.")
                names = {m.get("name", "") for m in tags.json().get("models", []) if isinstance(m, dict)}
                wanted = {self.model} if ":" in self.model else {self.model, f"{self.model}:latest"}
                if not names & wanted:
                    return result(False, f"Model '{self.model}' is not installed. Run 'ollama pull {self.model}'.")

                capabilities: list[str] = []
                show = await client.post("/api/show", json={"model": self.model})
                if show.status_code < 400:
                    raw = show.json().get("capabilities", [])
                    capabilities = [str(c) for c in raw] if isinstance(raw, list) else []
                return result(True, "Ready. Documents are processed on this computer.", capabilities)
        except (httpx.HTTPError, ValueError):
            return result(False, f"Ollama is not reachable at {self.base_url}. Start Ollama and refresh.")


def _error_text(response: httpx.Response) -> str:
    try:
        data = response.json()
        if isinstance(data, dict) and isinstance(data.get("error"), str):
            return data["error"]
    except ValueError:
        pass
    return response.text or "unknown error"
