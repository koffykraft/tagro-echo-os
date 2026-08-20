from __future__ import annotations

import json
from typing import Any, Mapping

from src.aws_runtime.config import RuntimeConfig
from src.aws_runtime.database import probe


def _response(status_code: int, payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(payload, separators=(",", ":"), sort_keys=True),
    }


def _jwt_claims(event: Mapping[str, Any]) -> Mapping[str, Any]:
    try:
        claims = event["requestContext"]["authorizer"]["jwt"]["claims"]
    except (KeyError, TypeError):
        return {}
    return claims if isinstance(claims, Mapping) else {}


def lambda_handler(event: Mapping[str, Any], context: Any) -> dict[str, Any]:
    """Thin HTTP/Lambda boundary for ECHO OS.

    API Gateway is the primary JWT enforcement boundary. This handler also refuses
    protected routes when JWT claims are absent so a direct/incomplete integration
    cannot silently become authenticated application traffic.
    """
    config = RuntimeConfig.from_env()
    raw_path = str(event.get("rawPath") or "/")
    method = str(event.get("requestContext", {}).get("http", {}).get("method") or "GET").upper()

    if raw_path == "/health" and method == "GET":
        return _response(
            200,
            {
                "service": "tagro-echo-os",
                "environment": config.environment,
                "status": "ok",
                "database_configured": config.database_configured(),
            },
        )

    claims = _jwt_claims(event)
    if not claims:
        return _response(401, {"error": "authentication_required"})

    if raw_path == "/whoami" and method == "GET":
        return _response(
            200,
            {
                "subject": claims.get("sub"),
                "email": claims.get("email"),
                "username": claims.get("username") or claims.get("cognito:username"),
            },
        )

    if raw_path == "/db-health" and method == "GET":
        try:
            result = probe(config)
        except Exception as exc:
            return _response(
                503,
                {
                    "status": "database_unavailable",
                    "error_type": type(exc).__name__,
                },
            )
        return _response(200, {"status": "database_reachable", **result})

    return _response(404, {"error": "route_not_admitted"})
