"""Turn an uploaded PDF or image into page-numbered text."""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from pathlib import Path

import anyio

from app.core.config import Settings
from app.core.errors import ExtractionError, LimitExceededError, ProviderError
from app.providers.base import AIProvider, ImageInput
from app.schemas.documents import ExtractionMethod, ExtractionResponse, PageText
from app.services.file_validation import FileKind
from app.services.ocr import OcrEngine, transcribe_with_vision

logger = logging.getLogger("leaselens.extraction")

MAX_IMAGE_PIXELS = 40_000_000
MIN_DOCUMENT_CHARS = 20


@dataclass
class _RawPage:
    page: int
    text: str
    method: ExtractionMethod
    image: bytes | None = None  # PNG bytes, only kept in memory for pages that need OCR


class DocumentExtractor:
    def __init__(
        self, settings: Settings, ocr: OcrEngine, vision_provider: AIProvider | None = None
    ) -> None:
        self.settings = settings
        self.ocr = ocr
        self.vision_provider = vision_provider

    async def extract(self, path: Path, kind: FileKind, display_name: str) -> ExtractionResponse:
        warnings: list[str] = []
        if kind == "pdf":
            pages = await anyio.to_thread.run_sync(self._read_pdf, path)
        else:
            pages = await anyio.to_thread.run_sync(self._read_image, path)

        needs_ocr = [page for page in pages if page.image is not None]
        if needs_ocr:
            await self._run_ocr(needs_ocr, warnings)

        page_texts = [
            PageText(page=p.page, text=p.text, method=p.method if p.text.strip() else "none")
            for p in pages
        ]
        total_chars = sum(len(p.text.strip()) for p in page_texts)
        if total_chars < MIN_DOCUMENT_CHARS:
            hint = " ".join(warnings) or "The document may be blank or an image that could not be read."
            raise ExtractionError(f"No readable text was found in this document. {hint}")
        if total_chars > self.settings.max_text_chars:
            raise LimitExceededError(
                f"The document has about {total_chars:,} characters of text, more than the "
                f"{self.settings.max_text_chars:,} character limit. Try uploading the relevant pages only."
            )

        empty_pages = [p.page for p in page_texts if p.method == "none"]
        if empty_pages and len(empty_pages) < len(page_texts):
            warnings.append(f"No text was found on page(s) {', '.join(map(str, empty_pages[:15]))}.")

        methods = sorted({p.method for p in page_texts if p.method != "none"})
        logger.info("extracted kind=%s pages=%d chars=%d methods=%s", kind, len(page_texts), total_chars, methods)
        return ExtractionResponse(
            file_name=display_name,
            file_type=kind,
            page_count=len(page_texts),
            pages=page_texts,
            total_chars=total_chars,
            methods_used=methods,  # type: ignore[arg-type]
            warnings=warnings,
        )

    # --- PDF -----------------------------------------------------------------

    def _read_pdf(self, path: Path) -> list[_RawPage]:
        import pymupdf

        try:
            document = pymupdf.open(path, filetype="pdf")
        except Exception as exc:  # noqa: BLE001 - PyMuPDF raises several error types
            raise ExtractionError("The PDF could not be opened. It may be damaged.") from exc

        with document:
            if document.needs_pass:
                raise ExtractionError("The PDF is password-protected. Remove the password and upload it again.")
            if document.page_count == 0:
                raise ExtractionError("The PDF has no pages.")
            if document.page_count > self.settings.max_pdf_pages:
                raise LimitExceededError(
                    f"The PDF has {document.page_count} pages; the limit is {self.settings.max_pdf_pages}."
                )

            pages: list[_RawPage] = []
            for number, page in enumerate(document, start=1):
                text = page.get_text("text") or ""
                image = None
                if len(text.strip()) < self.settings.min_chars_per_page_before_ocr and self.settings.ocr_enabled:
                    image = page.get_pixmap(dpi=200).tobytes("png")
                pages.append(_RawPage(page=number, text=text, method="pdf_text", image=image))
            return pages

    # --- Images --------------------------------------------------------------

    def _read_image(self, path: Path) -> list[_RawPage]:
        from PIL import Image, ImageOps, UnidentifiedImageError

        try:
            with Image.open(path) as probe:
                probe.verify()
            with Image.open(path) as image:
                if image.width * image.height > MAX_IMAGE_PIXELS:
                    raise LimitExceededError("The image is too large. Please upload a smaller photo or scan.")
                upright = ImageOps.exif_transpose(image).convert("RGB")
                buffer = io.BytesIO()
                upright.save(buffer, format="PNG")
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
            raise ExtractionError("The image could not be read. It may be damaged.") from exc

        if not self.settings.ocr_enabled:
            raise ExtractionError("Reading text from images needs OCR, which is turned off (OCR_ENABLED=false).")
        return [_RawPage(page=1, text="", method="none", image=buffer.getvalue())]

    # --- OCR -----------------------------------------------------------------

    async def _run_ocr(self, pages: list[_RawPage], warnings: list[str]) -> None:
        if self.ocr.available():
            for page in pages:
                image = page.image or b""
                try:
                    page.text = await anyio.to_thread.run_sync(self.ocr.image_to_text, image)
                    page.method = "ocr"
                except Exception:  # noqa: BLE001
                    logger.warning("ocr failed page=%d", page.page)
                    warnings.append(f"OCR could not read page {page.page}.")
                finally:
                    page.image = None
            return

        vision = self.vision_provider
        if self.settings.vision_ocr_fallback and vision is not None and vision.is_local:
            if await vision.supports_vision():
                for page in pages:
                    try:
                        page.text = await transcribe_with_vision(
                            vision, ImageInput(data=page.image or b"", mime_type="image/png")
                        )
                        page.method = "vision_model"
                    except ProviderError as exc:
                        warnings.append(f"The local model could not read page {page.page}: {exc.message}")
                    finally:
                        page.image = None
                warnings.append(
                    "Scanned pages were read by the local Gemma model because Tesseract is not installed. "
                    "Please check the extracted text carefully."
                )
                return

        for page in pages:
            page.image = None
        warnings.append(
            f"{len(pages)} page(s) look scanned, but no OCR engine is available. Install Tesseract OCR "
            "(see README), or run Ollama with a vision-capable model."
        )
