from __future__ import annotations

from decimal import Decimal
from typing import Any

from .config import RuntimeConfig
from .database import connect


KINDS = {"branches", "products", "customers", "suppliers"}


class ReferenceRuntimeError(ValueError):
    pass


def _limit(value: Any) -> int:
    raw = 40 if value is None or value == "" else value
    try:
        n = int(raw)
    except (TypeError, ValueError) as exc:
        raise ReferenceRuntimeError("limit must be an integer") from exc
    if n < 1 or n > 100:
        raise ReferenceRuntimeError("limit must be between 1 and 100")
    return n


def _wire(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def reference_search(
    config: RuntimeConfig,
    *,
    enterprise_id: str,
    kind: str,
    query: str = "",
    limit: Any = 40,
    branch_code: str = "",
) -> dict[str, Any]:
    """Read enterprise-scoped operational reference data.

    Product lookup resolves canonical identity plus manufacturer/TAGRO/BUSY aliases.
    Missing HSN/GST remains visible as incomplete rather than being fabricated.
    """
    kind = str(kind or "").strip().lower()
    if kind not in KINDS:
        raise ReferenceRuntimeError("unsupported reference kind")
    n = _limit(limit)
    q = str(query or "").strip().lower()
    branch = str(branch_code or "").strip().upper()
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
                select p.product_id,p.sku,p.model,p.name,p.category,p.gst_rate,p.unit,p.serial_tracked,
                       coalesce(pca.hsn_code,''),coalesce(pca.manufacturer_part_no,''),
                       coalesce(pca.gst_known,false),approved.amount,approved.price_type,
                       approved.effective_from
                from products p
                left join product_commercial_attributes pca on pca.product_id=p.product_id
                left join lateral (
                  select pr.amount,pr.price_type,pr.effective_from
                  from prices pr
                  left join branches price_branch on price_branch.branch_id=pr.branch_id
                  where pr.enterprise_id=p.enterprise_id
                    and pr.product_id=p.product_id
                    and pr.price_type in ('tagro_approved_sale','approved_sale')
                    and pr.effective_from<=current_date
                    and (pr.effective_to is null or pr.effective_to>=current_date)
                    and (pr.branch_id is null or (%s<>'' and price_branch.code=%s))
                  order by case when pr.branch_id is null then 1 else 0 end,
                           pr.effective_from desc,pr.price_id desc
                  limit 1
                ) approved on true
                where p.enterprise_id=%s and p.active=true
                  and (
                    %s=''
                    or lower(p.sku) like %s
                    or lower(p.model) like %s
                    or lower(p.name) like %s
                    or lower(p.category) like %s
                    or lower(coalesce(pca.hsn_code,'')) like %s
                    or lower(coalesce(pca.manufacturer_part_no,'')) like %s
                    or exists (
                      select 1 from product_aliases pa
                      where pa.enterprise_id=p.enterprise_id and pa.product_id=p.product_id and pa.active=true
                        and (pa.branch_code='' or %s='' or pa.branch_code=%s)
                        and lower(pa.alias_value) like %s
                    )
                  )
                order by p.model,p.name limit %s
                """,
                (branch, branch, enterprise_id, q, pattern, pattern, pattern, pattern, pattern, pattern, branch, branch, pattern, n),
            ).fetchall()
            columns = (
                "product_id", "sku", "model", "name", "category", "gst_rate", "unit", "serial_tracked",
                "hsn_code", "manufacturer_part_no", "gst_known",
                "approved_price_before_tax", "approved_price_type", "approved_price_effective_from",
            )
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
