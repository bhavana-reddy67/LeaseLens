"""AI clause classification for one batch of clauses."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ValidationError, field_validator

from app.core.errors import ProviderResponseError
from app.providers.base import AIProvider
from app.schemas.common import RiskLevel
from app.services.clause_segmentation import Clause
from app.services.knowledge_base import KnowledgeBase
from app.services.model_output import clip, parse_json_object
from app.services.prompts import ANALYSIS_SCHEMA, ANALYSIS_SYSTEM, REPAIR_NOTE, build_analysis_prompt

logger = logging.getLogger("leaselens.clause_analysis")


class AIFinding(BaseModel):
    clause_id: str
    category: str
    risk_level: RiskLevel
    reason: str = ""
    impact: str = ""
    questions: list[str] = []
    confidence: Literal["high", "medium", "low"] = "medium"

    @field_validator("risk_level", "confidence", mode="before")
    @classmethod
    def _lower(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("reason", "impact", mode="before")
    @classmethod
    def _clip_text(cls, value: object) -> str:
        return clip(value, 600)

    @field_validator("questions", mode="before")
    @classmethod
    def _clip_questions(cls, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [clip(q, 250) for q in value if isinstance(q, str) and q.strip()][:4]


class AIBatchAnswer(BaseModel):
    findings: list[AIFinding]


@dataclass
class BatchOutcome:
    findings: list[AIFinding] = field(default_factory=list)
    retried: bool = False
    failed: bool = False
    dropped: int = 0


async def analyze_batch(
    provider: AIProvider, clauses: list[Clause], document_category: str, kb: KnowledgeBase
) -> BatchOutcome:
    """Ask the model about a batch of clauses.

    Invalid JSON is retried once. Provider outages (not running, model missing, not configured)
    are raised to the caller, because results must never be invented.
    """
    prompt = build_analysis_prompt(clauses, document_category, kb)
    outcome = BatchOutcome()
    answer: AIBatchAnswer | None = None

    for attempt in (1, 2):
        try:
            raw = await provider.generate(
                ANALYSIS_SYSTEM, prompt if attempt == 1 else prompt + REPAIR_NOTE, json_schema=ANALYSIS_SCHEMA
            )
            answer = AIBatchAnswer.model_validate(parse_json_object(raw))
            break
        except (ValueError, ValidationError, ProviderResponseError) as exc:
            logger.warning("invalid model output attempt=%d error=%s", attempt, type(exc).__name__)
            if attempt == 1:
                outcome.retried = True
            else:
                outcome.failed = True
                return outcome

    assert answer is not None
    valid_ids = {c.id for c in clauses}
    label_to_id = {c.label.lower(): c.id for c in kb.categories}
    seen: set[tuple[str, str]] = set()
    for item in answer.findings:
        category = item.category.strip()
        category = category if category in kb.category_map else label_to_id.get(category.lower(), "")
        key = (item.clause_id, category)
        if item.clause_id not in valid_ids or not category or key in seen:
            outcome.dropped += 1
            continue
        seen.add(key)
        outcome.findings.append(item.model_copy(update={"category": category}))
    return outcome
