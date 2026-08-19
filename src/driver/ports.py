from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

from src.core.event import EventEnvelope


@dataclass(frozen=True)
class Command:
    command_id: str
    command_type: str
    idempotency_key: str
    actor_id: str
    authority_scope: Sequence[str]
    payload: Mapping[str, Any]

    def validate(self) -> None:
        if not self.command_id.strip():
            raise ValueError("command_id is required")
        if not self.command_type.strip():
            raise ValueError("command_type is required")
        if not self.idempotency_key.strip():
            raise ValueError("Driver commands require an idempotency_key")
        if not self.actor_id.strip():
            raise ValueError("actor_id is required")
        if any(not value.strip() for value in self.authority_scope):
            raise ValueError("authority_scope values must be non-empty")
        if not isinstance(self.payload, Mapping):
            raise ValueError("payload must be a mapping")


@dataclass(frozen=True)
class CommandResult:
    command_id: str
    accepted: bool
    status: str
    emitted_events: Sequence[EventEnvelope]
    reason: str | None = None


class DriverPort(Protocol):
    """Front-seat operational command boundary.

    Concrete business engines implement this protocol. They must validate
    authority, business rules and idempotency before emitting admitted events.
    """

    def execute(self, command: Command) -> CommandResult:
        ...
