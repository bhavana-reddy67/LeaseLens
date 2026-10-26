from tests.conftest import FakeProvider


def test_health(make_client):
    response = make_client().get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["default_provider"] == "ollama"


def test_providers_lists_both_without_secrets(make_client, settings):
    from app.core.config import Settings
    from app.providers.registry import ProviderRegistry

    secret_settings = Settings(_env_file=None, google_api_key="super-secret-key-123", temp_dir=settings.temp_dir)
    registry = ProviderRegistry.from_settings(secret_settings)
    # Replace network-backed providers' status with fakes, keep Google's real "configured" logic offline.
    registry._providers["ollama"] = FakeProvider()
    client = make_client()
    client.app.state.registry = registry

    async def offline_status():
        from app.schemas.system import ProviderStatus

        return ProviderStatus(
            name="google", label="Google Gemini API", model=secret_settings.google_model, local=False,
            configured=True, available=False, capabilities=[], detail="offline in tests",
        )

    registry._providers["google"].status = offline_status  # type: ignore[method-assign]
    response = client.get("/api/providers")
    assert response.status_code == 200
    assert "super-secret-key-123" not in response.text
    names = {p["name"] for p in response.json()["providers"]}
    assert names == {"ollama", "google"}


def test_google_provider_reports_not_configured_without_key(make_client, settings):
    from app.providers.registry import ProviderRegistry

    registry = ProviderRegistry.from_settings(settings)  # settings fixture has no Google key
    registry._providers["ollama"] = FakeProvider()
    client = make_client()
    client.app.state.registry = registry
    google = next(p for p in client.get("/api/providers").json()["providers"] if p["name"] == "google")
    assert google["configured"] is False
    assert google["available"] is False
    assert google["model"] == "gemma-4-26b-a4b-it"
    assert "GOOGLE_API_KEY" in google["detail"]


def test_default_settings_use_local_ollama(settings):
    assert settings.ai_provider == "ollama"
    assert settings.ollama_base_url == "http://127.0.0.1:11434"
    assert settings.ollama_model == "gemma4"
    assert settings.google_model == "gemma-4-26b-a4b-it"


def test_production_rejects_wildcard_cors():
    import pytest
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="production", cors_origins="*")


def test_knowledge_base_endpoint(make_client):
    response = make_client().get("/api/knowledge-base")
    assert response.status_code == 200
    body = response.json()
    assert "not laws" in body["note"]
    ids = {c["id"] for c in body["categories"]}
    assert {"auto_renewal", "security_deposit", "liability"} <= ids
    assert all(c["entries"] for c in body["categories"])


def test_analyze_rejects_invalid_requests(make_client):
    client = make_client()
    assert client.post("/api/analyze", json={"category": "rental", "pages": []}).status_code == 422
    bad_category = client.post("/api/analyze", json={"category": "lease", "pages": [{"page": 1, "text": "x"}]})
    assert bad_category.status_code == 422
    assert bad_category.json()["error"]["code"] == "invalid_request"
    bad_page = client.post("/api/analyze", json={"category": "rental", "pages": [{"page": 0, "text": "x"}]})
    assert bad_page.status_code == 422


def test_validation_errors_do_not_echo_document_text(make_client):
    secret_text = "CONFIDENTIAL-CLAUSE-TEXT " * 3000  # longer than the per-page limit
    response = make_client().post(
        "/api/analyze", json={"category": "rental", "pages": [{"page": 1, "text": secret_text}]}
    )
    assert response.status_code == 422
    assert "CONFIDENTIAL-CLAUSE-TEXT" not in response.text


def test_email_rejects_empty_findings(make_client):
    response = make_client().post(
        "/api/negotiation-email", json={"document_category": "rental", "findings": []}
    )
    assert response.status_code == 422
