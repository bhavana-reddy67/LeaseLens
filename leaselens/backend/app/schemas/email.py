from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import DocumentCategory, ProviderName


class EmailFindingInput(BaseModel):
    category_label: str = Field(max_length=120)
    excerpt: str = Field(max_length=2_000)
    reason: str = Field(default="", max_length=1_500)
    questions: list[str] = Field(default_factory=list, max_length=6)
    page: int | None = None


class NegotiationEmailRequest(BaseModel):
    document_category: DocumentCategory
    findings: list[EmailFindingInput] = Field(min_length=1, max_length=15)
    recipient_role: str = Field(default="", max_length=60, description="e.g. landlord, recruiter")
    recipient_name: str = Field(default="", max_length=80)
    sender_name: str = Field(default="", max_length=80)
    tone: Literal["polite", "formal", "friendly"] = "polite"
    provider: ProviderName | None = None
    allow_cloud_processing: bool = False


class NegotiationEmailResponse(BaseModel):
    subject: str
    body: str
    provider: ProviderName
    model: str
    warnings: list[str]
