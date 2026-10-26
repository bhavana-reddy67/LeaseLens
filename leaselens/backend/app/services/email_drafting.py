"""Negotiation email drafting from the findings the user selected."""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel, Field, ValidationError

from app.core.errors import ProviderResponseError
from app.providers.base import AIProvider
from app.schemas.common import DOCUMENT_CATEGORY_LABELS
from app.schemas.email import NegotiationEmailRequest, NegotiationEmailResponse
from app.services.injection import escape_untrusted
from app.services.model_output import parse_json_object
from app.services.prompts import EMAIL_SCHEMA, EMAIL_SYSTEM, REPAIR_NOTE

logger = logging.getLogger("leaselens.email")

STRONG_LANGUAGE = re.compile(
    r"\b(illegal|unlawful|lawsuit|sue|void|unenforceable|fraud\w*|scam|court)\b", re.IGNORECASE
)


class EmailDraft(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=20, max_length=8_000)


def build_email_prompt(request: NegotiationEmailRequest) -> str:
    findings = []
    for number, finding in enumerate(request.findings, start=1):
        page = f" page=\"{finding.page}\"" if finding.page else ""
        questions = " | ".join(finding.questions)
        findings.append(
            f'<finding number="{number}" topic="{escape_untrusted(finding.category_label)}"{page}>\n'
            f"Clause text: {escape_untrusted(finding.excerpt)}\n"
            f"Why it was flagged: {escape_untrusted(finding.reason)}\n"
            f"Questions: {escape_untrusted(questions)}\n"
            f"</finding>"
        )
    recipient = request.recipient_name.strip() or request.recipient_role.strip() or "the other party"
    sender = request.sender_name.strip() or "leave a placeholder like [Your name]"
    return f"""Write a {request.tone} email about a {DOCUMENT_CATEGORY_LABELS[request.document_category].lower()}.
Recipient: {escape_untrusted(recipient)}
Sender name: {escape_untrusted(sender)}

Structure:
1. Thank them and say you are reviewing the document before signing.
2. For each finding, refer to the clause briefly (mention the page if given), ask the question or
   propose a reasonable clarification or change in one or two sentences.
3. Close politely, saying you look forward to discussing it.

Findings to discuss:
{chr(10).join(findings)}"""


async def draft_email(provider: AIProvider, request: NegotiationEmailRequest) -> NegotiationEmailResponse:
    prompt = build_email_prompt(request)
    draft: EmailDraft | None = None
    for attempt in (1, 2):
        try:
            raw = await provider.generate(
                EMAIL_SYSTEM, prompt if attempt == 1 else prompt + REPAIR_NOTE, json_schema=EMAIL_SCHEMA
            )
            draft = EmailDraft.model_validate(parse_json_object(raw))
            break
        except (ValueError, ValidationError, ProviderResponseError) as exc:
            logger.warning("invalid email output attempt=%d error=%s", attempt, type(exc).__name__)
    if draft is None:
        raise ProviderResponseError("The AI returned an email draft that could not be read. Please try again.")

    warnings: list[str] = []
    strong = sorted({m.lower() for m in STRONG_LANGUAGE.findall(f"{draft.subject} {draft.body}")})
    if strong:
        warnings.append(
            "The draft uses strong legal wording (" + ", ".join(strong) + "). "
            "Consider softening it before sending."
        )
    warnings.append("Review and edit the draft before sending. LeaseLens never sends emails for you.")
    return NegotiationEmailResponse(
        subject=draft.subject.strip(),
        body=draft.body.strip(),
        provider=provider.name,
        model=provider.model,
        warnings=warnings,
    )
