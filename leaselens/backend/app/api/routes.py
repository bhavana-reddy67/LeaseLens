"""HTTP endpoints. Business logic lives in services/ and agents/."""

from __future__ import annotations

import asyncio
from typing import Annotated

import anyio
from fastapi import APIRouter, Depends, File, UploadFile

from app import __version__
from app.agents.contract_review import ContractReviewWorkflow
from app.api.dependencies import get_extractor, get_kb, get_ocr, get_registry, get_settings, get_workflow
from app.core.config import Settings
from app.providers.registry import ProviderRegistry
from app.schemas.analysis import AnalyzeRequest, AnalyzeResponse
from app.schemas.documents import ExtractionResponse
from app.schemas.email import NegotiationEmailRequest, NegotiationEmailResponse
from app.schemas.system import (
    HealthResponse,
    KnowledgeBaseResponse,
    KnowledgeCategory,
    KnowledgeEntrySummary,
    ProvidersResponse,
)
from app.services.email_drafting import draft_email
from app.services.extraction import DocumentExtractor
from app.services.file_validation import detect_kind, read_limited, sanitize_filename
from app.services.knowledge_base import KB_NOTE, KnowledgeBase
from app.services.ocr import OcrEngine
from app.services.temp_files import temporary_upload

router = APIRouter(prefix="/api")

SettingsDep = Annotated[Settings, Depends(get_settings)]
RegistryDep = Annotated[ProviderRegistry, Depends(get_registry)]


@router.get("/health", response_model=HealthResponse)
async def health(settings: SettingsDep) -> HealthResponse:
    return HealthResponse(status="ok", version=__version__, default_provider=settings.ai_provider)


@router.get("/providers", response_model=ProvidersResponse)
async def providers(
    settings: SettingsDep, registry: RegistryDep, ocr: Annotated[OcrEngine, Depends(get_ocr)]
) -> ProvidersResponse:
    statuses = await asyncio.gather(*(p.status() for p in registry.all()))
    ocr_available = await anyio.to_thread.run_sync(ocr.available)
    return ProvidersResponse(
        default_provider=registry.default,
        providers=list(statuses),
        max_upload_mb=settings.max_upload_mb,
        ocr_available=ocr_available,
    )


@router.post("/documents/extract", response_model=ExtractionResponse)
async def extract_document(
    settings: SettingsDep,
    extractor: Annotated[DocumentExtractor, Depends(get_extractor)],
    file: Annotated[UploadFile, File(description="PDF, JPG, JPEG or PNG")],
) -> ExtractionResponse:
    display_name = sanitize_filename(file.filename)
    data = await read_limited(file, settings.max_upload_bytes)
    kind = detect_kind(display_name, file.content_type, data[:16])
    suffix = {"pdf": ".pdf", "jpeg": ".jpg", "png": ".png"}[kind]
    try:
        with temporary_upload(settings.upload_dir, data, suffix) as path:
            return await extractor.extract(path, kind, display_name)
    finally:
        await file.close()


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    request: AnalyzeRequest,
    registry: RegistryDep,
    workflow: Annotated[ContractReviewWorkflow, Depends(get_workflow)],
) -> AnalyzeResponse:
    provider = registry.resolve(request.provider, request.allow_cloud_processing)
    return await workflow.run(request, provider)


@router.post("/negotiation-email", response_model=NegotiationEmailResponse)
async def negotiation_email(request: NegotiationEmailRequest, registry: RegistryDep) -> NegotiationEmailResponse:
    provider = registry.resolve(request.provider, request.allow_cloud_processing)
    return await draft_email(provider, request)


@router.get("/knowledge-base", response_model=KnowledgeBaseResponse)
async def knowledge_base(kb: Annotated[KnowledgeBase, Depends(get_kb)]) -> KnowledgeBaseResponse:
    return KnowledgeBaseResponse(
        note=KB_NOTE,
        categories=[
            KnowledgeCategory(
                id=category.id,
                label=category.label,
                description=category.description,
                entries=[
                    KnowledgeEntrySummary(id=e.id, title=e.title, applies_to=e.applies_to)
                    for e in kb.entries
                    if e.category == category.id
                ],
            )
            for category in kb.categories
        ],
    )
