from __future__ import annotations

from typing import Any, Mapping

from scripts.apply_schema_migrations import apply

CONFIRMATION = "APPLY_NONPROD_V0_4"
START_AT = "0017-purchase-entry-v0.10"


def lambda_handler(event: Mapping[str, Any], context: Any) -> dict[str, Any]:
    """Explicit, confirmation-gated migration for the WO-0017 purchase entry."""
    if event.get("confirm") != CONFIRMATION:
        return {
            "status": "refused",
            "reason": "explicit_confirmation_required",
            "required_confirmation": CONFIRMATION,
        }

    apply(start_at=START_AT)
    return {
        "status": "migration_complete",
        "migration_set": "nonprod_v0_4",
        "start_at": START_AT,
    }
