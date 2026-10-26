from tests.conftest import FakeOcr, FakeProvider, RENTAL_TEXT, make_pdf, make_png


def upload(client, name, data, mime):
    return client.post("/api/documents/extract", files={"file": (name, data, mime)})


def test_pdf_text_extraction_keeps_pages(make_client):
    pdf = make_pdf([RENTAL_TEXT, "5. NOTICES\nAll notices must be given in writing to the addresses above."])
    response = upload(make_client(), "lease.pdf", pdf, "application/pdf")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["page_count"] == 2
    assert body["pages"][0]["page"] == 1
    assert "automatically renew" in body["pages"][0]["text"]
    assert body["pages"][1]["method"] == "pdf_text"
    assert body["methods_used"] == ["pdf_text"]
    assert "deleted" in body["retention_note"]


def test_scanned_pdf_uses_ocr_fallback(make_client):
    ocr = FakeOcr(text="The landlord may enter the premises at any time without notice.")
    pdf = make_pdf([""])  # a page with no text layer
    response = upload(make_client(ocr=ocr), "scan.pdf", pdf, "application/pdf")
    assert response.status_code == 200, response.text
    assert ocr.calls == 1
    assert response.json()["pages"][0]["method"] == "ocr"


def test_image_uses_ocr(make_client):
    ocr = FakeOcr(text="Tenant shall pay a late fee of 5% per day on unpaid rent.")
    response = upload(make_client(ocr=ocr), "photo.png", make_png(), "image/png")
    assert response.status_code == 200, response.text
    assert response.json()["file_type"] == "png"
    assert response.json()["pages"][0]["method"] == "ocr"


def test_image_falls_back_to_local_vision_model_when_no_tesseract(make_client):
    local = FakeProvider(["The deposit is non-refundable and will be retained by the landlord."], vision=True)
    client = make_client(local=local, ocr=FakeOcr(available=False))
    response = upload(client, "photo.png", make_png(), "image/png")
    assert response.status_code == 200, response.text
    assert response.json()["pages"][0]["method"] == "vision_model"
    assert local.calls and local.calls[0]["images"]


def test_vision_fallback_not_used_without_verified_capability(make_client):
    local = FakeProvider(["should not be called"], vision=False)
    response = upload(make_client(local=local, ocr=FakeOcr(available=False)), "p.png", make_png(), "image/png")
    assert response.status_code == 422
    assert "no OCR engine" in response.json()["error"]["message"]
    assert local.calls == []


def test_empty_document_is_rejected_with_explanation(make_client):
    response = upload(make_client(ocr=FakeOcr(text="")), "blank.pdf", make_pdf([""]), "application/pdf")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "extraction_failed"


def test_corrupted_pdf(make_client):
    response = upload(make_client(), "bad.pdf", b"%PDF-1.7\nthis is not really a pdf", "application/pdf")
    assert response.status_code == 422
    assert "/" not in response.json()["error"]["message"].replace("I/O", "")  # no file paths leaked


def test_too_many_pages(make_client):
    pdf = make_pdf(["Clause text on this page is long enough to count."] * 3)
    response = upload(make_client(max_pdf_pages=2), "long.pdf", pdf, "application/pdf")
    assert response.status_code == 413
