"""Split page text into clause-sized pieces that keep their page number."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas.analysis import PageInput

MAX_CLAUSE_CHARS = 1_200
MIN_CLAUSE_CHARS = 40

_NUMBERED = re.compile(
    r"^\s*(?:(?:section|clause|article)\s+\d+|\d{1,3}(?:\.\d{1,3})*[.)]\s+|\(?[a-z]\)\s+|\(?(?:i|ii|iii|iv|v|vi|vii|viii|ix|x)\)\s+)",
    re.IGNORECASE,
)
_CAPS_HEADING = re.compile(r"^[A-Z][A-Z0-9 ,&/\-]{3,60}:?$")
_SENTENCE_END = re.compile(r"(?<=[.;:])\s+")


@dataclass(frozen=True)
class Clause:
    id: str
    page: int
    text: str


def _is_heading(line: str) -> bool:
    return bool(_NUMBERED.match(line) or _CAPS_HEADING.match(line.strip()))


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _split_long(text: str) -> list[str]:
    if len(text) <= MAX_CLAUSE_CHARS:
        return [text]
    parts: list[str] = []
    current = ""
    for sentence in _SENTENCE_END.split(text):
        if current and len(current) + len(sentence) + 1 > MAX_CLAUSE_CHARS:
            parts.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
        while len(current) > MAX_CLAUSE_CHARS:  # one very long sentence
            parts.append(current[:MAX_CLAUSE_CHARS])
            current = current[MAX_CLAUSE_CHARS:]
    if current:
        parts.append(current)
    return parts


def _page_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            blocks.append(_normalise(" ".join(buffer)))
            buffer.clear()

    for line in text.splitlines():
        if not line.strip():
            flush()
            continue
        if _is_heading(line):
            flush()
        buffer.append(line)
    flush()
    return [b for b in blocks if b]


def _merge_short(blocks: list[str]) -> list[str]:
    """Attach short fragments (usually headings) to the following block."""
    merged: list[str] = []
    carry = ""
    for block in blocks:
        block = f"{carry} {block}".strip() if carry else block
        if len(block) < MIN_CLAUSE_CHARS:
            carry = block
            continue
        carry = ""
        merged.append(block)
    if carry:
        if merged:
            merged[-1] = f"{merged[-1]} {carry}"
        else:
            merged.append(carry)
    return merged


def split_into_clauses(pages: list[PageInput]) -> list[Clause]:
    clauses: list[Clause] = []
    for page in sorted(pages, key=lambda p: p.page):
        index = 0
        for block in _merge_short(_page_blocks(page.text)):
            for piece in _split_long(block):
                index += 1
                clauses.append(Clause(id=f"p{page.page}-c{index}", page=page.page, text=piece))
    return clauses
