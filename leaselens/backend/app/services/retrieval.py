"""Small TF-IDF retriever over the local guidance entries (no external services)."""

from __future__ import annotations

import math
import re
from collections import Counter

from app.schemas.analysis import KnowledgeReference
from app.services.knowledge_base import GuidanceEntry, KnowledgeBase

SAME_CATEGORY_BONUS = 0.2
MIN_SCORE = 0.08
# Guidance from a different category must share much more wording to count as relevant.
CROSS_CATEGORY_MIN_SCORE = 0.3

_TOKEN = re.compile(r"[a-z]{3,}")
_STOPWORDS = set(
    """the and for any all are with this that from shall will may such other than into upon been
    being its their there these those which who whom whose your you our has have had not but per
    each under within without party parties agreement contract hereby herein thereof any""".split()
)


def tokenize(text: str) -> list[str]:
    tokens = []
    for token in _TOKEN.findall(text.lower()):
        if token in _STOPWORDS:
            continue
        if token.endswith("ies") and len(token) > 4:
            token = token[:-3] + "y"
        elif token.endswith("s") and not token.endswith("ss") and len(token) > 4:
            token = token[:-1]
        tokens.append(token)
    return tokens


class TfidfRetriever:
    def __init__(self, kb: KnowledgeBase) -> None:
        self.kb = kb
        self.entries: list[GuidanceEntry] = kb.entries
        documents = [tokenize(e.search_text(kb.label_for(e.category))) for e in self.entries]
        document_frequency: Counter[str] = Counter()
        for tokens in documents:
            document_frequency.update(set(tokens))
        total = len(documents)
        self.idf = {term: math.log((1 + total) / (1 + df)) + 1 for term, df in document_frequency.items()}
        self.vectors = [self._vector(tokens) for tokens in documents]

    def _vector(self, tokens: list[str]) -> dict[str, float]:
        counts = Counter(t for t in tokens if t in self.idf)
        vector = {term: count * self.idf[term] for term, count in counts.items()}
        norm = math.sqrt(sum(v * v for v in vector.values())) or 1.0
        return {term: value / norm for term, value in vector.items()}

    def search(
        self, query: str, category: str | None, document_category: str, top_k: int = 2
    ) -> list[KnowledgeReference]:
        query_vector = self._vector(tokenize(query))
        scored: list[tuple[float, GuidanceEntry, list[str]]] = []
        for entry, vector in zip(self.entries, self.vectors):
            if document_category not in entry.applies_to:
                continue
            shared = set(query_vector) & set(vector)
            score = sum(query_vector[t] * vector[t] for t in shared)
            same_category = category is not None and entry.category == category
            if same_category:
                score += SAME_CATEGORY_BONUS
            if score < MIN_SCORE or (not same_category and score < CROSS_CATEGORY_MIN_SCORE):
                continue
            terms = sorted(shared, key=lambda t: query_vector[t] * vector[t], reverse=True)[:4]
            scored.append((score, entry, terms if not same_category else ["same category", *terms]))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            KnowledgeReference(
                source_id=entry.id,
                title=entry.title,
                relevance=_relevance_text(entry, terms, self.kb),
                score=round(min(score, 1.0), 3),
            )
            for score, entry, terms in scored[:top_k]
        ]


def _relevance_text(entry: GuidanceEntry, terms: list[str], kb: KnowledgeBase) -> str:
    parts = []
    if terms and terms[0] == "same category":
        parts.append(f"Same category ({kb.label_for(entry.category)})")
        terms = terms[1:]
    if terms:
        parts.append("shared terms: " + ", ".join(terms))
    return "; ".join(parts) + "." if parts else "Related general guidance."
