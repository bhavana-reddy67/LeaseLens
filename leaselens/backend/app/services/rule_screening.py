"""Deterministic keyword rules applied to each clause."""

from __future__ import annotations

from collections import defaultdict

from app.schemas.analysis import RuleHit
from app.services.clause_segmentation import Clause
from app.services.knowledge_base import KnowledgeBase


def screen_clauses(clauses: list[Clause], kb: KnowledgeBase) -> dict[str, dict[str, list[RuleHit]]]:
    """Return {clause_id: {category_id: [rule hits]}} for clauses that matched any rule."""
    results: dict[str, dict[str, list[RuleHit]]] = {}
    for clause in clauses:
        by_category: dict[str, list[RuleHit]] = defaultdict(list)
        for rule in kb.rules:
            if rule.regex.search(clause.text):
                by_category[rule.category].append(
                    RuleHit(rule_id=rule.id, description=rule.description, level=rule.level)
                )
        if by_category:
            results[clause.id] = dict(by_category)
    return results
