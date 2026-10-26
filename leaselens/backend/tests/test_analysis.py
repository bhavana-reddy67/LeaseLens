from app.core.errors import ModelNotFoundError
from tests.conftest import RENTAL_TEXT, FakeProvider, ai_answer

GOOD_AI = ai_answer(
    [
        {
            "clause_id": "p1-c1",
            "category": "auto_renewal",
            "risk_level": "high",
            "reason": "Renews automatically and needs 90 days notice.",
            "impact": "You could be locked in for another year.",
            "questions": ["What is the last date I can cancel?"],
            "confidence": "high",
        },
        {
            "clause_id": "p1-c2",
            "category": "Security deposit and deductions",  # label instead of id is accepted
            "risk_level": "HIGH",
            "reason": "Deductions for any reason.",
            "impact": "You may lose the deposit.",
            "questions": ["Which costs can be deducted?"],
            "confidence": "medium",
        },
        {
            "clause_id": "p1-c3",
            "category": "fees",
            "risk_level": "low",
            "reason": "Normal rent payment terms.",
            "impact": "None expected.",
            "questions": [],
            "confidence": "medium",
        },
        {"clause_id": "p9-c9", "category": "fees", "risk_level": "high", "reason": "x", "impact": "x",
         "questions": [], "confidence": "high"},
        {"clause_id": "p1-c4", "category": "made_up", "risk_level": "high", "reason": "x", "impact": "x",
         "questions": [], "confidence": "high"},
    ]
)


def analyze(client, text=RENTAL_TEXT, **extra):
    payload = {"category": "rental", "pages": [{"page": 1, "text": text}], **extra}
    return client.post("/api/analyze", json=payload)


def test_analysis_combines_rules_and_ai(make_client):
    local = FakeProvider([GOOD_AI])
    response = analyze(make_client(local=local))
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["provider"] == "ollama" and body["processed_locally"] is True
    assert body["ai_status"] == "completed"
    by_key = {(f["clause_id"], f["category"]): f for f in body["findings"]}
    assert set(by_key) == {
        ("p1-c1", "auto_renewal"),
        ("p1-c2", "security_deposit"),
        ("p1-c2", "unilateral_changes"),
        ("p1-c3", "fees"),
    }

    renewal = by_key[("p1-c1", "auto_renewal")]
    assert renewal["risk_level"] == "high"
    assert renewal["evidence_agreement"] == "high"
    assert renewal["assessed_by"] == ["rules", "ai"]
    assert {h["rule_id"] for h in renewal["rule_hits"]} >= {"AR-01", "AR-03"}
    assert renewal["page"] == 1
    assert renewal["excerpt"].startswith("1. TERM This lease shall automatically renew")
    assert renewal["references"][0]["source_id"].startswith("KB-AR")

    rules_only = by_key[("p1-c2", "unilateral_changes")]
    assert rules_only["assessed_by"] == ["rules"] and rules_only["ai_level"] is None
    assert rules_only["evidence_agreement"] == "low"

    assert body["summary"]["counts"] == {"high": 2, "medium": 1, "low": 1, "uncertain": 0}
    assert body["summary"]["overall"] == "high"
    assert [f["risk_level"] for f in body["findings"]] == ["high", "high", "medium", "low"]

    stages = [e["stage"] for e in body["audit"]]
    assert stages[0] == "input" and stages[-1] == "review"
    assert any("Ignored 2 item(s)" in e["detail"] for e in body["audit"])
    assert "not a lawyer" in body["disclaimer"]


def test_excerpts_come_from_document_not_model(make_client):
    tampered = ai_answer([{"clause_id": "p1-c1", "category": "auto_renewal", "risk_level": "low",
                           "reason": "ok", "impact": "ok", "questions": [], "confidence": "high",
                           "excerpt": "MODEL WROTE THIS"}])
    body = analyze(make_client(local=FakeProvider([tampered]))).json()
    assert all("MODEL WROTE THIS" not in f["excerpt"] for f in body["findings"])


def test_invalid_model_json_is_retried_then_falls_back_to_rules(make_client):
    local = FakeProvider(["this is not json", "{still not json"])
    response = analyze(make_client(local=local))
    assert response.status_code == 200
    body = response.json()
    assert body["ai_status"] == "failed"
    assert len(local.calls) == 2
    assert "not valid JSON" in local.calls[1]["prompt"]
    assert all(f["assessed_by"] == ["rules"] for f in body["findings"])
    assert any("keyword rules only" in w for w in body["warnings"])
    statuses = [e["status"] for e in body["audit"] if e["stage"] == "ai_analysis"]
    assert statuses == ["retried", "failed"]


def test_invalid_json_then_valid_json(make_client):
    local = FakeProvider(["```json\n{oops", "```json\n" + GOOD_AI + "\n```"])
    body = analyze(make_client(local=local)).json()
    assert body["ai_status"] == "completed"
    assert any(e["status"] == "retried" for e in body["audit"])


def test_schema_violations_are_rejected(make_client):
    wrong_level = ai_answer([{"clause_id": "p1-c1", "category": "auto_renewal", "risk_level": "catastrophic",
                              "reason": "", "impact": "", "questions": [], "confidence": "high"}])
    body = analyze(make_client(local=FakeProvider([wrong_level, wrong_level]))).json()
    assert body["ai_status"] == "failed"


def test_provider_unavailable_returns_503_and_no_findings(make_client):
    response = analyze(make_client(local=FakeProvider([])))
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "provider_unavailable"
    assert "findings" not in response.json()


def test_model_not_found_message(make_client):
    local = FakeProvider([ModelNotFoundError("The model 'gemma4' is not installed in Ollama.")])
    response = analyze(make_client(local=local))
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "model_not_found"


def test_cloud_provider_requires_explicit_consent(make_client):
    cloud = FakeProvider([GOOD_AI], name="google", local=False)
    client = make_client(cloud=cloud)
    refused = analyze(client, provider="google")
    assert refused.status_code == 400
    assert refused.json()["error"]["code"] == "cloud_consent_required"
    assert cloud.calls == []

    allowed = analyze(client, provider="google", allow_cloud_processing=True)
    assert allowed.status_code == 200
    assert allowed.json()["processed_locally"] is False


def test_local_mode_never_calls_cloud_provider(make_client):
    cloud = FakeProvider([GOOD_AI], name="google", local=False)
    analyze(make_client(local=FakeProvider([GOOD_AI]), cloud=cloud), allow_cloud_processing=True)
    assert cloud.calls == []


def test_no_matching_clauses_gives_honest_summary(make_client):
    text = "This agreement is between Alex and Sam. It is signed on the date written below by both people."
    body = analyze(make_client(local=FakeProvider([ai_answer([])])), text=text).json()
    assert body["findings"] == []
    assert body["summary"]["overall"] is None
    assert "does not mean the document is safe" in body["summary"]["headline"]


def test_missing_knowledge_base_reference_is_reported(make_client):
    # Interest-rate guidance only applies to loan agreements, so a rental document gets no reference.
    text = "7. PAYMENT TERMS\nAny unpaid balance accrues interest at a variable interest rate set by the landlord."
    body = analyze(make_client(local=FakeProvider([ai_answer([])])), text=text).json()
    finding = next(f for f in body["findings"] if f["category"] == "interest_and_repayment")
    assert finding["references"] == []
    assert any("No local guidance" in n for n in finding["uncertainty_notes"])
    retrieval = next(e for e in body["audit"] if e["stage"] == "retrieval")
    assert retrieval["status"] == "warning"


def test_batches_and_partial_failure(make_client):
    pages = [{"page": n, "text": f"{n}. CLAUSE\nThe landlord may enter at any time without notice, clause {n}."}
             for n in range(1, 4)]
    local = FakeProvider([ai_answer([]), "bad", "bad", ai_answer([])])
    client = make_client(local=local, ai_batch_size=1)
    body = client.post("/api/analyze", json={"category": "rental", "pages": pages}).json()
    assert body["ai_status"] == "partial"
    assert len(local.calls) == 4


def test_text_limit(make_client):
    response = analyze(make_client(max_text_chars=1000), text="word " * 400)
    assert response.status_code == 413
