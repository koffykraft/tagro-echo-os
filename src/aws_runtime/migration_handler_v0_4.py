from __future__ import annotations

from typing import Any, Mapping

from scripts.apply_schema_migrations import apply

CONFIRMATION = "APPLY_NONPROD_V0_4"
START_AT = "0017-purchase-entry-v0.10"


def lambda_handler(event: Mapping[str, Any], context: Any) -> dict[str, Any]:
    """Explicit schema migration entry point for the WO-0017 purchase-entry extension.

    NOTE: this module is proposed alongside the migration SQL and the updated
    manifest -- it has not been wired into any Lambda function/alias by this
    change. Whatever CloudFormation/SAM (or equivalent) binds a Lambda function
    to schemas/migrations/nonprod_v0_3_manifest.json's existing migration_handler
    module needs a matching change to pick this one up instead, or to add it as
    a new function. That infra wiring was not visible from here and needs an
    ops/IaC review before this is relied on.
    """
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
