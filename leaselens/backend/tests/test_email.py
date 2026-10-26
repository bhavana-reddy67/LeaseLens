import json

from tests.conftest import FakeProvider

FINDINGS = [
    {
        "category_label": "Automatic renewal",
        "excerpt": "This lease shall automatically renew unless ninety days notice is given.",
        "reason": "Long cancellation window.",
        "questions": ["Can the notice period be 30 days?"],
        "page": 1,
    }
]


def request_email(client, **extra):
    payload = {"document_category": "rental", "findings": FINDINGS, "recipient_role": "landlord",
               "sender_name": "Sam", **extra}
    return client.post("/api/negotiation-email", json=payload)


def draft(subject="Questions about the lease", body="Dear landlord,\n\nThank you for sending the lease. Could the renewal notice be 30 days?\n\nKind regards,\nSam"):
    return json.dumps({"subject": subject, "body": body})


def test_email_is_generated_from_selected_findings(make_client):
    local = FakeProvider([draft()])
    response = request_email(make_client(local=local))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["subject"] == "Questions about the lease"
    assert "30 days" in body["body"]
    assert body["provider"] == "ollama"
    assert any("never sends" in w for w in body["warnings"])
    prompt = local.calls[0]["prompt"]
    assert "automatically renew" in prompt and "page=\"1\"" in prompt and "Sam" in prompt


def test_email_flags_strong_legal_language(make_client):
    local = FakeProvider([draft(body="Dear landlord, this clause is illegal and I will sue you over it. Regards, Sam")])
    warnings = request_email(make_client(local=local)).json()["warnings"]
    assert any("illegal" in w and "sue" in w for w in warnings)


def test_email_invalid_json_twice_returns_502(make_client):
    response = request_email(make_client(local=FakeProvider(["nope", "still nope"])))
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "invalid_model_response"


def test_email_retry_recovers(make_client):
    local = FakeProvider(['{"subject": ""}', draft()])
    assert request_email(make_client(local=local)).status_code == 200
    assert len(local.calls) == 2


def test_email_cloud_requires_consent(make_client):
    cloud = FakeProvider([draft()], name="google", local=False)
    response = request_email(make_client(cloud=cloud), provider="google")
    assert response.status_code == 400
    assert cloud.calls == []


def test_email_provider_unavailable(make_client):
    response = request_email(make_client(local=FakeProvider([])))
    assert response.status_code == 503
