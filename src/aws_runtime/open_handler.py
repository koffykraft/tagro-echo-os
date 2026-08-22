from __future__ import annotations

import json
from typing import Any, Mapping

from src.aws_runtime.billing_runtime import RuntimeBillingError, issue_bill
from src.aws_runtime.cash_document_runtime import CashDocumentRuntimeError, save_cash_document
from src.aws_runtime.cash_runtime import CashRuntimeError, cash_day_readback, open_cash_day, record_cash_entry, submit_cash_day
from src.aws_runtime.config import RuntimeConfig
from src.aws_runtime.database import connect, probe
from src.aws_runtime.import_reconciliation import reconciliation_readback
from src.aws_runtime.on_call_runtime import OnCallRuntimeError, owner_on_call_readback
from src.aws_runtime.operational_runtime import OperationalRuntimeError, create_purchase_order, create_service_intake, record_stock_count
from src.aws_runtime.reference_runtime import ReferenceRuntimeError, reference_search
from src.aws_runtime.twin_read_runtime import TwinReadError, history_search, source_status

ENTERPRISE_CODE = "TAGRO"


def _response(status_code: int, payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"content-type": "application/json", "cache-control": "no-store"},
        "body": json.dumps(payload, separators=(",", ":"), sort_keys=True, default=str),
    }


def _json_body(event: Mapping[str, Any]) -> dict[str, Any] | None:
    raw = event.get("body")
    if isinstance(raw, Mapping):
        return dict(raw)
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return dict(value) if isinstance(value, Mapping) else None


def _query(event: Mapping[str, Any]) -> Mapping[str, Any]:
    value = event.get("queryStringParameters") or {}
    return value if isinstance(value, Mapping) else {}


def _headers(event: Mapping[str, Any]) -> Mapping[str, Any]:
    value = event.get("headers") or {}
    return value if isinstance(value, Mapping) else {}


def _open_context(config: RuntimeConfig) -> dict[str, Any]:
    """Resolve the real TAGRO enterprise and a durable server-side audit actor.

    Access is intentionally open for the internal operating deployment. The selected
    owner principal is used only as the database actor required by existing engines;
    it is not an authentication decision.
    """
    with connect(config) as conn:
        row = conn.execute(
            """
            select p.principal_id, p.display_name, m.membership_id,
                   e.enterprise_id, e.code, e.name, m.role_code, m.tool_pack_code
            from enterprise_memberships m
            join enterprises e on e.enterprise_id=m.enterprise_id
            join principals p on p.principal_id=m.principal_id
            where e.code=%s
              and e.status='active'
              and p.active=true
              and m.status='active'
              and m.role_code='OWNER'
              and m.valid_from <= now()
              and (m.valid_to is null or m.valid_to > now())
              and exists (
                  select 1 from users u
                  where u.enterprise_id=e.enterprise_id
                    and u.principal_id=p.principal_id
                    and u.active=true
              )
            order by p.principal_id
            limit 1
            """,
            (ENTERPRISE_CODE,),
        ).fetchone()
        if not row:
            raise RuntimeError("TAGRO active owner runtime actor not found")
        principal_id, display_name, membership_id, enterprise_id, code, name, role_code, tool_pack_code = row
        entitlements = conn.execute(
            """
            select capability_code
            from enterprise_entitlements
            where enterprise_id=%s
              and status='enabled'
              and effective_from <= now()
              and (effective_to is null or effective_to > now())
            order by capability_code
            """,
            (enterprise_id,),
        ).fetchall()
    membership = {
        "membership_id": membership_id,
        "enterprise_id": enterprise_id,
        "enterprise_code": code,
        "enterprise_name": name,
        "role_code": role_code,
        "tool_pack_code": tool_pack_code,
        "capabilities": [r[0] for r in entitlements],
    }
    return {"principal_id": principal_id, "display_name": display_name, "enterprises": [membership]}


def _resolve_branch(config: RuntimeConfig, raw: Any) -> str | None:
    token = str(raw or "").strip().upper()
    if not token:
        return None
    with connect(config) as conn:
        exact = conn.execute(
            "select code from branches where enterprise_id=(select enterprise_id from enterprises where code=%s and status='active') and active=true and upper(code)=%s",
            (ENTERPRISE_CODE, token),
        ).fetchone()
        if exact:
            return str(exact[0]).upper()
        if len(token) == 1:
            rows = conn.execute(
                """
                select code
                from branches
                where enterprise_id=(select enterprise_id from enterprises where code=%s and status='active')
                  and active=true
                  and (upper(code) like %s or upper(name) like %s)
                order by code
                """,
                (ENTERPRISE_CODE, token + "%", token + "%"),
            ).fetchall()
            unique = list(dict.fromkeys(str(r[0]).upper() for r in rows))
            if len(unique) == 1:
                return unique[0]
            if len(unique) > 1:
                raise OperationalRuntimeError(f"branch alpha {token} is ambiguous; use the branch code")
    raise OperationalRuntimeError(f"active branch not found for {token}")


def _requested_branch(event: Mapping[str, Any], payload: Mapping[str, Any] | None = None) -> str | None:
    if payload and payload.get("branch_code"):
        return str(payload.get("branch_code"))
    q = _query(event)
    if q.get("branch"):
        return str(q.get("branch"))
    for key, value in _headers(event).items():
        if str(key).lower() == "x-tagro-branch" and value:
            return str(value)
    return None


def _prepare_payload(config: RuntimeConfig, event: Mapping[str, Any]) -> dict[str, Any] | None:
    payload = _json_body(event)
    if payload is None:
        return None
    raw_branch = _requested_branch(event, payload)
    if raw_branch:
        payload["branch_code"] = _resolve_branch(config, raw_branch)
    return payload


def _membership(context_result: Mapping[str, Any]) -> Mapping[str, Any]:
    return list(context_result["enterprises"])[0]


def _operational_post(config: RuntimeConfig, event: Mapping[str, Any], *, capability: str, operation, schema: str):
    payload = _prepare_payload(config, event)
    if payload is None:
        return _response(400, {"error": "invalid_json_body"})
    try:
        ctx = _open_context(config)
        membership = _membership(ctx)
        if capability not in {str(x).upper() for x in membership.get("capabilities") or []}:
            return _response(409, {"error": f"{capability.lower()}_capability_not_enabled"})
        result = operation(config, principal_id=str(ctx["principal_id"]), membership=membership, payload=payload)
    except (OperationalRuntimeError, CashRuntimeError, CashDocumentRuntimeError) as exc:
        return _response(409, {"error": "operation_rejected", "detail": str(exc)})
    except PermissionError as exc:
        return _response(409, {"error": "enterprise_capability_not_enabled", "detail": str(exc)})
    except Exception as exc:
        return _response(503, {"error": "operational_runtime_unavailable", "error_type": type(exc).__name__})
    return _response(201, {"schema": schema, "data": result})


def lambda_handler(event: Mapping[str, Any], context: Any) -> dict[str, Any]:
    config = RuntimeConfig.from_env()
    raw_path = str(event.get("rawPath") or "/")
    method = str(event.get("requestContext", {}).get("http", {}).get("method") or "GET").upper()
    query = _query(event)

    if raw_path == "/health" and method == "GET":
        return _response(200, {"service": "tagro-echo-os", "environment": config.environment, "status": "ok", "access": "open_internal", "database_configured": config.database_configured()})

    try:
        ctx = _open_context(config)
        membership = _membership(ctx)
    except Exception as exc:
        return _response(503, {"error": "tagro_runtime_context_unavailable", "error_type": type(exc).__name__})
    enterprise_id = str(membership["enterprise_id"])

    if raw_path == "/whoami" and method == "GET":
        branch = None
        requested = _requested_branch(event)
        if requested:
            try:
                branch = _resolve_branch(config, requested)
            except OperationalRuntimeError as exc:
                return _response(409, {"error": "branch_selection_required", "detail": str(exc)})
        return _response(200, {
            "access": "open_internal",
            "enterprise_code": membership["enterprise_code"],
            "enterprise_name": membership["enterprise_name"],
            "branch_code": branch,
            "actor": ctx["display_name"],
        })

    if raw_path == "/db-health" and method == "GET":
        try:
            return _response(200, {"status": "database_reachable", **probe(config)})
        except Exception as exc:
            return _response(503, {"status": "database_unavailable", "error_type": type(exc).__name__})

    if raw_path == "/tenant-context" and method == "GET":
        return _response(200, {"status": "tenant_context_resolved", "access": "open_internal", **ctx})

    if raw_path == "/reference-data" and method == "GET":
        try:
            result = reference_search(config, enterprise_id=enterprise_id, kind=str(query.get("kind") or ""), query=str(query.get("q") or ""), limit=query.get("limit") or 40)
        except ReferenceRuntimeError as exc:
            return _response(400, {"error": "invalid_reference_query", "detail": str(exc)})
        except Exception as exc:
            return _response(503, {"error": "reference_data_unavailable", "error_type": type(exc).__name__})
        return _response(200, result)

    if raw_path == "/owner-on-call" and method == "GET":
        try:
            branch = _resolve_branch(config, query.get("branch")) if query.get("branch") else None
            payload = owner_on_call_readback(config, enterprise_id=enterprise_id, start=str(query.get("start") or "") or None, end=str(query.get("end") or "") or None, branch=branch)
        except (OnCallRuntimeError, OperationalRuntimeError) as exc:
            return _response(400, {"error": "invalid_on_call_query", "detail": str(exc)})
        except Exception as exc:
            return _response(503, {"error": "owner_on_call_unavailable", "error_type": type(exc).__name__})
        return _response(200, payload)

    if raw_path == "/cash-days" and method == "GET":
        try:
            branch = _resolve_branch(config, query.get("branch")) if query.get("branch") else None
            result = cash_day_readback(config, enterprise_id=enterprise_id, branch_code=branch, business_date=str(query.get("business_date") or "") or None, limit=query.get("limit") or 14)
        except (CashRuntimeError, OperationalRuntimeError) as exc:
            return _response(400, {"error": "invalid_cash_query", "detail": str(exc)})
        except Exception as exc:
            return _response(503, {"error": "cash_runtime_unavailable", "error_type": type(exc).__name__})
        return _response(200, {"schema": "tagro.echo.cash-day-readback.v1", "data": result})

    if raw_path == "/billing/issue" and method == "POST":
        payload = _prepare_payload(config, event)
        if payload is None:
            return _response(400, {"error": "invalid_json_body"})
        try:
            result = issue_bill(config, principal_id=str(ctx["principal_id"]), membership=membership, payload=payload)
        except RuntimeBillingError as exc:
            return _response(409, {"error": "billing_rejected", "detail": str(exc)})
        except PermissionError as exc:
            return _response(409, {"error": "sell_capability_not_enabled", "detail": str(exc)})
        except Exception as exc:
            return _response(503, {"error": "billing_runtime_unavailable", "error_type": type(exc).__name__})
        return _response(201, {"schema": "tagro.echo.bill-issued.v1", "data": result})

    if raw_path == "/cash-days/open" and method == "POST":
        return _operational_post(config, event, capability="CASH", operation=open_cash_day, schema="tagro.echo.cash-day-opened.v1")
    if raw_path == "/cash-days/entries" and method == "POST":
        return _operational_post(config, event, capability="CASH", operation=record_cash_entry, schema="tagro.echo.cash-entry-recorded.v1")
    if raw_path == "/cash-days/submit" and method == "POST":
        return _operational_post(config, event, capability="CASH", operation=submit_cash_day, schema="tagro.echo.cash-day-submitted.v1")
    if raw_path == "/cash-days/save" and method == "POST":
        return _operational_post(config, event, capability="CASH", operation=save_cash_document, schema="tagro.echo.cash-document-saved.v1")
    if raw_path == "/service/intake" and method == "POST":
        return _operational_post(config, event, capability="SERVICE", operation=create_service_intake, schema="tagro.echo.service-intake.v1")
    if raw_path == "/purchase-orders" and method == "POST":
        return _operational_post(config, event, capability="PURCHASE", operation=create_purchase_order, schema="tagro.echo.purchase-order.v1")
    if raw_path == "/stock-count/record" and method == "POST":
        return _operational_post(config, event, capability="STOCK", operation=record_stock_count, schema="tagro.echo.stock-count.v1")

    if raw_path == "/import-reconciliation" and method == "GET":
        try:
            result = reconciliation_readback(config, enterprise_id=enterprise_id)
        except Exception as exc:
            return _response(503, {"error": "reconciliation_unavailable", "error_type": type(exc).__name__})
        return _response(200, {"status": "reconciliation_readback", **result})

    if raw_path == "/twin-source-status" and method == "GET":
        try:
            return _response(200, source_status(config, enterprise_id=enterprise_id))
        except Exception as exc:
            return _response(503, {"error": "operational_twin_read_unavailable", "error_type": type(exc).__name__})

    if raw_path == "/twin-history" and method == "GET":
        try:
            branch = _resolve_branch(config, query.get("branch")) if query.get("branch") else None
            return _response(200, history_search(config, enterprise_id=enterprise_id, domain=str(query.get("domain") or "") or None, branch_code=branch, record_type=str(query.get("record_type") or "") or None, event_type=str(query.get("event_type") or "") or None, start=str(query.get("start") or "") or None, end=str(query.get("end") or "") or None, query=str(query.get("q") or "") or None, limit=int(query.get("limit") or 100), cursor=int(query.get("cursor") or 0), mode=str(query.get("mode") or "planar")))
        except (TwinReadError, OperationalRuntimeError) as exc:
            return _response(400, {"error": "invalid_twin_history_query", "detail": str(exc)})
        except Exception as exc:
            return _response(503, {"error": "operational_twin_read_unavailable", "error_type": type(exc).__name__})

    return _response(404, {"error": "route_not_admitted"})
