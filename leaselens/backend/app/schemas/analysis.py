from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import DocumentCategory, EvidenceAgreement, ProviderName, RiskLevel

MAX_PAGES_PER_REQUEST = 300
MAX_PAGE_CHARS = 60_000


class PageInput(BaseModel):
    page: int = Field(ge=1, le=10_000)
    text: str = Field(max_length=MAX_PAGE_CHARS)


class AnalyzeRequest(BaseModel):
    category: DocumentCategory
    pages: list[PageInput] = Field(min_length=1, max_length=MAX_PAGES_PER_REQUEST)
    provider: ProviderName | None = Field(
        default=None, description="Leave empty to use the server default (AI_PROVIDER)."
    )
    allow_cloud_processing: bool = Field(
        default=False,
        description="Must be true to send document text to a cloud provider such as Google.",
    )


class KnowledgeReference(BaseModel):
    source_id: str
    title: str
    kind: Literal["general_guidance"] = "general_guidance"
    relevance: str
    score: float


class RuleHit(BaseModel):
    rule_id: str
    description: str
    level: Literal["high", "medium", "low"]


class Finding(BaseModel):
    id: str
    clause_id: str
    category: str
    category_label: str
    excerpt: str = Field(description="Text copied from the document, never written by the model.")
    page: int | None
    risk_level: RiskLevel
    reason: str
    impact: str
    questions: list[str]
    references: list[KnowledgeReference]
    rule_hits: list[RuleHit]
    rule_level: Literal["high", "medium", "low"] | None
    ai_level: RiskLevel | None
    assessed_by: list[Literal["rules", "ai"]]
    evidence_agreement: EvidenceAgreement = Field(
        description="How well the rule check and AI check agree. Not legal certainty."
    )
    uncertainty_notes: list[str]


class RiskSummary(BaseModel):
    overall: RiskLevel | None
    counts: dict[RiskLevel, int]
    headline: str


class AuditEvent(BaseModel):
    stage: str
    status: Literal["completed", "warning", "failed", "retried", "skipped"]
    detail: str
    sources: list[str] = Field(default_factory=list)
    timestamp: datetime


class AnalyzeResponse(BaseModel):
    provider: ProviderName
    model: str
    processed_locally: bool
    category: DocumentCategory
    ai_status: Literal["completed", "partial", "failed"]
    summary: RiskSummary
    findings: list[Finding]
    warnings: list[str]
    audit: list[AuditEvent]
    disclaimer: str
