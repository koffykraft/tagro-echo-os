from __future__ import annotations

from decimal import Decimal, InvalidOperation
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

    if product_ids and str(membership.get("role_code") or "").upper() != "OWNER":
        branch_code = str(payload.get("branch_code") or "").strip().upper()
        with connect(config) as conn:
            rows = conn.execute(
                """
                select p.product_id,approved.amount
                from products p
                left join lateral (
                  select pr.amount
                  from prices pr
                  left join branches price_branch on price_branch.branch_id=pr.branch_id
                  where pr.enterprise_id=p.enterprise_id
                    and pr.product_id=p.product_id
                    and pr.price_type in ('tagro_approved_sale','approved_sale')
                    and pr.effective_from<=current_date
                    and (pr.effective_to is null or pr.effective_to>=current_date)
                    and (pr.branch_id is null or price_branch.code=%s)
                  order by case when pr.branch_id is null then 1 else 0 end,
                           pr.effective_from desc,pr.price_id desc
                  limit 1
                ) approved on true
                where p.enterprise_id=%s and p.active=true and p.product_id=any(%s)
                """,
                (branch_code, enterprise_id, product_ids),
            ).fetchall()
        approved_prices = {str(product_id): amount for product_id, amount in rows}
        for raw in lines:
            if not isinstance(raw, Mapping):
                continue
            product_id = str(raw.get("product_id") or "").strip()
            approved = approved_prices.get(product_id)
            if approved is None:
                raise RuntimeBillingError(f"Approved selling price unavailable for product {product_id}; owner approval required")
            try:
                submitted = Decimal(str(raw.get("unit_price_before_tax"))).quantize(Decimal("0.01"))
                expected = Decimal(str(approved)).quantize(Decimal("0.01"))
            except (InvalidOperation, TypeError, ValueError) as exc:
                raise RuntimeBillingError(f"Invalid selling price for product {product_id}") from exc
            if submitted != expected:
                raise RuntimeBillingError(f"Selling price differs from the approved TAGRO price for product {product_id}")
            try:
                discount = Decimal(str(raw.get("discount_before_tax") or "0"))
            except (InvalidOperation, TypeError, ValueError) as exc:
                raise RuntimeBillingError(f"Invalid discount for product {product_id}") from exc
            if discount != 0:
                raise RuntimeBillingError(f"Staff discount requires owner approval for product {product_id}")

    return _issue_bill(
        config,
        principal_id=principal_id,
        membership=membership,
        payload=payload,
    )
