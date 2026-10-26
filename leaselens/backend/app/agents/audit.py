"""Analysis timeline. Records stages, counts and source ids, never document text."""

from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.analysis import AuditEvent


class AuditTrail:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def add(self, stage: str, status: str, detail: str, sources: list[str] | None = None) -> None:
        self.events.append(
            AuditEvent(
                stage=stage,
                status=status,  # type: ignore[arg-type]
                detail=detail,
                sources=sources or [],
                timestamp=datetime.now(timezone.utc),
            )
        )
