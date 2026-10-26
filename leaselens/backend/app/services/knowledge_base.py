"""Loads and validates the local knowledge base (categories, rules, guidance)."""

from __future__ import annotations

import json
import re
from functools import cached_property, lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

KB_DIR = Path(__file__).resolve().parents[1] / "knowledge_base"

KB_NOTE = (
    "General contract-review guidance written for LeaseLens. These entries are not laws, "
    "regulations or legal citations, and rules differ between countries, states and cities."
)


class Category(BaseModel):
    id: str
    label: str
    description: str


class Rule(BaseModel):
    model_config = ConfigDict(ignored_types=(cached_property,))

    id: str
    category: str
    level: Literal["high", "medium", "low"]
    pattern: str
    description: str

    @cached_property
    def regex(self) -> re.Pattern[str]:
        return re.compile(self.pattern, re.IGNORECASE)


class GuidanceEntry(BaseModel):
    id: str
    category: str
    title: str
    applies_to: list[str]
    summary: str
    warning_signs: list[str]
    example_clause: str
    questions: list[str]

    def search_text(self, category_label: str) -> str:
        return " ".join(
            [self.title, category_label, self.summary, " ".join(self.warning_signs), self.example_clause]
        )


class KnowledgeBase(BaseModel):
    categories: list[Category]
    rules: list[Rule]
    entries: list[GuidanceEntry]

    @model_validator(mode="after")
    def _check_references(self) -> "KnowledgeBase":
        category_ids = {c.id for c in self.categories}
        for kind, items in (("rule", self.rules), ("guidance entry", self.entries)):
            ids = [item.id for item in items]
            if len(ids) != len(set(ids)):
                raise ValueError(f"Duplicate {kind} id in knowledge base.")
            for item in items:
                if item.category not in category_ids:
                    raise ValueError(f"{kind} {item.id} uses unknown category '{item.category}'.")
        for rule in self.rules:
            try:
                re.compile(rule.pattern)
            except re.error as exc:
                raise ValueError(f"Rule {rule.id} has an invalid pattern: {exc}") from exc
        return self

    @property
    def category_map(self) -> dict[str, Category]:
        return {c.id: c for c in self.categories}

    def label_for(self, category_id: str) -> str:
        category = self.category_map.get(category_id)
        return category.label if category else category_id

    def entry(self, entry_id: str) -> GuidanceEntry | None:
        return next((e for e in self.entries if e.id == entry_id), None)

    @classmethod
    def load(cls, directory: Path = KB_DIR) -> "KnowledgeBase":
        def read(name: str) -> dict:
            return json.loads((directory / name).read_text(encoding="utf-8"))

        return cls(
            categories=read("categories.json")["categories"],
            rules=read("risk_rules.json")["rules"],
            entries=read("guidance.json")["entries"],
        )


@lru_cache
def get_knowledge_base() -> KnowledgeBase:
    return KnowledgeBase.load()
