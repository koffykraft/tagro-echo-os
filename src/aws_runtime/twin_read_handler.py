from __future__ import annotations

import json
from typing import Any, Mapping

from .config import RuntimeConfig
from .database import tenant_context
from .twin_read_runtime import TwinReadError, history_search, source_status


def _response(status_code: int, payload: Mapping[str, Any]) -> dict[str, Any]:
    return {"statusCode": status_code, "headers": {"content-type": "application/json"}, "body": json.dumps(payload, separators=(",", ":"), sort_keys=True, default=str)}


def _claims(event: Mapping[str, Any]) -> Mapping[str, Any]:
    try:
        value = event["requestContext"]["authorizer"]["jwt"]["claims"]
    except (KeyError, TypeError):
        return {}
    return value if isinstance(value, Mapping) else {}


def _membership(config: RuntimeConfig, subject: str, enterprise_id: str):
    context = tenant_context(config, subject)
    if not context:
        return None
    rows = list(context.get("enterprises") or [])
    if enterprise_id:
        rows = [row for row in rows if str(row.get("enterprise_id") or "") == enterprise_id]
    return rows[0] if len(rows) == 1 else None


def lambda_handler(event: Mapping[str, Any], context: Any) -> dict[str, Any]:
    claims = _claims(event)
    subject = str(claims.get("sub") or "")
    if not subject:
        return _response(401, {"error": "authentication_required"})

    query = event.get("queryStringParameters") or {}
    if not isinstance(query, Mapping):
        query = {}
    enterprise_id = str(query.get("enterprise_id") or "")
    config = RuntimeConfig.from_env()
    try:
        membership = _membership(config, subject, enterprise_id)
    except Exception as exc:
        return _response(503, {"error": "tenant_context_unavailable", "error_type": type(exc).__name__})
    if not membership:
        return _response(409, {"error": "enterprise_selection_required"})
    enterprise_id = str(membership["enterprise_id"])

    raw_path = str(event.get("rawPath") or "/")
    method = str(event.get("requestContext", {}).get("http", {}).get("method") or "GET").upper()
    if method != "GET":
        return _response(405, {"error": "method_not_allowed"})

    try:
        if raw_path == "/twin-source-status":
            return _response(200, source_status(config, enterprise_id=enterprise_id))
        if raw_path == "/twin-history":
            return _response(200, history_search(
                config,
                enterprise_id=enterprise_id,
                domain=str(query.get("domain") or "") or None,
                branch_code=str(query.get("branch") or "") or None,
                record_type=str(query.get("record_type") or "") or None,
                event_type=str(query.get("event_type") or "") or None,
                start=str(query.get("start") or "") or None,
                end=str(query.get("end") or "") or None,
                query=str(query.get("q") or "") or None,
                limit=int(query.get("limit") or 100),
                cursor=int(query.get("cursor") or 0),
                mode=str(query.get("mode") or "planar"),
            ))
    except TwinReadError as exc:
        return _response(400, {"error": "invalid_twin_history_query", "detail": str(exc)})
    except Exception as exc:
        return _response(503, {"error": "operational_twin_read_unavailable", "error_type": type(exc).__name__})

    return _response(404, {"error": "route_not_admitted"})
