from __future__ import annotations

from typing import Any, Mapping

from .billing_runtime import RuntimeBillingError, issue_bill as _issue_bill
from .config import RuntimeConfig
from .database import connect


def issue_bill(
    config: RuntimeConfig,
    *,
    principal_id: str,
    membership: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Guard canonical tax completeness, then delegate to the proven billing engine.

    Products may remain active and searchable while HSN/GST is incomplete. Billing,
    however, must never interpret unknown GST as 0%. This guard rejects only sale
    lines whose canonical GST is still unknown; it does not hide the product from
    Service, Stock, Purchase or reference lookup.
    """
    enterprise_id = str(membership.get("enterprise_id") or "")
    lines = payload.get("lines")
    if not enterprise_id or not isinstance(lines, list) or not lines:
        return _issue_bill(
            config,
            principal_id=principal_id,
            membership=membership,
            payload=payload,
        )

    product_ids = []
    for index, raw in enumerate(lines, start=1):
        if not isinstance(raw, Mapping):
            continue
        product_id = str(raw.get("product_id") or "").strip()
        if product_id:
            product_ids.append(product_id)

    if product_ids:
        with connect(config) as conn:
            rows = conn.execute(
                """
                select p.product_id,p.gst_rate,coalesce(pca.gst_known,false)
                from products p
                left join product_commercial_attributes pca on pca.product_id=p.product_id
                where p.enterprise_id=%s and p.active=true and p.product_id = any(%s)
                """,
                (enterprise_id, product_ids),
            ).fetchall()
        state = {str(pid): (gst, bool(known)) for pid, gst, known in rows}
        for product_id in product_ids:
            value = state.get(product_id)
            if value is None:
                continue  # The proven engine returns the canonical missing/inactive error.
            gst_rate, gst_known = value
            if gst_rate is None or not gst_known:
                raise RuntimeBillingError(f"GST incomplete for product {product_id}; populate canonical GST before billing")

    return _issue_bill(
        config,
        principal_id=principal_id,
        membership=membership,
        payload=payload,
    )
