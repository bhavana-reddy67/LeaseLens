from pathlib import Path

import pytest

from app.services.temp_files import clear_stale_uploads, temporary_upload
from tests.conftest import RENTAL_TEXT, make_pdf


def test_temporary_upload_is_deleted_after_success(tmp_path: Path):
    with temporary_upload(tmp_path, b"data", ".pdf") as path:
        assert path.exists()
        assert path.parent == tmp_path
    assert list(tmp_path.iterdir()) == []


def test_temporary_upload_is_deleted_after_failure(tmp_path: Path):
    with pytest.raises(RuntimeError):
        with temporary_upload(tmp_path, b"data", ".pdf"):
            raise RuntimeError("boom")
    assert list(tmp_path.iterdir()) == []


def test_unknown_suffix_is_not_used(tmp_path: Path):
    with temporary_upload(tmp_path, b"data", "/../../evil.sh") as path:
        assert path.suffix == ".bin"
        assert path.parent == tmp_path


def test_clear_stale_uploads(tmp_path: Path):
    (tmp_path / "upload-old.pdf").write_bytes(b"x")
    (tmp_path / "keep.txt").write_bytes(b"x")
    assert clear_stale_uploads(tmp_path) == 1
    assert [p.name for p in tmp_path.iterdir()] == ["keep.txt"]


def test_extract_endpoint_leaves_no_files_on_success(make_client, settings):
    response = make_client().post(
        "/api/documents/extract", files={"file": ("lease.pdf", make_pdf([RENTAL_TEXT]), "application/pdf")}
    )
    assert response.status_code == 200
    assert list(settings.upload_dir.iterdir()) == []


def test_extract_endpoint_leaves_no_files_on_failure(make_client, settings):
    client = make_client()

    async def explode(*args, **kwargs):
        raise RuntimeError("extractor crashed")

    client.app.state.extractor.extract = explode
    with _NoRaiseClient(client) as safe:
        response = safe.post(
            "/api/documents/extract", files={"file": ("lease.pdf", make_pdf([RENTAL_TEXT]), "application/pdf")}
        )
    assert response.status_code == 500
    assert "extractor crashed" not in response.text
    assert list(settings.upload_dir.iterdir()) == []


class _NoRaiseClient:
    """Returns the 500 response instead of re-raising server exceptions."""

    def __init__(self, client):
        from fastapi.testclient import TestClient

        self.client = TestClient(client.app, raise_server_exceptions=False)

    def __enter__(self):
        return self.client

    def __exit__(self, *exc):
        self.client.close()
