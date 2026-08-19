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
