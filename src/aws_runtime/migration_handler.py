from __future__ import annotations

from typing import Any, Mapping

from scripts.apply_schema_migrations import apply

CONFIRMATION = "APPLY_NONPROD_V0_1"


def lambda_handler(event: Mapping[str, Any], context: Any) -> dict[str, Any]:
    """Explicit one-time schema migration entry point.

    This function has no API/event source. It can only be invoked explicitly and
    refuses to mutate schema unless the caller supplies the exact confirmation
    token for the admitted NonProd v0.1 migration set.
    """
    if event.get("confirm") != CONFIRMATION:
        return {
            "status": "refused",
            "reason": "explicit_confirmation_required",
            "required_confirmation": CONFIRMATION,
        }

    apply()
    return {
        "status": "migration_complete",
        "migration_set": "nonprod_v0_1",
    }
