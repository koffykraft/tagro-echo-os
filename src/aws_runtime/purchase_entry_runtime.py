from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Any, Mapping

from .config import RuntimeConfig
from .database import connect

class PurchaseEntryRuntimeError(ValueError):
    pass


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _decimal(value: Any, field: str, *, allow_zero: bool = True) -> Decimal:
    try:
        d = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PurchaseEntryRuntimeError(f"{field} must be numeric") from exc
    if d < 0 or (d == 0 and not allow_zero):
        raise PurchaseEntryRuntimeError(f"{field} must be positive")
    return d


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def _stable_id(enterprise_id: str, key: str) -> str:
    return f"echo-pe-{sha256(f'{enterprise_id}|{key}'.encode()).hexdigest()[:24]}"


def _tax_mode(supplier_gstin: str, buyer_state_code: str) -> str:
    gstin = supplier_gstin.strip().upper()
    buyer = buyer_state_code.strip()
    if len(gstin) != 15 or not gstin[:2].isdigit():
        raise PurchaseEntryRuntimeError("supplier GSTIN is required and must identify its state")
    if len(buyer) != 2 or not buyer.isdigit():
        raise PurchaseEntryRuntimeError("branch GST state is not configured; purchase needs review")
    return "inter" if gstin[:2] != buyer else "intra"


def _branch_allowed(role_code: str, user_branch_id: str | None, selected_branch_id: str) -> bool:
    return role_code.strip().upper() == "OWNER" or bool(user_branch_id and user_branch_id == selected_branch_id)


def _parse_date(value: Any) -> date | None:
    text = _clean(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise PurchaseEntryRuntimeError("invoice_date must be an ISO date (YYYY-MM-DD)") from exc


def save_purchase_entry(
    config: RuntimeConfig,
    *,
    principal_id: str,
    membership: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Create or update a purchase entry (a recorded supplier invoice / goods receipt).

    status='draft' can be edited further by resubmitting with the same entry_id;
    status='recorded' is the final state -- once recorded, an entry_id is no longer
    accepted for further edits through this operation.
    """
    caps = {str(x).upper() for x in membership.get("capabilities") or []}
    if "PURCHASE" not in caps:
        raise PermissionError("PURCHASE capability required")

    enterprise_id = _clean(membership.get("enterprise_id"))
    branch_code = _clean(payload.get("branch_code")).upper()
    supplier_id = _clean(payload.get("supplier_id"))
    status = _clean(payload.get("status")).lower() or "draft"
    entry_id = _clean(payload.get("entry_id"))
    key = _clean(payload.get("idempotency_key"))
    raw_lines = payload.get("lines")

    if status not in ("draft", "recorded"):
        raise PurchaseEntryRuntimeError("status must be draft or recorded")
    if not enterprise_id or not branch_code or not supplier_id or not key:
        raise PurchaseEntryRuntimeError("branch, supplier and idempotency_key are required")
    if not isinstance(raw_lines, list) or not raw_lines:
        raise PurchaseEntryRuntimeError("at least one purchase item is required")

    supplier_gstin = _clean(payload.get("supplier_gstin")).upper()
    place_of_supply = _clean(payload.get("place_of_supply"))
    invoice_number = _clean(payload.get("invoice_number"))
    invoice_date = _parse_date(payload.get("invoice_date"))
    shipment_reference = _clean(payload.get("shipment_reference"))
    transporter = _clean(payload.get("transporter"))
    shipment_note = _clean(payload.get("shipment_note"))
    purchase_note = _clean(payload.get("purchase_note"))

    normalized_lines: list[dict[str, Any]] = []
    taxable_total = Decimal("0")
    cgst_total = Decimal("0")
    sgst_total = Decimal("0")
    igst_total = Decimal("0")

    now = datetime.now(timezone.utc)

    with connect(config) as conn:
        with conn.transaction():
            user = conn.execute(
                "select user_id,branch_id from users where enterprise_id=%s and principal_id=%s and active=true",
                (enterprise_id, principal_id),
            ).fetchone()
            if not user:
                raise PurchaseEntryRuntimeError("authenticated principal has no active ECHO user")
            user_id = str(user[0])
            user_branch_id = str(user[1]) if user[1] else None

            branch = conn.execute(
                "select branch_id,gst_state_code from branches where enterprise_id=%s and code=%s and active=true",
                (enterprise_id, branch_code),
            ).fetchone()
            if not branch:
                raise PurchaseEntryRuntimeError("active branch not found for enterprise")
            branch_id = str(branch[0])
            if not _branch_allowed(_clean(membership.get("role_code")), user_branch_id, branch_id):
                raise PermissionError("purchase entry is restricted to the user's branch")
            inter_state = _tax_mode(supplier_gstin, _clean(branch[1])) == "inter"

            if not conn.execute(
                "select 1 from suppliers where enterprise_id=%s and supplier_id=%s",
                (enterprise_id, supplier_id),
            ).fetchone():
                raise PurchaseEntryRuntimeError("supplier does not belong to enterprise")

            for i, raw in enumerate(raw_lines, 1):
                if not isinstance(raw, Mapping):
                    raise PurchaseEntryRuntimeError(f"invalid purchase item {i}")
                item_name = _clean(raw.get("item_name"))
                if not item_name:
                    raise PurchaseEntryRuntimeError(f"item name is required for line {i}")
                product_id = _clean(raw.get("product_id")) or None
                if product_id and not conn.execute(
                    "select 1 from products where enterprise_id=%s and product_id=%s and active=true",
                    (enterprise_id, product_id),
                ).fetchone():
                    raise PurchaseEntryRuntimeError(f"product on line {i} does not belong to enterprise")
                quantity = _decimal(raw.get("quantity"), f"quantity on line {i}", allow_zero=False)
                unit_rate = _decimal(raw.get("unit_rate"), f"unit_rate on line {i}")
                gst_rate = _decimal(raw.get("gst_rate"), f"gst_rate on line {i}")
                unit = _clean(raw.get("unit")) or "nos"
                hsn_code = _clean(raw.get("hsn_code"))

                taxable = _money(quantity * unit_rate)
                tax = _money(taxable * gst_rate / Decimal("100"))
                if inter_state:
                    cgst, sgst, igst = Decimal("0.00"), Decimal("0.00"), tax
                else:
                    half = _money(tax / Decimal("2"))
                    cgst, sgst, igst = half, half, Decimal("0.00")
                line_total = _money(taxable + cgst + sgst + igst)

                taxable_total += taxable
                cgst_total += cgst
                sgst_total += sgst
                igst_total += igst

                normalized_lines.append(
                    {
                        "product_id": product_id,
                        "item_name": item_name,
                        "hsn_code": hsn_code,
                        "unit": unit,
                        "quantity": quantity,
                        "unit_rate": unit_rate,
                        "gst_rate": gst_rate,
                        "taxable_amount": taxable,
                        "cgst_amount": cgst,
                        "sgst_amount": sgst,
                        "igst_amount": igst,
                        "line_total": line_total,
                    }
                )

            grand_total = _money(taxable_total + cgst_total + sgst_total + igst_total)

            if entry_id:
                existing = conn.execute(
                    "select status,entry_number from purchase_entries where enterprise_id=%s and entry_id=%s",
                    (enterprise_id, entry_id),
                ).fetchone()
                if not existing:
                    raise PurchaseEntryRuntimeError("purchase entry not found")
                if existing[0] == "recorded":
                    raise PurchaseEntryRuntimeError("a recorded purchase entry can no longer be edited")
                entry_number = existing[1]
                conn.execute(
                    """
                    update purchase_entries set
                      branch_id=%s,supplier_id=%s,status=%s,supplier_gstin=%s,place_of_supply=%s,
                      invoice_number=%s,invoice_date=%s,shipment_reference=%s,transporter=%s,
                      shipment_note=%s,purchase_note=%s,taxable_total=%s,cgst_total=%s,sgst_total=%s,
                      igst_total=%s,grand_total=%s,updated_at=%s
                    where enterprise_id=%s and entry_id=%s
                    """,
                    (
                        branch_id, supplier_id, status, supplier_gstin, place_of_supply,
                        invoice_number, invoice_date, shipment_reference, transporter,
                        shipment_note, purchase_note, taxable_total, cgst_total, sgst_total,
                        igst_total, grand_total, now,
                        enterprise_id, entry_id,
                    ),
                )
                conn.execute("delete from purchase_entry_lines where entry_id=%s", (entry_id,))
                idempotent_replay = False
            else:
                entry_id = _stable_id(enterprise_id, key)
                replay = conn.execute(
                    "select entry_number,status from purchase_entries where enterprise_id=%s and entry_id=%s",
                    (enterprise_id, entry_id),
                ).fetchone()
                if replay:
                    return {
                        "entry_id": entry_id,
                        "entry_number": replay[0],
                        "status": replay[1],
                        "taxable_total": str(taxable_total),
                        "cgst_total": str(cgst_total),
                        "sgst_total": str(sgst_total),
                        "igst_total": str(igst_total),
                        "grand_total": str(grand_total),
                        "idempotent_replay": True,
                    }
                seq = conn.execute(
                    """
                    insert into purchase_entry_sequences(enterprise_id,next_seq) values(%s,1)
                    on conflict(enterprise_id) do update set next_seq=purchase_entry_sequences.next_seq+1
                    returning next_seq
                    """,
                    (enterprise_id,),
                ).fetchone()
                entry_number = f"PE-{int(seq[0]):06d}"
                conn.execute(
                    """
                    insert into purchase_entries(
                      entry_id,enterprise_id,branch_id,supplier_id,entry_number,status,supplier_gstin,
                      place_of_supply,invoice_number,invoice_date,shipment_reference,transporter,
                      shipment_note,purchase_note,taxable_total,cgst_total,sgst_total,igst_total,
                      grand_total,created_by,created_at,updated_at
                    ) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        entry_id, enterprise_id, branch_id, supplier_id, entry_number, status,
                        supplier_gstin, place_of_supply, invoice_number, invoice_date,
                        shipment_reference, transporter, shipment_note, purchase_note,
                        taxable_total, cgst_total, sgst_total, igst_total, grand_total,
                        user_id, now, now,
                    ),
                )
                idempotent_replay = False

            for line_no, line in enumerate(normalized_lines, 1):
                conn.execute(
                    """
                    insert into purchase_entry_lines(
                      entry_id,line_no,product_id,item_name,hsn_code,unit,quantity,unit_rate,
                      gst_rate,taxable_amount,cgst_amount,sgst_amount,igst_amount,line_total
                    ) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        entry_id, line_no, line["product_id"], line["item_name"], line["hsn_code"],
                        line["unit"], line["quantity"], line["unit_rate"], line["gst_rate"],
                        line["taxable_amount"], line["cgst_amount"], line["sgst_amount"],
                        line["igst_amount"], line["line_total"],
                    ),
                )

    return {
        "entry_id": entry_id,
        "entry_number": entry_number,
        "status": status,
        "taxable_total": str(taxable_total),
        "cgst_total": str(cgst_total),
        "sgst_total": str(sgst_total),
        "igst_total": str(igst_total),
        "grand_total": str(grand_total),
        "idempotent_replay": idempotent_replay,
    }
