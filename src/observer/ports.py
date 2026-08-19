from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from src.core.event import EventEnvelope


@dataclass(frozen=True)
class Finding:
    finding_id: str
    finding_type: str
    evidence_event_ids: Sequence[str]
    component_ids: Sequence[str]
    rule_or_model: str
    assumptions: Sequence[str]
    confidence: float | None
    message: str
    recommended_review: str | None = None

    def validate(self) -> None:
        if not self.finding_id.strip():
            raise ValueError("finding_id is required")
        if not self.finding_type.strip():
            raise ValueError("finding_type is required")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("finding confidence must be between 0 and 1")
        if not self.rule_or_model.strip():
            raise ValueError("rule_or_model is required")
        if not self.message.strip():
            raise ValueError("message is required")


class ObserverPort(Protocol):
    """Read-only observation interface.

    Implementations receive admitted events and return findings.
    They do not expose an operational execution method.
    """

    def observe(self, events: Sequence[EventEnvelope]) -> Sequence[Finding]:
        ...
