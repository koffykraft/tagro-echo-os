from __future__ import annotations

import json
from typing import Any, Mapping

from .config import RuntimeConfig
from .database import tenant_context
from .twin_planar_runtime import TwinPlanarError, history_readback, planar_status


def _response(status_code: int, payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(payload, separators=(",", ":"), sort_keys=True, default=str),
    }


def _claims(event: Mapping[str, Any]) -> Mapping[str, Any]:
    try:
        value = event["requestContext"]["authorizer"]["jwt"]["claims"]
    except (KeyError, TypeError):
        return {}
    return value if isinstance(value, Mapping) else {}


def _membership(config: RuntimeConfig, event: Mapping[str, Any]):
    claims = _claims(event)
    subject = str(claims.get("sub") or "")
    if not subject:
        return None, _response(401, {"error": "authentication_required"})
    try:
        context = tenant_context(config, subject)
    except Exception as exc:
        return None, _response(503, {"error": "tenant_context_unavailable", "error_type": type(exc).__name__})
    if not context or not context.get("enterprises"):
        return None, _response(403, {"error": "enterprise_membership_required"})
    query = event.get("queryStringParameters") or {}
    if not isinstance(query, Mapping):
        query = {}
    requested = str(query.get("enterprise_id") or "")
    memberships = list(context["enterprises"])
    if requested:
        memberships = [m for m in memberships if str(m.get("enterprise_id") or "") == requested]
    if len(memberships) != 1:
        return None, _response(409, {"error": "enterprise_selection_required"})
    membership = memberships[0]
    capabilities = {str(x).upper() for x in membership.get("capabilities") or []}
    if str(membership.get("role_code") or "").upper() != "OWNER" and "REPORTS" not in capabilities:
        return None, _response(403, {"error": "reports_capability_required"})
    return membership, None


def lambda_handler(event: Mapping[str, Any], context: Any) -> dict[str, Any]:
    config = RuntimeConfig.from_env()
    raw_path = str(event.get("rawPath") or "/")
    method = str(event.get("requestContext", {}).get("http", {}).get("method") or "GET").upper()
    if method != "GET":
        return _response(405, {"error": "method_not_allowed"})

    membership, error = _membership(config, event)
    if error:
        return error
    enterprise_id = str(membership["enterprise_id"])
    query = event.get("queryStringParameters") or {}
    if not isinstance(query, Mapping):
        query = {}

    try:
        if raw_path == "/planar-status":
            return _response(200, planar_status(config, enterprise_id=enterprise_id))
        if raw_path == "/history":
            return _response(
                200,
                history_readback(
                    config,
                    enterprise_id=enterprise_id,
                    branch=str(query.get("branch") or "") or None,
                    event_type=str(query.get("event_type") or "") or None,
                    start=str(query.get("start") or "") or None,
                    end=str(query.get("end") or "") or None,
                    query=str(query.get("q") or "") or None,
                    limit=query.get("limit") or 50,
                    cursor=query.get("cursor") or 0,
                ),
            )
    except TwinPlanarError as exc:
        return _response(400, {"error": "invalid_history_query", "detail": str(exc)})
    except Exception as exc:
        return _response(503, {"error": "history_runtime_unavailable", "error_type": type(exc).__name__})

    return _response(404, {"error": "route_not_admitted"})
