from __future__ import annotations

from typing import Any, Mapping

from scripts.apply_schema_migrations import apply

CONFIRMATION = "APPLY_NONPROD_V0_3"
START_AT = "0014-catalog-parts-lookup-v0.7"


def lambda_handler(event: Mapping[str, Any], context: Any) -> dict[str, Any]:
    """Explicit schema migration entry point for the WO-0014 catalog/runtime extension."""
    if event.get("confirm") != CONFIRMATION:
        return {
            "status": "refused",
            "reason": "explicit_confirmation_required",
            "required_confirmation": CONFIRMATION,
        }

    apply(start_at=START_AT)
    return {
        "status": "migration_complete",
        "migration_set": "nonprod_v0_3",
        "start_at": START_AT,
    }
