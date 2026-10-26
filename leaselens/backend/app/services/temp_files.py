"""Temporary upload storage that is always cleaned up."""

from __future__ import annotations

import contextlib
import logging
import os
import secrets
from collections.abc import Iterator
from pathlib import Path

logger = logging.getLogger("leaselens.temp_files")


@contextlib.contextmanager
def temporary_upload(directory: Path, data: bytes, suffix: str) -> Iterator[Path]:
    """Write bytes to a randomly named file and delete it when the block ends,
    whether it ends normally or with an exception.

    The user's original file name is never used on disk (prevents path traversal).
    """
    safe_suffix = suffix if suffix in {".pdf", ".jpg", ".png"} else ".bin"
    path = directory / f"upload-{secrets.token_hex(16)}{safe_suffix}"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        yield path
    finally:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.warning("could not delete a temporary upload; it will be removed on next start")


def clear_stale_uploads(directory: Path) -> int:
    """Delete leftovers from a crash. Called at start-up."""
    removed = 0
    for item in directory.glob("upload-*"):
        with contextlib.suppress(OSError):
            item.unlink()
            removed += 1
    return removed
