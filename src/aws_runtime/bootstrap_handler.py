from __future__ import annotations

from typing import Any, Mapping

from src.aws_runtime.bootstrap import bootstrap, validate_request
from src.aws_runtime.config import RuntimeConfig


def lambda_handler(event: Mapping[str, Any], context: Any) -> dict[str, Any]:
    """Private, explicit NonProd bootstrap entry point with no API/event source."""
    try:
        request = validate_request(event)
    except ValueError as exc:
        return {"status": "refused", "reason": str(exc)}

    try:
        return bootstrap(RuntimeConfig.from_env(), request)
    except Exception as exc:
        return {
            "status": "bootstrap_failed",
            "error_type": type(exc).__name__,
        }
