from __future__ import annotations

from decimal import Decimal
from typing import Any

from .config import RuntimeConfig
from .database import connect


KINDS = {"branches", "products", "customers", "suppliers"}


class ReferenceRuntimeError(ValueError):
    pass


def _limit(value: Any) -> int:
    try:
        n = int(value or 40)
    except (TypeError, ValueError) as exc:
        raise ReferenceRuntimeError("limit must be an integer") from exc
    if n < 1 or n > 100:
        raise ReferenceRuntimeError("limit must be between 1 and 100")
    return n


def _wire(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    return value


def reference_search(
    config: RuntimeConfig,
    *,
    enterprise_id: str,
    kind: str,
    query: str = "",
    limit: Any = 40,
) -> dict[str, Any]:
    """Read enterprise-scoped operational reference data.

    This endpoint is intentionally read-only and bounded. Membership resolution is
    performed by the HTTP boundary before this function is called; no client value
    may broaden enterprise scope.
    """
    kind = str(kind or "").strip().lower()
    if kind not in KINDS:
        raise ReferenceRuntimeError("unsupported reference kind")
    n = _limit(limit)
    q = str(query or "").strip().lower()
    pattern = f"%{q}%"

    with connect(config) as conn:
        if kind == "branches":
            rows = conn.execute(
                """
                select branch_id,code,name,district,branch_type
                from branches
                where enterprise_id=%s and active=true
                  and (%s='' or lower(code) like %s or lower(name) like %s or lower(district) like %s)
                order by code limit %s
                """,
                (enterprise_id, q, pattern, pattern, pattern, n),
            ).fetchall()
            columns = ("branch_id", "code", "name", "district", "branch_type")
        elif kind == "products":
            rows = conn.execute(
                """
                select product_id,sku,model,name,category,gst_rate,unit,serial_tracked
                from products
                where enterprise_id=%s and active=true
                  and (%s='' or lower(sku) like %s or lower(model) like %s or lower(name) like %s or lower(category) like %s)
                order by model,name limit %s
                """,
                (enterprise_id, q, pattern, pattern, pattern, pattern, n),
            ).fetchall()
            columns = ("product_id", "sku", "model", "name", "category", "gst_rate", "unit", "serial_tracked")
        elif kind == "customers":
            rows = conn.execute(
                """
                select customer_id,name,phone,email,gstin,district
                from customers
                where enterprise_id=%s
                  and (%s='' or lower(name) like %s or lower(phone) like %s or lower(gstin) like %s or lower(district) like %s)
                order by name limit %s
                """,
                (enterprise_id, q, pattern, pattern, pattern, pattern, n),
            ).fetchall()
            columns = ("customer_id", "name", "phone", "email", "gstin", "district")
        else:
            rows = conn.execute(
                """
                select supplier_id,name,phone,email,gstin
                from suppliers
                where enterprise_id=%s
                  and (%s='' or lower(name) like %s or lower(phone) like %s or lower(gstin) like %s)
                order by name limit %s
                """,
                (enterprise_id, q, pattern, pattern, pattern, n),
            ).fetchall()
            columns = ("supplier_id", "name", "phone", "email", "gstin")

    return {
        "schema": "tagro.echo.reference-data.v1",
        "kind": kind,
        "query": query,
        "limit": n,
        "count": len(rows),
        "items": [{column: _wire(value) for column, value in zip(columns, row)} for row in rows],
        "source": "echo_postgres_enterprise_scope",
        "read_only": True,
    }
