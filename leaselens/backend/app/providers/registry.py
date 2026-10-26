"""Chooses the AI provider for a request and enforces the cloud-consent rule."""

from __future__ import annotations

from app.core.config import Settings
from app.core.errors import CloudConsentRequiredError
from app.providers.base import AIProvider
from app.providers.google import GoogleProvider
from app.providers.ollama import OllamaProvider
from app.schemas.common import ProviderName


class ProviderRegistry:
    def __init__(self, providers: dict[str, AIProvider], default: ProviderName) -> None:
        self._providers = providers
        self.default: ProviderName = default

    @classmethod
    def from_settings(cls, settings: Settings) -> "ProviderRegistry":
        api_key = settings.google_api_key.get_secret_value() if settings.google_api_key else None
        return cls(
            {
                "ollama": OllamaProvider(
                    settings.ollama_base_url,
                    settings.ollama_model,
                    timeout_seconds=settings.ollama_timeout_seconds,
                    think=settings.ollama_think,
                ),
                "google": GoogleProvider(
                    api_key, settings.google_model, timeout_seconds=settings.google_timeout_seconds
                ),
            },
            default=settings.ai_provider,
        )

    def all(self) -> list[AIProvider]:
        return list(self._providers.values())

    def get(self, name: ProviderName | None) -> AIProvider:
        return self._providers[name or self.default]

    def resolve(self, requested: ProviderName | None, allow_cloud_processing: bool) -> AIProvider:
        """Return the provider, refusing cloud providers unless the user opted in for this request."""
        provider = self.get(requested)
        if not provider.is_local and not allow_cloud_processing:
            raise CloudConsentRequiredError(
                f"{provider.label} sends document text to a cloud service. "
                "Confirm cloud processing in the app, or switch to Local Ollama."
            )
        return provider

    def local_vision_provider(self) -> AIProvider | None:
        """The provider allowed to read images during extraction (local only, never cloud)."""
        provider = self._providers.get("ollama")
        return provider if provider and provider.is_local else None
