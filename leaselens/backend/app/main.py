"""FastAPI application entry point.

Run from the backend folder:
    uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.agents.contract_review import ContractReviewWorkflow
from app.api.routes import router
from app.core.config import Settings, get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.providers.registry import ProviderRegistry
from app.services.extraction import DocumentExtractor
from app.services.knowledge_base import KnowledgeBase, get_knowledge_base
from app.services.ocr import NoOcr, OcrEngine, TesseractOcr
from app.services.retrieval import TfidfRetriever
from app.services.temp_files import clear_stale_uploads


def create_app(
    settings: Settings | None = None,
    registry: ProviderRegistry | None = None,
    ocr: OcrEngine | None = None,
    kb: KnowledgeBase | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        clear_stale_uploads(settings.upload_dir)
        yield

    development = settings.environment == "development"
    app = FastAPI(
        title="LeaseLens API",
        version=__version__,
        description="Privacy-first contract red-flag assistant. Informational only, not legal advice.",
        docs_url="/api/docs" if development else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if development else None,
        lifespan=lifespan,
    )

    kb = kb or get_knowledge_base()
    registry = registry or ProviderRegistry.from_settings(settings)
    ocr = ocr or (TesseractOcr(settings.tesseract_cmd) if settings.ocr_enabled else NoOcr())

    app.state.settings = settings
    app.state.kb = kb
    app.state.registry = registry
    app.state.ocr = ocr
    app.state.extractor = DocumentExtractor(settings, ocr, registry.local_vision_provider())
    app.state.workflow = ContractReviewWorkflow(settings, kb, TfidfRetriever(kb))

    # Only the Angular dev server origins are allowed by default (see CORS_ORIGINS in .env).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
        allow_credentials=False,
    )
    register_error_handlers(app)
    app.include_router(router)
    return app


app = create_app()
