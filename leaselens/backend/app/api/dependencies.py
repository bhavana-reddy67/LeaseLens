"""FastAPI dependencies. Shared objects live on app.state so tests can replace them."""

from fastapi import Request

from app.agents.contract_review import ContractReviewWorkflow
from app.core.config import Settings
from app.providers.registry import ProviderRegistry
from app.services.extraction import DocumentExtractor
from app.services.knowledge_base import KnowledgeBase
from app.services.ocr import OcrEngine


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_registry(request: Request) -> ProviderRegistry:
    return request.app.state.registry


def get_kb(request: Request) -> KnowledgeBase:
    return request.app.state.kb


def get_ocr(request: Request) -> OcrEngine:
    return request.app.state.ocr


def get_extractor(request: Request) -> DocumentExtractor:
    return request.app.state.extractor


def get_workflow(request: Request) -> ContractReviewWorkflow:
    return request.app.state.workflow
