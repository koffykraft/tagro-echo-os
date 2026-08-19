from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class EntityRef:
    entity_type: str
    entity_id: str
    role: str | None = None

    def validate(self) -> None:
        if not self.entity_type.strip():
            raise ValueError("entity_type is required")
        if not self.entity_id.strip():
            raise ValueError("entity_id is required")


@dataclass(frozen=True)
class EvidenceRef:
    evidence_id: str
    evidence_type: str
    source: str
    confidence: float | None = None

    def validate(self) -> None:
        if not self.evidence_id.strip():
            raise ValueError("evidence_id is required")
        if not self.evidence_type.strip():
            raise ValueError("evidence_type is required")
        if not self.source.strip():
            raise ValueError("evidence source is required")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("evidence confidence must be between 0 and 1")


@dataclass(frozen=True)
class AuthorityContext:
    actor_id: str
    actor_type: str
    authority_scope: Sequence[str]
    authenticated: bool

    def validate(self) -> None:
        if not self.actor_id.strip():
            raise ValueError("actor_id is required")
        if not self.actor_type.strip():
            raise ValueError("actor_type is required")
        if not self.authenticated:
            raise ValueError("consequential events require authenticated authority")


@dataclass(frozen=True)
class EventEnvelope:
    event_id: str
    event_type: str
    schema_version: str
    event_time: datetime
    recorded_time: datetime
    source_effective_time: datetime | None
    location_id: str | None
    authority: AuthorityContext
    entities: Sequence[EntityRef]
    evidence: Sequence[EvidenceRef]
    provenance: Mapping[str, Any]
    confidence: float | None
    idempotency_key: str
    causal_event_ids: Sequence[str] = field(default_factory=tuple)
    supersedes_event_id: str | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.event_id.strip():
            raise ValueError("event_id is required")
        if not self.event_type.strip():
            raise ValueError("event_type is required")
        if not self.schema_version.strip():
            raise ValueError("schema_version is required")
        if not self.idempotency_key.strip():
            raise ValueError("idempotency_key is required")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("event confidence must be between 0 and 1")
        self.authority.validate()
        for entity in self.entities:
            entity.validate()
        for item in self.evidence:
            item.validate()
        if not isinstance(self.provenance, Mapping):
            raise ValueError("provenance must be a mapping")
        if not isinstance(self.payload, Mapping):
            raise ValueError("payload must be a mapping")

    @property
    def is_correction(self) -> bool:
        return self.supersedes_event_id is not None
