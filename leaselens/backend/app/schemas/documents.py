from typing import Literal

from pydantic import BaseModel, Field

ExtractionMethod = Literal["pdf_text", "ocr", "vision_model", "none"]


class PageText(BaseModel):
    page: int = Field(ge=1)
    text: str
    method: ExtractionMethod


class ExtractionResponse(BaseModel):
    file_name: str = Field(description="Sanitised file name, for display only.")
    file_type: Literal["pdf", "jpeg", "png"]
    page_count: int
    pages: list[PageText]
    total_chars: int
    methods_used: list[ExtractionMethod]
    warnings: list[str]
    retention_note: str = Field(
        default="The uploaded file was deleted from the server after text extraction. "
        "The extracted text is kept only in your browser until you start a new analysis."
    )
