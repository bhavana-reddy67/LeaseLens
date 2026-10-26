"""Shared test fixtures. Tests never need Ollama, Tesseract or a Google API key."""

from __future__ import annotations

import io
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.errors import ProviderUnavailableError
from app.main import create_app
from app.providers.base import AIProvider, ImageInput
from app.providers.registry import ProviderRegistry
from app.schemas.system import ProviderStatus


class FakeProvider(AIProvider):
    """Returns scripted answers. Each item is a string, a callable(prompt) -> str, or an exception."""

    def __init__(
        self,
        responses: list[Any] | None = None,
        *,
        name: str = "ollama",
        local: bool = True,
        vision: bool = False,
    ) -> None:
        self.name = name  # type: ignore[assignment]
        self.label = "Fake local" if local else "Fake cloud"
        self.model = "fake-model"
        self.is_local = local
        self.responses = list(responses or [])
        self.calls: list[dict[str, Any]] = []
        self.vision = vision

    async def generate(
        self,
        system: str,
        prompt: str,
        *,
        json_schema: dict[str, Any] | None = None,
        images: list[ImageInput] | None = None,
    ) -> str:
        self.calls.append({"system": system, "prompt": prompt, "images": images or []})
        if not self.responses:
            raise ProviderUnavailableError("Fake provider has no scripted answer.")
        answer = self.responses.pop(0)
        if isinstance(answer, Exception):
            raise answer
        if callable(answer):
            return answer(prompt)
        return answer

    async def status(self) -> ProviderStatus:
        return ProviderStatus(
            name=self.name,  # type: ignore[arg-type]
            label=self.label,
            model=self.model,
            local=self.is_local,
            configured=True,
            available=True,
            capabilities=["completion", "vision"] if self.vision else ["completion"],
            detail="fake",
        )


class FakeOcr:
    name = "fake-ocr"

    def __init__(self, text: str = "", available: bool = True, error: Exception | None = None) -> None:
        self.text = text
        self._available = available
        self.error = error
        self.calls = 0

    def available(self) -> bool:
        return self._available

    def image_to_text(self, image_bytes: bytes) -> str:
        self.calls += 1
        if self.error:
            raise self.error
        return self.text


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        temp_dir=tmp_path / "uploads",
        google_api_key=None,
        max_upload_mb=1,
        ai_batch_size=10,
    )


@pytest.fixture
def make_client(settings: Settings) -> Callable[..., TestClient]:
    def factory(
        local: FakeProvider | None = None,
        cloud: FakeProvider | None = None,
        ocr: FakeOcr | None = None,
        **overrides: Any,
    ) -> TestClient:
        app_settings = settings.model_copy(update=overrides) if overrides else settings
        registry = ProviderRegistry(
            {
                "ollama": local or FakeProvider(),
                "google": cloud or FakeProvider(name="google", local=False),
            },
            default="ollama",
        )
        app = create_app(app_settings, registry=registry, ocr=ocr or FakeOcr(available=False))
        return TestClient(app)

    return factory


def make_pdf(pages: list[str]) -> bytes:
    import pymupdf

    document = pymupdf.open()
    for text in pages:
        page = document.new_page()
        if text:
            page.insert_textbox(pymupdf.Rect(50, 50, 550, 800), text, fontsize=10)
    data = document.tobytes()
    document.close()
    return data


def make_png(size: tuple[int, int] = (200, 100)) -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", size, "white").save(buffer, format="PNG")
    return buffer.getvalue()


def ai_answer(findings: list[dict[str, Any]]) -> str:
    return json.dumps({"findings": findings})


RENTAL_TEXT = """1. TERM
This lease shall automatically renew for successive twelve month terms unless the tenant gives ninety (90) days written notice before expiry.

2. DEPOSIT
The landlord may deduct any amount from the security deposit at its sole discretion for any reason.

3. RENT
Rent is 1,500 per month, payable on the first day of each month by bank transfer to the landlord's account.

4. PETS
The tenant may keep one cat with prior written approval from the landlord, which will not be unreasonably refused."""
