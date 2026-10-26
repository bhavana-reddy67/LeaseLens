from typing import Literal

from pydantic import BaseModel

from app.schemas.common import ProviderName


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
    default_provider: ProviderName


class ProviderStatus(BaseModel):
    name: ProviderName
    label: str
    model: str
    local: bool
    configured: bool
    available: bool
    capabilities: list[str]
    detail: str


class ProvidersResponse(BaseModel):
    default_provider: ProviderName
    providers: list[ProviderStatus]
    max_upload_mb: int
    ocr_available: bool


class KnowledgeEntrySummary(BaseModel):
    id: str
    title: str
    applies_to: list[str]


class KnowledgeCategory(BaseModel):
    id: str
    label: str
    description: str
    entries: list[KnowledgeEntrySummary]


class KnowledgeBaseResponse(BaseModel):
    note: str
    categories: list[KnowledgeCategory]
