from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
from typing import Any, Mapping

from .config import RuntimeConfig
from .database import connect


class RuntimeBillingError(ValueError):
    pass


def _money(value: Any) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _stable_id(prefix: str, enterprise_id: str, idempotency_key: str) -> str:
    digest = sha256(f"{enterprise_id}|{idempotency_key}".encode()).hexdigest()[:24]
    return f"{prefix}-{digest}"


def _request_hash(payload: Mapping[str, Any]) -> str:
    stable = {
        "enterprise_id": payload.get("enterprise_id"),
        "branch_code": str(payload.get("branch_code") or "").upper(),
        "customer_id": payload.get("customer_id"),
        "customer_name": str(payload.get("customer_name") or "").strip(),
        "payment_mode": str(payload.get("payment_mode") or "").lower(),
        "owner_stock_override": bool(payload.get("owner_stock_override", False)),
        "stock_override_reason": str(payload.get("stock_override_reason") or "").strip(),
        "lines": payload.get("lines") or [],
    }
    return sha256(json.dumps(stable, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _stock_assessment(lines: list[dict[str, Any]], provisional_rows: list[tuple[Any, ...]]):
    """Assess only known provisional physical stock; absence remains UNKNOWN."""
    provisional: dict[str, dict[str, Any]] = {}
    for row in provisional_rows:
        product_id = str(row[0])
        provisional[product_id] = {
            "quantity": Decimal(str(row[1])),
            "source_observation_id": str(row[2]),
            "observed_at": row[3],
            "truth_state": str(row[4]),
        }
    shortages = [line for line in lines if line["product_id"] in provisional and provisional[line["product_id"]]["quantity"] < line["quantity"]]
    unknown = [line for line in lines if line["product_id"] not in provisional]
    return provisional, shortages, unknown


def issue_bill(
    config: RuntimeConfig,
    *,
    principal_id: str,
    membership: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Atomically admit one authenticated ECHO bill in NonProd.

    The authenticated principal and server-side membership determine authority.
    Client-supplied role/authority is ignored. Sale, stock movements and audit
    event are committed together. BUSY booking is never asserted here.
    """
    enterprise_id = str(membership.get("enterprise_id") or "")
    if not enterprise_id or str(payload.get("enterprise_id") or enterprise_id) != enterprise_id:
        raise RuntimeBillingError("enterprise selection does not match authenticated membership")
    capabilities = {str(x).upper() for x in membership.get("capabilities") or []}
    if "SELL" not in capabilities:
        raise PermissionError("SELL capability required")

    branch_code = str(payload.get("branch_code") or "").strip().upper()
    idempotency_key = str(payload.get("idempotency_key") or "").strip()
    lines = payload.get("lines")
    if not branch_code or not idempotency_key or not isinstance(lines, list) or not lines:
        raise RuntimeBillingError("branch_code, idempotency_key and lines are required")

    normalized: list[dict[str, Any]] = []
    taxable_total = Decimal("0")
    tax_total = Decimal("0")
    for index, raw in enumerate(lines, start=1):
        if not isinstance(raw, Mapping):
            raise RuntimeBillingError(f"line {index} must be an object")
        product_id = str(raw.get("product_id") or "").strip()
        quantity = Decimal(str(raw.get("quantity") or "0"))
        price = _money(raw.get("unit_price_before_tax") or 0)
        discount = _money(raw.get("discount_before_tax") or 0)
        gst_rate = Decimal(str(raw.get("gst_rate") or "0"))
        if not product_id or quantity <= 0 or price < 0 or discount < 0 or gst_rate < 0:
            raise RuntimeBillingError(f"line {index} is invalid")
        taxable = _money(quantity * price - discount)
        if taxable < 0:
            raise RuntimeBillingError(f"line {index} discount exceeds value")
        tax = _money(taxable * gst_rate / Decimal("100"))
        total = _money(taxable + tax)
        taxable_total += taxable
        tax_total += tax
        normalized.append({"product_id": product_id, "quantity": quantity, "unit_price": price, "discount": discount, "gst_rate": gst_rate, "line_total": total})

    taxable_total = _money(taxable_total)
    tax_total = _money(tax_total)
    invoice_total = _money(taxable_total + tax_total)
    sale_id = _stable_id("echo-sale", enterprise_id, idempotency_key)
    event_id = _stable_id("echo-event", enterprise_id, idempotency_key)
    request_hash = _request_hash({**payload, "enterprise_id": enterprise_id})
    now = datetime.now(timezone.utc)

    with connect(config) as connection:
        with connection.transaction():
            branch = connection.execute(
                "select branch_id from branches where enterprise_id=%s and code=%s and active=true",
                (enterprise_id, branch_code),
            ).fetchone()
            if not branch:
                raise RuntimeBillingError("active branch not found for enterprise")
            branch_id = str(branch[0])

            actor = connection.execute(
                "select user_id from users where enterprise_id=%s and principal_id=%s and active=true",
                (enterprise_id, principal_id),
            ).fetchone()
            if not actor:
                raise RuntimeBillingError("authenticated principal has no active ECHO user")

            existing = connection.execute(
                "select payload_json from echo_events where event_id=%s and enterprise_id=%s",
                (event_id, enterprise_id),
            ).fetchone()
            if existing:
                prior = json.loads(existing[0])
                if prior.get("request_hash") != request_hash:
                    raise RuntimeBillingError("idempotency key replayed with different billing payload")
                header = connection.execute(
                    "select total,payment_status,created_at from sale_headers where sale_id=%s and enterprise_id=%s",
                    (sale_id, enterprise_id),
                ).fetchone()
                if not header:
                    raise RuntimeError("billing audit event exists without sale header")
                return {
                    "bill_id": sale_id,
                    "invoice_total": str(header[0]),
                    "payment_status": header[1],
                    "created_at": header[2].isoformat(),
                    "stock_evidence_state": prior.get("stock_evidence_state", "unknown"),
                    "stock_unknown_count": int(prior.get("stock_unknown_count", 0)),
                    "busy_status": "not_booked_not_confirmed",
                    "busy_series": None,
                    "idempotent_replay": True,
                }

            product_ids = [row["product_id"] for row in normalized]
            rows = connection.execute(
                "select product_id,gst_rate from products where enterprise_id=%s and active=true and product_id = any(%s)",
                (enterprise_id, product_ids),
            ).fetchall()
            products = {str(pid): Decimal(str(gst)) for pid, gst in rows}
            if set(product_ids) != set(products):
                raise RuntimeBillingError("one or more products are not active enterprise products")
            for row in normalized:
                if row["gst_rate"] != products[row["product_id"]]:
                    raise RuntimeBillingError(f"GST rate mismatch for product {row['product_id']}")

            provisional_rows = connection.execute(
                "select product_id,quantity,source_observation_id,observed_at,truth_state from provisional_stock_position where enterprise_id=%s and branch_id=%s and product_id = any(%s)",
                (enterprise_id, branch_id, product_ids),
            ).fetchall()
            provisional, shortages, unknown_stock = _stock_assessment(normalized, provisional_rows)

            # Canonical movement-only position is retained as a comparison ray. During
            # count-led transition it is not promoted to physical opening-stock truth.
            canonical_rows = connection.execute(
                "select product_id,quantity from stock_position where enterprise_id=%s and branch_id=%s and product_id = any(%s)",
                (enterprise_id, branch_id, product_ids),
            ).fetchall()
            canonical_comparison = {str(pid): Decimal(str(qty)) for pid, qty in canonical_rows}

            override = bool(payload.get("owner_stock_override", False))
            reason = str(payload.get("stock_override_reason") or "").strip()
            if shortages:
                if str(membership.get("role_code") or "").upper() != "OWNER" or not override or not reason:
                    raise RuntimeBillingError("known provisional stock shortage; explicit owner override with reason required")

            customer_id = str(payload.get("customer_id") or "").strip() or None
            if customer_id:
                customer = connection.execute(
                    "select 1 from customers where enterprise_id=%s and customer_id=%s",
                    (enterprise_id, customer_id),
                ).fetchone()
                if not customer:
                    raise RuntimeBillingError("customer does not belong to enterprise")

            payment_mode = str(payload.get("payment_mode") or "").strip().lower()
            payment_status = "unpaid" if payment_mode == "credit" else "paid"
            connection.execute(
                "insert into sale_headers(sale_id,enterprise_id,branch_id,customer_id,created_at,payment_status,source_quote_id,total) values(%s,%s,%s,%s,%s,%s,null,%s)",
                (sale_id, enterprise_id, branch_id, customer_id, now, payment_status, invoice_total),
            )
            shortage_products = {row["product_id"] for row in shortages}
            unknown_products = {row["product_id"] for row in unknown_stock}
            for line_no, row in enumerate(normalized, start=1):
                connection.execute(
                    "insert into sale_lines(sale_id,line_no,product_id,quantity,unit_price,discount,gst_rate,line_total) values(%s,%s,%s,%s,%s,%s,%s,%s)",
                    (sale_id, line_no, row["product_id"], row["quantity"], row["unit_price"], row["discount"], row["gst_rate"], row["line_total"]),
                )
                movement_id = f"{sale_id}-stock-{line_no}"
                movement_note = reason if row["product_id"] in shortage_products else ("stock_evidence_unknown_at_sale" if row["product_id"] in unknown_products else "")
                connection.execute(
                    "insert into stock_movements(movement_id,enterprise_id,branch_id,product_id,quantity_delta,movement_type,occurred_at,reference_type,reference_id,note) values(%s,%s,%s,%s,%s,'sale',%s,'sale',%s,%s)",
                    (movement_id, enterprise_id, branch_id, row["product_id"], -row["quantity"], now, sale_id, movement_note),
                )

            if shortages:
                stock_evidence_state = "known_shortage_owner_override"
            elif unknown_stock:
                stock_evidence_state = "partial_or_full_unknown"
            else:
                stock_evidence_state = "provisional_known"

            stock_basis: dict[str, Any] = {}
            for row in normalized:
                pid = row["product_id"]
                if pid in provisional:
                    p = provisional[pid]
                    observed_at = p["observed_at"]
                    stock_basis[pid] = {
                        "state": "provisional",
                        "quantity_before_sale": str(p["quantity"]),
                        "source_observation_id": p["source_observation_id"],
                        "observed_at": observed_at.isoformat() if hasattr(observed_at, "isoformat") else str(observed_at),
                        "truth_state": p["truth_state"],
                        "canonical_movement_comparison": str(canonical_comparison[pid]) if pid in canonical_comparison else None,
                    }
                else:
                    stock_basis[pid] = {
                        "state": "unknown",
                        "quantity_before_sale": None,
                        "source_observation_id": None,
                        "canonical_movement_comparison": str(canonical_comparison[pid]) if pid in canonical_comparison else None,
                    }

            event_payload = {
                "schema": "tagro.echo.billing-admission.v1",
                "request_hash": request_hash,
                "idempotency_key": idempotency_key,
                "branch_code": branch_code,
                "payment_mode": payment_mode,
                "customer_name": str(payload.get("customer_name") or "").strip(),
                "invoice_total": str(invoice_total),
                "stock_exception": bool(shortages),
                "stock_exception_reason": reason if shortages else "",
                "stock_evidence_state": stock_evidence_state,
                "stock_unknown_count": len(unknown_stock),
                "stock_unknown_products": sorted(unknown_products),
                "stock_basis": stock_basis,
                "busy_status": "not_booked_not_confirmed",
            }
            connection.execute(
                "insert into echo_events(event_id,enterprise_id,event_type,subject_type,subject_id,occurred_at,recorded_at,actor_principal_id,location_ref,authority_basis,evidence_ref,provenance_ref,confidence,materiality_class,sensitivity_class,payload_json,admission_state) values(%s,%s,'sale.issued','sale',%s,%s,%s,%s,%s,%s,'','','1.0','A','internal',%s,'admitted')",
                (event_id, enterprise_id, sale_id, now, now, principal_id, branch_id, f"membership:{membership.get('membership_id','')};capability:SELL", json.dumps(event_payload, sort_keys=True, separators=(",", ":"))),
            )

    return {
        "bill_id": sale_id,
        "invoice_total": str(invoice_total),
        "payment_status": payment_status,
        "created_at": now.isoformat(),
        "stock_evidence_state": stock_evidence_state,
        "stock_unknown_count": len(unknown_stock),
        "busy_status": "not_booked_not_confirmed",
        "busy_series": None,
        "idempotent_replay": False,
    }
