from __future__ import annotations

from typing import Any, Mapping

from src.aws_runtime.config import RuntimeConfig
from src.aws_runtime.import_reconciliation import record_observations

CONFIRMATION = "IMPORT_NONPROD_OBSERVATIONS_V0_1"
MAX_OBSERVATIONS = 500


def lambda_handler(event: Mapping[str, Any], context: Any) -> dict[str, Any]:
    """Explicit private ingestion boundary for governed NonProd observations.

    This Lambda has no API/event source. It only records source evidence in
    import_sources/import_observations and cannot admit canonical business state.
    """
    if event.get("confirm") != CONFIRMATION:
        return {
            "status": "refused",
            "reason": "explicit_confirmation_required",
            "required_confirmation": CONFIRMATION,
        }

    enterprise_id = str(event.get("enterprise_id") or "")
    package = event.get("package")
    if not enterprise_id or not isinstance(package, Mapping):
        return {"status": "refused", "reason": "enterprise_id_and_package_required"}

    observations = package.get("observations")
    if not isinstance(observations, list):
        return {"status": "refused", "reason": "observations_array_required"}
    if not observations:
        return {"status": "refused", "reason": "empty_observation_package"}
    if len(observations) > MAX_OBSERVATIONS:
        return {
            "status": "refused",
            "reason": "observation_limit_exceeded",
            "limit": MAX_OBSERVATIONS,
        }

    required = ("source_system", "source_locator", "source_class")
    if any(not package.get(key) for key in required):
        return {"status": "refused", "reason": "source_metadata_required"}

    config = RuntimeConfig.from_env()
    result = record_observations(
        config,
        enterprise_id=enterprise_id,
        source_system=str(package["source_system"]),
        source_locator=str(package["source_locator"]),
        source_class=str(package["source_class"]),
        source_as_of=str(package.get("source_as_of") or "") or None,
        immutable_ref=str(package.get("immutable_ref") or ""),
        observations=observations,
    )
    return {
        "status": "observation_import_complete",
        "canonical_write": False,
        **result,
    }
