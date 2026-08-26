from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Mapping


OWNER_ON_CALL_SCHEMA = "tagro.echo.owner-on-call.v1"


def _wire(value: Any) -> Any:
    """Convert financial projection values to deterministic JSON-safe values.

    Money remains textual decimal data rather than binary floating point. Dates
    and timestamps are ISO-8601. Dataclasses are expanded recursively. This is a
    presentation boundary only; it does not add, classify, or mutate evidence.
    """
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _wire(asdict(value))
    if isinstance(value, Mapping):
        return {str(k): _wire(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_wire(v) for v in value]
    return value


def owner_on_call_payload(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Wrap an OwnerOnCall snapshot in the stable read-only API contract."""
    payload = _wire(snapshot)
    if not isinstance(payload, dict):
        raise TypeError("owner on-call snapshot must be a mapping")
    return {
        "schema": OWNER_ON_CALL_SCHEMA,
        "projection_status": "not_accounting_final",
        "data": payload,
    }
