"""Common interface that every AI provider implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from app.schemas.common import ProviderName
from app.schemas.system import ProviderStatus


@dataclass(frozen=True)
class ImageInput:
    data: bytes
    mime_type: str  # "image/png" or "image/jpeg"


class AIProvider(ABC):
    name: ProviderName
    label: str
    model: str
    is_local: bool

    @abstractmethod
    async def generate(
        self,
        system: str,
        prompt: str,
        *,
        json_schema: dict[str, Any] | None = None,
        images: list[ImageInput] | None = None,
    ) -> str:
        """Return the model's text answer.

        Raises a subclass of ``app.core.errors.ProviderError`` when the provider
        is not configured, unreachable, missing the model, or returns nothing usable.
        """

    @abstractmethod
    async def status(self) -> ProviderStatus:
        """Report availability without exposing secrets."""

    async def supports_vision(self) -> bool:
        """True only when the provider has *verified* that the model accepts images."""
        status = await self.status()
        return status.available and "vision" in status.capabilities
