"""Shared type aliases used across request and response schemas."""

from typing import Literal

ProviderName = Literal["ollama", "google"]
DocumentCategory = Literal["rental", "employment", "loan", "other"]
RiskLevel = Literal["high", "medium", "low", "uncertain"]
EvidenceAgreement = Literal["high", "medium", "low"]

DOCUMENT_CATEGORY_LABELS: dict[str, str] = {
    "rental": "Rental agreement",
    "employment": "Employment contract",
    "loan": "Loan agreement",
    "other": "Other contract",
}

DISCLAIMER = (
    "LeaseLens is an informational tool, not a lawyer. It can miss clauses or misjudge them, "
    "and it does not decide whether a term is legal, enforceable or safe. For important "
    "decisions, ask a qualified legal professional in your jurisdiction."
)
