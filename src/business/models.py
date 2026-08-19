from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Sequence
from uuid import uuid4


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def new_id(prefix: str) -> str:
    return f'{prefix}-{uuid4().hex[:12]}'


@dataclass(frozen=True)
class UserRecord:
    user_id: str; name: str; email: str; role: str; branch_id: str | None = None; active: bool = True

@dataclass(frozen=True)
class Branch:
    branch_id: str; code: str; name: str; district: str; branch_type: str = 'counter'; active: bool = True

@dataclass(frozen=True)
class Product:
    product_id: str; sku: str; model: str; name: str; category: str; gst_rate: Decimal; unit: str = 'nos'; serial_tracked: bool = False; active: bool = True

@dataclass(frozen=True)
class PriceRecord:
    price_id: str; product_id: str; price_type: str; amount: Decimal; effective_from: date; effective_to: date | None = None; branch_id: str | None = None

@dataclass(frozen=True)
class Customer:
    customer_id: str; name: str; phone: str; email: str = ''; gstin: str = ''; district: str = ''

@dataclass(frozen=True)
class Supplier:
    supplier_id: str; name: str; phone: str = ''; email: str = ''; gstin: str = ''

@dataclass(frozen=True)
class LineItem:
    product_id: str; quantity: Decimal; unit_price: Decimal; gst_rate: Decimal; discount: Decimal = Decimal('0.00')
    @property
    def taxable(self): return money(self.quantity * self.unit_price - self.discount)
    @property
    def tax(self): return money(self.taxable * self.gst_rate / Decimal('100'))
    @property
    def total(self): return money(self.taxable + self.tax)

@dataclass(frozen=True)
class Quote:
    quote_id: str; branch_id: str; customer_id: str; created_at: datetime; items: Sequence[LineItem]; status: str = 'draft'
    @property
    def total(self): return money(sum((x.total for x in self.items), Decimal('0')))

@dataclass(frozen=True)
class Sale:
    sale_id: str; branch_id: str; customer_id: str | None; created_at: datetime; items: Sequence[LineItem]; payment_status: str = 'unpaid'; source_quote_id: str | None = None
    @property
    def total(self): return money(sum((x.total for x in self.items), Decimal('0')))

@dataclass(frozen=True)
class Purchase:
    purchase_id: str; branch_id: str; supplier_id: str; created_at: datetime; items: Sequence[LineItem]; supplier_invoice_no: str = ''
    @property
    def total(self): return money(sum((x.total for x in self.items), Decimal('0')))

@dataclass(frozen=True)
class StockMovement:
    movement_id: str; branch_id: str; product_id: str; quantity_delta: Decimal; movement_type: str; occurred_at: datetime; reference_type: str; reference_id: str; note: str = ''
