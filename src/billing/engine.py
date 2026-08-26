from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import json
from typing import Iterable, Mapping
from uuid import uuid4


class BillingError(ValueError):
    pass


def money(value: Decimal | str | int | float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class BillingLine:
    product_id: str
    description: str
    quantity: Decimal
    unit_price_before_tax: Decimal
    gst_rate: Decimal
    discount_before_tax: Decimal = Decimal("0")

    @property
    def taxable(self) -> Decimal:
        return money(self.quantity * self.unit_price_before_tax - self.discount_before_tax)

    @property
    def tax(self) -> Decimal:
        return money(self.taxable * self.gst_rate / Decimal("100"))

    @property
    def total(self) -> Decimal:
        return money(self.taxable + self.tax)

    def validate(self) -> None:
        if not self.product_id.strip():
            raise BillingError("product_id is required")
        if self.quantity <= 0:
            raise BillingError("quantity must be positive")
        if self.unit_price_before_tax < 0 or self.discount_before_tax < 0:
            raise BillingError("price/discount cannot be negative")
        if self.taxable < 0:
            raise BillingError("discount cannot exceed line value")
        if self.gst_rate < 0:
            raise BillingError("gst_rate cannot be negative")


@dataclass(frozen=True)
class BillingRequest:
    enterprise_id: str
    branch_id: str
    branch_code: str
    actor_id: str
    actor_role: str
    customer_id: str | None
    customer_name: str
    lines: tuple[BillingLine, ...]
    payment_mode: str
    idempotency_key: str
    owner_stock_override: bool = False
    stock_override_reason: str = ""


@dataclass(frozen=True)
class EchoBill:
    bill_id: str
    enterprise_id: str
    branch_id: str
    branch_code: str
    customer_id: str | None
    customer_name: str
    lines: tuple[BillingLine, ...]
    payment_mode: str
    created_by: str
    created_at: str
    taxable_total: Decimal
    tax_total: Decimal
    invoice_total: Decimal
    stock_exception: bool
    stock_exception_reason: str
    status: str = "echo_issued"


@dataclass(frozen=True)
class BusySeriesConfig:
    branch_code: str
    voucher_series: str
    material_centre_ref: str | None = None


@dataclass(frozen=True)
class BusyBookingHandoff:
    handoff_id: str
    bill_id: str
    enterprise_id: str
    branch_code: str
    voucher_series: str
    material_centre_ref: str | None
    payload: Mapping[str, object]
    payload_hash: str
    status: str = "queued_not_booked"


class BillingEngine:
    """Operational ECHO billing with an explicit BUSY proving boundary.

    ECHO issue is operational truth inside this engine. BUSY remains a separate
    accounting/GST destination during proving. Creating a handoff never claims
    that BUSY has booked the voucher; a local bridge must confirm that later.
    """

    def __init__(self) -> None:
        self._bills_by_idempotency: dict[str, EchoBill] = {}
        self._request_hash_by_idempotency: dict[str, str] = {}

    @staticmethod
    def _request_payload(request: BillingRequest) -> dict[str, object]:
        return {
            "enterprise_id": request.enterprise_id,
            "branch_id": request.branch_id,
            "branch_code": request.branch_code,
            "actor_id": request.actor_id,
            "actor_role": request.actor_role,
            "customer_id": request.customer_id,
            "customer_name": request.customer_name,
            "payment_mode": request.payment_mode,
            "owner_stock_override": request.owner_stock_override,
            "stock_override_reason": request.stock_override_reason,
            "lines": [
                {
                    "product_id": line.product_id,
                    "description": line.description,
                    "quantity": str(line.quantity),
                    "unit_price_before_tax": str(line.unit_price_before_tax),
                    "gst_rate": str(line.gst_rate),
                    "discount_before_tax": str(line.discount_before_tax),
                }
                for line in request.lines
            ],
        }

    @classmethod
    def _request_hash(cls, request: BillingRequest) -> str:
        payload = cls._request_payload(request)
        return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def issue(
        self,
        request: BillingRequest,
        stock_on_hand: Mapping[str, Decimal],
    ) -> EchoBill:
        if not request.enterprise_id or not request.branch_id or not request.branch_code:
            raise BillingError("enterprise/branch identity is required")
        if not request.actor_id.strip() or not request.idempotency_key.strip():
            raise BillingError("actor_id and idempotency_key are required")
        if not request.lines:
            raise BillingError("at least one billing line is required")
        for line in request.lines:
            line.validate()

        digest = self._request_hash(request)
        existing = self._bills_by_idempotency.get(request.idempotency_key)
        if existing:
            if self._request_hash_by_idempotency[request.idempotency_key] != digest:
                raise BillingError("idempotency key replayed with different billing payload")
            return existing

        shortage = []
        for line in request.lines:
            available = Decimal(stock_on_hand.get(line.product_id, Decimal("0")))
            if available < line.quantity:
                shortage.append((line.product_id, available, line.quantity))
        stock_exception = bool(shortage)
        if stock_exception:
            if request.actor_role.strip().upper() != "OWNER" or not request.owner_stock_override:
                raise BillingError("insufficient stock; owner override required")
            if not request.stock_override_reason.strip():
                raise BillingError("owner stock override requires a reason")

        taxable = money(sum((line.taxable for line in request.lines), Decimal("0")))
        tax = money(sum((line.tax for line in request.lines), Decimal("0")))
        total = money(taxable + tax)
        bill = EchoBill(
            bill_id=f"echo-bill-{uuid4().hex[:16]}",
            enterprise_id=request.enterprise_id,
            branch_id=request.branch_id,
            branch_code=request.branch_code.upper(),
            customer_id=request.customer_id,
            customer_name=request.customer_name.strip(),
            lines=tuple(request.lines),
            payment_mode=request.payment_mode.strip().lower(),
            created_by=request.actor_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            taxable_total=taxable,
            tax_total=tax,
            invoice_total=total,
            stock_exception=stock_exception,
            stock_exception_reason=request.stock_override_reason.strip() if stock_exception else "",
        )
        self._bills_by_idempotency[request.idempotency_key] = bill
        self._request_hash_by_idempotency[request.idempotency_key] = digest
        return bill

    def prepare_busy_handoff(
        self,
        bill: EchoBill,
        series_by_branch: Mapping[str, BusySeriesConfig],
    ) -> BusyBookingHandoff:
        config = series_by_branch.get(bill.branch_code.upper())
        if config is None or not config.voucher_series.strip():
            raise BillingError("BUSY voucher series is not configured for this branch")
        payload: dict[str, object] = {
            "source": "ECHO",
            "echo_bill_id": bill.bill_id,
            "branch_code": bill.branch_code,
            "voucher_series": config.voucher_series,
            "material_centre_ref": config.material_centre_ref,
            "customer_id": bill.customer_id,
            "customer_name": bill.customer_name,
            "payment_mode": bill.payment_mode,
            "taxable_total": str(bill.taxable_total),
            "tax_total": str(bill.tax_total),
            "invoice_total": str(bill.invoice_total),
            "lines": [
                {
                    "product_id": line.product_id,
                    "description": line.description,
                    "quantity": str(line.quantity),
                    "unit_price_before_tax": str(line.unit_price_before_tax),
                    "discount_before_tax": str(line.discount_before_tax),
                    "gst_rate": str(line.gst_rate),
                    "taxable": str(line.taxable),
                    "tax": str(line.tax),
                    "total": str(line.total),
                }
                for line in bill.lines
            ],
        }
        digest = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return BusyBookingHandoff(
            handoff_id=f"busy-bill-{uuid4().hex[:16]}",
            bill_id=bill.bill_id,
            enterprise_id=bill.enterprise_id,
            branch_code=bill.branch_code,
            voucher_series=config.voucher_series,
            material_centre_ref=config.material_centre_ref,
            payload=payload,
            payload_hash=digest,
        )
