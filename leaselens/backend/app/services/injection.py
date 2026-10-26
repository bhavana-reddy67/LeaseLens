"""Prompt-injection defences.

Document text is untrusted. LeaseLens:
1. escapes it so it cannot close the XML-style tags that wrap it in the prompt,
2. tells the model to treat it as data only,
3. flags text that looks like instructions aimed at an AI,
4. never uses the model's copy of a clause; excerpts always come from the original text,
5. keeps the keyword rules independent of the model, so a manipulated model answer
   cannot hide a clause that the rules flagged.
"""

from __future__ import annotations

import html
import re

_PATTERNS = [
    r"\b(ignore|disregard|forget|override)\b.{0,30}\b(previous|prior|above|earlier|all|any|your)\b.{0,20}\b(instructions?|prompts?|rules|guidelines)\b",
    r"\byou are now\b",
    r"\b(system|developer)\s+(prompt|message|instructions?)\b",
    r"\bnew instructions?\s*:",
    r"\b(return|output|respond with|reply with)\b.{0,20}\b(no|zero|empty)\b.{0,20}\b(findings?|results?|risks?)\b",
    r"\b(mark|classify|rate|treat)\b.{0,30}\b(as|is)\s+(low[- ]risk|safe|fair|harmless)\b",
    r"</?\s*(system|assistant|user|clause|clauses|document|instructions?)\s*>",
    r"\b(ai|assistant|language model|llm|chatbot|gemma)\b.{0,40}\b(must|should|will|shall)\b.{0,40}\b(say|report|answer|ignore|output|respond)\b",
]
_COMPILED = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in _PATTERNS]


def looks_like_injection(text: str) -> bool:
    return any(pattern.search(text) for pattern in _COMPILED)


def escape_untrusted(text: str) -> str:
    """Escape <, > and & so document text cannot break out of its prompt delimiters."""
    return html.escape(text, quote=False)
