"""Optional cloud provider: Gemma 4 through the Gemini API (google-genai SDK).

Docs: https://ai.google.dev/gemma/docs/core/gemma_on_gemini_api
The documented pattern is:
    from google import genai
    client = genai.Client()
    client.models.generate_content(model="gemma-4-26b-a4b-it", contents=..., config=...)

This provider is only used when the user explicitly selects it and confirms that
document text may be sent to Google.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.errors import (
    ModelNotFoundError,
    ProviderNotConfiguredError,
    ProviderResponseError,
    ProviderUnavailableError,
)
from app.providers.base import AIProvider, ImageInput
from app.schemas.system import ProviderStatus

logger = logging.getLogger("leaselens.providers.google")


class GoogleProvider(AIProvider):
    name = "google"
    label = "Google Gemini API"
    is_local = False

    def __init__(self, api_key: str | None, model: str, *, timeout_seconds: float = 120) -> None:
        self._api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def _client(self) -> Any:
        if not self._api_key:
            raise ProviderNotConfiguredError(
                "The Google provider is not configured. Add GOOGLE_API_KEY to the backend .env file "
                "and restart the server."
            )
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:  # pragma: no cover - dependency is in requirements.txt
            raise ProviderNotConfiguredError(
                "The google-genai package is not installed. Run 'pip install -r requirements.txt'."
            ) from exc
        return genai.Client(
            api_key=self._api_key,
            http_options=types.HttpOptions(timeout=int(self.timeout_seconds * 1000)),
        )

    async def generate(
        self,
        system: str,
        prompt: str,
        *,
        json_schema: dict[str, Any] | None = None,
        images: list[ImageInput] | None = None,
    ) -> str:
        from google.genai import types

        client = self._client()
        contents: list[Any] = [
            types.Part.from_bytes(data=image.data, mime_type=image.mime_type) for image in images or []
        ]
        # JSON-schema output mode is not documented for Gemma on the Gemini API,
        # so the schema is described in the prompt and the answer is validated afterwards.
        contents.append(prompt)
        config = types.GenerateContentConfig(system_instruction=system, temperature=0.1)

        try:
            response = await client.aio.models.generate_content(
                model=self.model, contents=contents, config=config
            )
        except Exception as exc:  # noqa: BLE001 - mapped to safe messages below
            raise self._map_error(exc) from exc

        text = getattr(response, "text", None)
        if not isinstance(text, str) or not text.strip():
            raise ProviderResponseError("The Google API returned an empty answer.")
        return text

    async def status(self) -> ProviderStatus:
        base = {
            "name": self.name,
            "label": self.label,
            "model": self.model,
            "local": False,
        }
        if not self._api_key:
            return ProviderStatus(
                **base,
                configured=False,
                available=False,
                capabilities=[],
                detail="Optional. Set GOOGLE_API_KEY in the backend .env file to enable it.",
            )
        try:
            client = self._client()
            await client.aio.models.get(model=self.model)
        except Exception as exc:  # noqa: BLE001
            mapped = self._map_error(exc)
            return ProviderStatus(
                **base, configured=True, available=False, capabilities=[], detail=mapped.message
            )
        return ProviderStatus(
            **base,
            configured=True,
            available=True,
            # Image input for Gemma 4 is documented on the Gemma-on-Gemini-API page.
            capabilities=["completion", "vision"],
            detail="Ready. Document text is sent to Google when you use this provider.",
        )

    def _map_error(self, exc: Exception) -> Exception:
        if isinstance(exc, (ProviderNotConfiguredError, ProviderUnavailableError, ProviderResponseError)):
            return exc
        code = getattr(exc, "code", None)
        logger.warning("google provider error type=%s code=%s", type(exc).__name__, code)
        if code == 404:
            return ModelNotFoundError(
                f"The Google model '{self.model}' is not available for this API key. "
                "Check GOOGLE_MODEL against the Gemma on Gemini API documentation."
            )
        if code in (401, 403):
            return ProviderNotConfiguredError(
                "Google rejected the API key. Check GOOGLE_API_KEY in the backend .env file."
            )
        if code == 400:
            return ProviderResponseError("Google rejected the request (HTTP 400). Try a shorter document.")
        if code == 429:
            return ProviderUnavailableError("The Google API rate limit was reached. Wait a minute and try again.")
        return ProviderUnavailableError("The Google API could not be reached. Check your internet connection.")
