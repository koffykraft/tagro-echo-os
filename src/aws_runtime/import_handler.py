from __future__ import annotations

from typing import Any, Mapping

from src.aws_runtime.config import RuntimeConfig
from src.aws_runtime.twin_ingest_runtime import TwinIngestError, sync_source_records

CONFIRMATION = "SYNC_OPERATIONAL_TWIN_V1"
MAX_RECORDS = 1000


def lambda_handler(event: Mapping[str, Any], context: Any) -> dict[str, Any]:
    """Private ingestion boundary for the isolated ECHO Operational Twin.

    This function is intended to be invoked by the scheduled Dropbox/AWS data
    pipeline. Imported TAGRO/BUSY/Closing Cash/service/bank/history is persisted
    into PostgreSQL as primary ECHO working material with source provenance.
    It has no public HTTP event source.
    """
    if event.get("confirm") != CONFIRMATION:
        return {
            "status": "refused",
            "reason": "explicit_confirmation_required",
            "required_confirmation": CONFIRMATION,
        }

    enterprise_id = str(event.get("enterprise_id") or "").strip()
    package = event.get("package")
    if not enterprise_id or not isinstance(package, Mapping):
        return {"status": "refused", "reason": "enterprise_id_and_package_required"}

    records = package.get("records")
    if not isinstance(records, list) or not records:
        return {"status": "refused", "reason": "records_array_required"}
    if len(records) > MAX_RECORDS:
        return {"status": "refused", "reason": "record_limit_exceeded", "limit": MAX_RECORDS}

    required = ("source_system", "source_locator", "source_class", "sync_run_id")
    if any(not package.get(key) for key in required):
        return {"status": "refused", "reason": "source_metadata_required"}

    try:
        result = sync_source_records(
            RuntimeConfig.from_env(),
            enterprise_id=enterprise_id,
            source_system=str(package["source_system"]),
            source_locator=str(package["source_locator"]),
            source_class=str(package["source_class"]),
            source_as_of=str(package.get("source_as_of") or "") or None,
            records=records,
            sync_run_id=str(package["sync_run_id"]),
            provenance=package.get("provenance") if isinstance(package.get("provenance"), Mapping) else {},
        )
    except TwinIngestError as exc:
        return {"status": "refused", "reason": "invalid_operational_twin_package", "detail": str(exc)}

    return {"status": "operational_twin_sync_complete", "database_primary": True, **result}
