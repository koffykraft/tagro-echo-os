from __future__ import annotations

import json
from typing import Any, Mapping

from src.aws_runtime.billing_runtime import RuntimeBillingError, issue_bill
from src.aws_runtime.config import RuntimeConfig
from src.aws_runtime.database import probe, tenant_context
from src.aws_runtime.import_reconciliation import reconciliation_readback
from src.aws_runtime.operational_runtime import (
    OperationalRuntimeError,
    create_purchase_order,
    create_service_intake,
    record_stock_count,
)


def _response(status_code: int, payload: Mapping[str, Any]) -> dict[str, Any]:
    return {"statusCode": status_code, "headers": {"content-type": "application/json"}, "body": json.dumps(payload, separators=(",", ":"), sort_keys=True)}


def _jwt_claims(event: Mapping[str, Any]) -> Mapping[str, Any]:
    try:
        claims = event["requestContext"]["authorizer"]["jwt"]["claims"]
    except (KeyError, TypeError):
        return {}
    return claims if isinstance(claims, Mapping) else {}


def _json_body(event: Mapping[str, Any]) -> Mapping[str, Any] | None:
    raw = event.get("body")
    if isinstance(raw, Mapping):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, Mapping) else None


def _runtime_identity(config: RuntimeConfig, subject: str, payload: Mapping[str, Any]):
    context_result = tenant_context(config, subject)
    if not context_result or not context_result.get("enterprises"):
        return None, None, _response(403, {"error": "enterprise_membership_required"})
    requested = str(payload.get("enterprise_id") or "")
    memberships = list(context_result["enterprises"])
    if requested:
        memberships = [m for m in memberships if str(m.get("enterprise_id") or "") == requested]
    if len(memberships) != 1:
        return None, None, _response(409, {"error": "enterprise_selection_required"})
    return context_result, memberships[0], None


def _operational_post(config: RuntimeConfig, claims: Mapping[str, Any], event: Mapping[str, Any], *, capability: str, operation, schema: str):
    subject = str(claims.get("sub") or "")
    payload = _json_body(event)
    if not subject:
        return _response(401, {"error": "authenticated_subject_missing"})
    if payload is None:
        return _response(400, {"error": "invalid_json_body"})
    try:
        context_result, membership, error = _runtime_identity(config, subject, payload)
    except Exception as exc:
        return _response(503, {"error": "tenant_context_unavailable", "error_type": type(exc).__name__})
    if error:
        return error
    if capability not in {str(x).upper() for x in membership.get("capabilities") or []}:
        return _response(403, {"error": f"{capability.lower()}_capability_required"})
    try:
        result = operation(config, principal_id=str(context_result["principal_id"]), membership=membership, payload=payload)
    except PermissionError:
        return _response(403, {"error": f"{capability.lower()}_capability_required"})
    except OperationalRuntimeError as exc:
        return _response(409, {"error": "operation_rejected", "detail": str(exc)})
    except Exception as exc:
        return _response(503, {"error": "operational_runtime_unavailable", "error_type": type(exc).__name__})
    return _response(201, {"schema": schema, "data": result})


def lambda_handler(event: Mapping[str, Any], context: Any) -> dict[str, Any]:
    config = RuntimeConfig.from_env()
    raw_path = str(event.get("rawPath") or "/")
    method = str(event.get("requestContext", {}).get("http", {}).get("method") or "GET").upper()

    if raw_path == "/health" and method == "GET":
        return _response(200, {"service": "tagro-echo-os", "environment": config.environment, "status": "ok", "database_configured": config.database_configured()})

    claims = _jwt_claims(event)
    if not claims:
        return _response(401, {"error": "authentication_required"})

    if raw_path == "/whoami" and method == "GET":
        return _response(200, {"subject": claims.get("sub"), "email": claims.get("email"), "username": claims.get("username") or claims.get("cognito:username")})

    if raw_path == "/db-health" and method == "GET":
        try:
            result = probe(config)
        except Exception as exc:
            return _response(503, {"status": "database_unavailable", "error_type": type(exc).__name__})
        return _response(200, {"status": "database_reachable", **result})

    if raw_path == "/tenant-context" and method == "GET":
        subject = str(claims.get("sub") or "")
        if not subject:
            return _response(401, {"error": "authenticated_subject_missing"})
        try:
            result = tenant_context(config, subject)
        except Exception as exc:
            return _response(503, {"error": "tenant_context_unavailable", "error_type": type(exc).__name__})
        if not result:
            return _response(403, {"error": "enterprise_membership_required"})
        return _response(200, {"status": "tenant_context_resolved", **result})

    if raw_path == "/billing/issue" and method == "POST":
        subject = str(claims.get("sub") or "")
        payload = _json_body(event)
        if not subject:
            return _response(401, {"error": "authenticated_subject_missing"})
        if payload is None:
            return _response(400, {"error": "invalid_json_body"})
        try:
            context_result, membership, error = _runtime_identity(config, subject, payload)
        except Exception as exc:
            return _response(503, {"error": "tenant_context_unavailable", "error_type": type(exc).__name__})
        if error:
            return error
        if "SELL" not in {str(x).upper() for x in membership.get("capabilities") or []}:
            return _response(403, {"error": "sell_capability_required"})
        try:
            result = issue_bill(config, principal_id=str(context_result["principal_id"]), membership=membership, payload=payload)
        except PermissionError:
            return _response(403, {"error": "sell_capability_required"})
        except RuntimeBillingError as exc:
            return _response(409, {"error": "billing_rejected", "detail": str(exc)})
        except Exception as exc:
            return _response(503, {"error": "billing_runtime_unavailable", "error_type": type(exc).__name__})
        return _response(201, {"schema": "tagro.echo.bill-issued.v1", "data": result})

    if raw_path == "/service/intake" and method == "POST":
        return _operational_post(config, claims, event, capability="SERVICE", operation=create_service_intake, schema="tagro.echo.service-intake.v1")

    if raw_path == "/purchase-orders" and method == "POST":
        return _operational_post(config, claims, event, capability="PURCHASE_ORDER", operation=create_purchase_order, schema="tagro.echo.purchase-order.v1")

    if raw_path == "/stock-count/record" and method == "POST":
        return _operational_post(config, claims, event, capability="STOCK_COUNT", operation=record_stock_count, schema="tagro.echo.stock-count.v1")

    if raw_path == "/import-reconciliation" and method == "GET":
        subject = str(claims.get("sub") or "")
        if not subject:
            return _response(401, {"error": "authenticated_subject_missing"})
        try:
            context_result = tenant_context(config, subject)
        except Exception as exc:
            return _response(503, {"error": "tenant_context_unavailable", "error_type": type(exc).__name__})
        if not context_result or not context_result.get("enterprises"):
            return _response(403, {"error": "enterprise_membership_required"})
        owner_memberships = [m for m in context_result["enterprises"] if m.get("role_code") == "OWNER"]
        if not owner_memberships:
            return _response(403, {"error": "owner_authority_required"})
        if len(owner_memberships) != 1:
            return _response(409, {"error": "enterprise_selection_required"})
        try:
            result = reconciliation_readback(config, enterprise_id=str(owner_memberships[0]["enterprise_id"]))
        except Exception as exc:
            return _response(503, {"error": "reconciliation_unavailable", "error_type": type(exc).__name__})
        return _response(200, {"status": "reconciliation_readback", **result})

    return _response(404, {"error": "route_not_admitted"})
