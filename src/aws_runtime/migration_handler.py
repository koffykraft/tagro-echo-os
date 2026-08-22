from __future__ import annotations

from typing import Any, Mapping

from scripts.apply_schema_migrations import apply

CONFIRMATION = "APPLY_NONPROD_V0_3"


def lambda_handler(event: Mapping[str, Any], context: Any) -> dict[str, Any]:
    """Explicit schema migration entry point for the Operational Twin runtime."""
    if event.get("confirm") != CONFIRMATION:
        return {
            "status": "refused",
            "reason": "explicit_confirmation_required",
            "required_confirmation": CONFIRMATION,
        }

    apply()
    return {
        "status": "migration_complete",
        "migration_set": "nonprod_v0_3",
    }
