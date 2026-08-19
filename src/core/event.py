from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class ActorRef:
    actor_type: str
    actor_id: str

    def validate(self) -> None:
        if not self.actor_type.strip():
            raise ValueError("actor_type is required")
        if not self.actor_id.strip():
            raise ValueError("actor_id is required")

    def to_dict(self) -> dict[str, Any]:
        return {"actor_type": self.actor_type, "actor_id": self.actor_id}


@dataclass(frozen=True)
class LocationRef:
    location_type: str
    location_id: str

    def validate(self) -> None:
        if not self.location_type.strip():
            raise ValueError("location_type is required")
        if not self.location_id.strip():
            raise ValueError("location_id is required")

    def to_dict(self) -> dict[str, Any]:
        return {"location_type": self.location_type, "location_id": self.location_id}


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

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {"entity_type": self.entity_type, "entity_id": self.entity_id}
        if self.role is not None:
            value["role"] = self.role
        return value


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

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "evidence_id": self.evidence_id,
            "evidence_type": self.evidence_type,
            "source": self.source,
        }
        if self.confidence is not None:
            value["confidence"] = self.confidence
        return value


@dataclass(frozen=True)
class AuthorityContext:
    authority_scope: Sequence[str]
    authenticated: bool
    authority_source: str | None = None

    def validate(self) -> None:
        if not isinstance(self.authenticated, bool):
            raise ValueError("authenticated must be boolean")
        if any(not value.strip() for value in self.authority_scope):
            raise ValueError("authority_scope values must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "authority_scope": list(self.authority_scope),
            "authenticated": self.authenticated,
        }
        if self.authority_source is not None:
            value["authority_source"] = self.authority_source
        return value


@dataclass(frozen=True)
class ConfidenceContext:
    score: float | None
    status: str
    basis: str | None = None

    def validate(self) -> None:
        if self.score is not None and not 0.0 <= self.score <= 1.0:
            raise ValueError("confidence score must be between 0 and 1")
        if not self.status.strip():
            raise ValueError("confidence status is required")

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {"score": self.score, "status": self.status}
        if self.basis is not None:
            value["basis"] = self.basis
        return value


@dataclass(frozen=True)
class EventEnvelope:
    event_id: str
    event_type: str
    schema_version: str
    event_time: datetime
    recorded_time: datetime
    source_effective_time: datetime | None
    actor: ActorRef
    location: LocationRef
    authority: AuthorityContext
    entities: Sequence[EntityRef]
    evidence: Sequence[EvidenceRef]
    provenance: Mapping[str, Any]
    confidence: ConfidenceContext | None
    idempotency_key: str | None
    caused_by: Sequence[str] = field(default_factory=tuple)
    supersedes: Sequence[str] = field(default_factory=tuple)
    payload: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.event_id.strip():
            raise ValueError("event_id is required")
        if not self.event_type.strip():
            raise ValueError("event_type is required")
        if not self.schema_version.strip():
            raise ValueError("schema_version is required")
        if self.idempotency_key is not None and not self.idempotency_key.strip():
            raise ValueError("idempotency_key must be null or non-empty")
        self.actor.validate()
        self.location.validate()
        self.authority.validate()
        if self.confidence is not None:
            self.confidence.validate()
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
        return bool(self.supersedes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "schema_version": self.schema_version,
            "event_time": self.event_time.isoformat(),
            "recorded_time": self.recorded_time.isoformat(),
            "source_effective_time": self.source_effective_time.isoformat() if self.source_effective_time else None,
            "actor": self.actor.to_dict(),
            "location": self.location.to_dict(),
            "entities": [value.to_dict() for value in self.entities],
            "evidence": [value.to_dict() for value in self.evidence],
            "authority": self.authority.to_dict(),
            "provenance": dict(self.provenance),
            "confidence": self.confidence.to_dict() if self.confidence else None,
            "idempotency_key": self.idempotency_key,
            "caused_by": list(self.caused_by),
            "supersedes": list(self.supersedes),
            "payload": dict(self.payload),
        }
