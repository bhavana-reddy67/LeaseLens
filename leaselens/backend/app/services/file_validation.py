"""Upload validation: extension, declared MIME type, file signature and size."""

from __future__ import annotations

import re
import unicodedata
from typing import Literal

from fastapi import UploadFile

from app.core.errors import FileTooLargeError, UnsupportedFileError

FileKind = Literal["pdf", "jpeg", "png"]

EXTENSIONS: dict[str, FileKind] = {".pdf": "pdf", ".jpg": "jpeg", ".jpeg": "jpeg", ".png": "png"}
MIME_TYPES: dict[FileKind, set[str]] = {
    "pdf": {"application/pdf"},
    "jpeg": {"image/jpeg", "image/jpg", "image/pjpeg"},
    "png": {"image/png"},
}
# Some browsers send a generic type; the file signature check below still applies.
GENERIC_MIME_TYPES = {"", "application/octet-stream"}
SIGNATURES: dict[FileKind, bytes] = {
    "pdf": b"%PDF-",
    "jpeg": b"\xff\xd8\xff",
    "png": b"\x89PNG\r\n\x1a\n",
}
SUPPORTED_TEXT = "PDF, JPG, JPEG or PNG"


def sanitize_filename(raw: str | None) -> str:
    """Return a display-safe file name with no directories or control characters."""
    name = (raw or "").replace("\\", "/").split("/")[-1]
    name = unicodedata.normalize("NFKC", name)
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip(" .")
    name = re.sub(r"\.{2,}", ".", name)
    return name[:100] or "document"


def detect_kind(filename: str, content_type: str | None, head: bytes) -> FileKind:
    extension = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    kind = EXTENSIONS.get(extension)
    if kind is None:
        raise UnsupportedFileError(f"Unsupported file type. Please upload a {SUPPORTED_TEXT} file.")

    declared = (content_type or "").split(";")[0].strip().lower()
    if declared not in MIME_TYPES[kind] and declared not in GENERIC_MIME_TYPES:
        raise UnsupportedFileError(
            "The file type does not match its extension. Please upload a real "
            f"{SUPPORTED_TEXT} file."
        )

    if not head.startswith(SIGNATURES[kind]):
        raise UnsupportedFileError(
            "The file content does not look like a valid "
            f"{kind.upper()} file. It may be damaged or renamed."
        )
    return kind


async def read_limited(upload: UploadFile, max_bytes: int) -> bytes:
    """Read the upload in chunks and stop as soon as it exceeds the limit."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise FileTooLargeError(
                f"The file is larger than the {max_bytes // (1024 * 1024)} MB limit."
            )
        chunks.append(chunk)
    data = b"".join(chunks)
    if not data:
        raise UnsupportedFileError("The uploaded file is empty.")
    return data
