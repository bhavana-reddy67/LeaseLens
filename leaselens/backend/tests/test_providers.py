import json

import httpx
import pytest

from app.core.errors import (
    CloudConsentRequiredError,
    ModelNotFoundError,
    ProviderNotConfiguredError,
    ProviderResponseError,
    ProviderUnavailableError,
)
from app.providers.google import GoogleProvider
from app.providers.ollama import OllamaProvider
from app.providers.registry import ProviderRegistry
from tests.conftest import FakeProvider


def ollama_with(handler) -> OllamaProvider:
    return OllamaProvider("http://127.0.0.1:11434", "gemma4", transport=httpx.MockTransport(handler))


async def test_ollama_generate_sends_documented_chat_payload():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"message": {"role": "assistant", "content": '{"ok": true}'}, "done": True})

    answer = await ollama_with(handler).generate("sys", "hello", json_schema={"type": "object"})
    assert answer == '{"ok": true}'
    assert seen["path"] == "/api/chat"
    assert seen["body"]["model"] == "gemma4"
    assert seen["body"]["stream"] is False
    assert seen["body"]["format"] == {"type": "object"}
    assert seen["body"]["messages"][0] == {"role": "system", "content": "sys"}


async def test_ollama_model_not_found():
    provider = ollama_with(lambda r: httpx.Response(404, json={"error": "model 'gemma4' not found"}))
    with pytest.raises(ModelNotFoundError) as info:
        await provider.generate("s", "p")
    assert "ollama pull gemma4" in info.value.message


async def test_ollama_not_running():
    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(ProviderUnavailableError):
        await ollama_with(handler).generate("s", "p")


async def test_ollama_timeout():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(ProviderUnavailableError) as info:
        await ollama_with(handler).generate("s", "p")
    assert info.value.status_code == 504


async def test_ollama_invalid_response_shape():
    provider = ollama_with(lambda r: httpx.Response(200, json={"unexpected": True}))
    with pytest.raises(ProviderResponseError):
        await provider.generate("s", "p")


async def test_ollama_retries_without_think_when_unsupported():
    bodies = []

    def handler(request):
        body = json.loads(request.content)
        bodies.append(body)
        if "think" in body:
            return httpx.Response(400, json={"error": "model does not support thinking"})
        return httpx.Response(200, json={"message": {"content": "fine"}})

    assert await ollama_with(handler).generate("s", "p") == "fine"
    assert "think" in bodies[0] and "think" not in bodies[1]


async def test_ollama_status_reports_capabilities():
    def handler(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "gemma4:latest"}]})
        return httpx.Response(200, json={"capabilities": ["completion", "vision"]})

    status = await ollama_with(handler).status()
    assert status.available is True
    assert "vision" in status.capabilities


async def test_ollama_status_model_missing():
    status = await ollama_with(lambda r: httpx.Response(200, json={"models": [{"name": "llama3:latest"}]})).status()
    assert status.available is False
    assert "ollama pull gemma4" in status.detail


async def test_google_without_key_is_not_configured():
    provider = GoogleProvider(None, "gemma-4-26b-a4b-it")
    status = await provider.status()
    assert status.configured is False and status.available is False
    with pytest.raises(ProviderNotConfiguredError):
        await provider.generate("s", "p")


def test_google_error_mapping_keeps_model_name():
    provider = GoogleProvider("key", "gemma-4-26b-a4b-it")

    class NotFound(Exception):
        code = 404

    mapped = provider._map_error(NotFound())
    assert isinstance(mapped, ModelNotFoundError)
    assert "gemma-4-26b-a4b-it" in mapped.message


def test_registry_requires_consent_for_cloud():
    registry = ProviderRegistry(
        {"ollama": FakeProvider(), "google": FakeProvider(name="google", local=False)}, default="ollama"
    )
    assert registry.resolve(None, False).name == "ollama"
    with pytest.raises(CloudConsentRequiredError):
        registry.resolve("google", False)
    assert registry.resolve("google", True).name == "google"
    assert registry.local_vision_provider().is_local
