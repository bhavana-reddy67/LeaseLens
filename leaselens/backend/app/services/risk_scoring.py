"""Transparent combination of rule-based and AI risk levels.

How the final level is chosen (also explained in the README):

| Rules        | AI                     | Final level        | Evidence agreement |
|--------------|------------------------|--------------------|--------------------|
| level R      | not assessed           | R                  | low                |
| level R      | uncertain              | R                  | low                |
| none         | uncertain              | uncertain          | low                |
| none         | level A, low confidence| uncertain          | low                |
| none         | level A                | A                  | medium             |
| level R      | level A                | higher of R and A  | high if equal, medium if one step apart, low if two |

Low AI confidence lowers agreement by one step. "Evidence agreement" describes how well the
two checks agree. It is not legal certainty.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.schemas.analysis import Finding, RiskSummary
from app.schemas.common import EvidenceAgreement, RiskLevel

Level = Literal["high", "medium", "low"]
ORDER: dict[str, int] = {"low": 1, "medium": 2, "high": 3}
AGREEMENT_STEPS: list[EvidenceAgreement] = ["low", "medium", "high"]
DISPLAY_ORDER: dict[str, int] = {"high": 0, "medium": 1, "low": 2, "uncertain": 3}


@dataclass
class Assessment:
    level: RiskLevel
    agreement: EvidenceAgreement
    notes: list[str] = field(default_factory=list)


def highest_rule_level(levels: list[Level]) -> Level | None:
    return max(levels, key=lambda lv: ORDER[lv]) if levels else None


def combine(rule_level: Level | None, ai_level: RiskLevel | None, ai_confidence: str | None) -> Assessment:
    if rule_level is None and ai_level is None:
        raise ValueError("A finding needs at least one assessment.")

    if ai_level is None:
        assert rule_level is not None
        return Assessment(rule_level, "low", ["Only the keyword rules flagged this clause; the AI did not assess it."])

    if ai_level == "uncertain":
        if rule_level:
            return Assessment(rule_level, "low", ["The AI could not judge this clause; the level comes from the keyword rules."])
        return Assessment("uncertain", "low", ["The AI was unsure and no keyword rule matched."])

    if rule_level is None:
        if ai_confidence == "low":
            return Assessment("uncertain", "low", ["Only the AI flagged this clause, and it was not confident."])
        return Assessment(ai_level, "medium", ["Only the AI flagged this clause; no keyword rule matched."])

    gap = abs(ORDER[rule_level] - ORDER[ai_level])
    level: Level = rule_level if ORDER[rule_level] >= ORDER[ai_level] else ai_level  # type: ignore[assignment]
    agreement_index = 2 - gap
    notes: list[str] = []
    if gap == 2:
        notes.append(
            f"The keyword rules ({rule_level}) and the AI ({ai_level}) disagree. "
            "The higher level is shown; read this clause carefully."
        )
    if ai_confidence == "low":
        agreement_index = max(agreement_index - 1, 0)
        notes.append("The AI reported low confidence for this clause.")
    return Assessment(level, AGREEMENT_STEPS[agreement_index], notes)


def summarize(findings: list[Finding]) -> RiskSummary:
    counts: dict[RiskLevel, int] = {"high": 0, "medium": 0, "low": 0, "uncertain": 0}
    for finding in findings:
        counts[finding.risk_level] += 1

    if not findings:
        return RiskSummary(
            overall=None,
            counts=counts,
            headline="No clauses matched the configured categories. This does not mean the document "
            "is safe; please still read it in full.",
        )

    overall: RiskLevel = next((lv for lv in ("high", "medium", "low") if counts[lv]), "uncertain")  # type: ignore[assignment]
    headline = (
        f"{len(findings)} finding(s): {counts['high']} high, {counts['medium']} medium, "
        f"{counts['low']} low and {counts['uncertain']} uncertain. Highest level: {overall.capitalize()}."
    )
    return RiskSummary(overall=overall, counts=counts, headline=headline)
