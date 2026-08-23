from __future__ import annotations

from typing import Any, Mapping

from src.aws_runtime.canonical_master_runtime import CanonicalMasterError, sync_canonical_master
from src.aws_runtime.config import RuntimeConfig
from src.aws_runtime.twin_ingest_runtime import TwinIngestError, sync_source_records
from src.aws_runtime.twin_planar_runtime import TwinPlanarError, sync_planar_records

CONFIRMATION = "SYNC_OPERATIONAL_TWIN_V1"
MAX_RECORDS = 1000


def lambda_handler(event: Mapping[str, Any], context: Any) -> dict[str, Any]:
    """Private ingestion boundary for the isolated ECHO Operational Twin.

    Scheduled Dropbox/AWS source pipelines invoke this Lambda. Generic source
    packages remain available for audit/intake. Explicit canonical-master packages
    admit reviewed reference data into operational products/prices/catalogue tables.
    Planar packages remain a separate higher projection plane.
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

    kwargs = dict(
        config=RuntimeConfig.from_env(),
        enterprise_id=enterprise_id,
        source_system=str(package["source_system"]),
        source_locator=str(package["source_locator"]),
        source_class=str(package["source_class"]),
        source_as_of=str(package.get("source_as_of") or "") or None,
        records=records,
        sync_run_id=str(package["sync_run_id"]),
        provenance=package.get("provenance") if isinstance(package.get("provenance"), Mapping) else {},
    )

    schema = str(package.get("schema") or "").lower()
    try:
        if schema in {"tagro.planar-export/1", "tagro.echo.planar-export/1"}:
            result = sync_planar_records(**kwargs)
            return {
                **result,
                "status": "operational_twin_planar_sync_complete",
                "database_primary": True,
                "planar_preserved": True,
            }
        if schema == "tagro.echo.canonical-master/1":
            result = sync_canonical_master(**kwargs)
            return {
                **result,
                "status": "canonical_master_sync_complete",
                "database_primary": True,
                "planar_projection": False,
            }
        result = sync_source_records(**kwargs)
    except CanonicalMasterError as exc:
        return {"status": "refused", "reason": "invalid_canonical_master_package", "detail": str(exc)}
    except (TwinIngestError, TwinPlanarError) as exc:
        return {"status": "refused", "reason": "invalid_operational_twin_package", "detail": str(exc)}

    return {
        **result,
        "status": "operational_twin_sync_complete",
        "database_primary": True,
    }
