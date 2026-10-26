import pytest

from app.core.errors import UnsupportedFileError
from app.services.file_validation import detect_kind, sanitize_filename
from tests.conftest import make_pdf, make_png


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("../../etc/passwd", "passwd"),
        ("..\\..\\Windows\\win.ini", "win.ini"),
        ("lease<script>.pdf", "lease_script_.pdf"),
        ("", "document"),
        ("....", "document"),
    ],
)
def test_sanitize_filename_blocks_paths(raw, expected):
    assert sanitize_filename(raw) == expected


def test_detect_kind_accepts_valid_files():
    assert detect_kind("lease.pdf", "application/pdf", make_pdf(["hi"])[:16]) == "pdf"
    assert detect_kind("photo.PNG", "image/png", make_png()[:16]) == "png"
    assert detect_kind("scan.jpg", "application/octet-stream", b"\xff\xd8\xff\xe0rest") == "jpeg"


@pytest.mark.parametrize(
    ("name", "mime", "head"),
    [
        ("notes.txt", "text/plain", b"hello"),
        ("lease.pdf", "image/png", b"%PDF-1.7"),  # MIME does not match extension
        ("lease.pdf", "application/pdf", b"MZ\x90\x00"),  # signature does not match
        ("photo.png", "image/png", b"%PDF-1.7"),
        ("lease", "application/pdf", b"%PDF-1.7"),  # no extension
    ],
)
def test_detect_kind_rejects_bad_files(name, mime, head):
    with pytest.raises(UnsupportedFileError):
        detect_kind(name, mime, head)


def test_upload_wrong_type_returns_415(make_client):
    response = make_client().post(
        "/api/documents/extract", files={"file": ("notes.txt", b"hello world", "text/plain")}
    )
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_file"


def test_upload_too_large_returns_413(make_client):
    big = b"%PDF-1.7\n" + b"0" * (1024 * 1024 + 10)  # settings fixture limit is 1 MB
    response = make_client().post(
        "/api/documents/extract", files={"file": ("big.pdf", big, "application/pdf")}
    )
    assert response.status_code == 413


def test_upload_empty_file(make_client):
    response = make_client().post("/api/documents/extract", files={"file": ("e.pdf", b"", "application/pdf")})
    assert response.status_code == 415
