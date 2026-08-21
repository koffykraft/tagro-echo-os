from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Iterable, Sequence


MONEY = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


class CostConfidence(str, Enum):
    EXACT = "exact"
    STRONG = "strong"
    WEAK = "weak"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PurchasePriceEvidence:
    item_key: str
    purchase_date: date
    cost_before_tax: Decimal
    branch: str | None = None
    vendor: str | None = None
    source_ref: str | None = None
    is_stock_transfer: bool = False


@dataclass(frozen=True)
class SaleLineEvidence:
    sale_id: str
    sale_date: date
    branch: str
    item_key: str
    quantity: Decimal
    sale_before_tax: Decimal
    explicit_cost_before_tax: Decimal | None = None
    source_ref: str | None = None


@dataclass(frozen=True)
class ExpenseEvidence:
    expense_id: str
    expense_date: date
    amount: Decimal
    branch: str | None = None
    category: str | None = None
    source_ref: str | None = None
    classification_confidence: str = "unknown"


@dataclass(frozen=True)
class CostEstimate:
    unit_cost: Decimal | None
    confidence: CostConfidence
    reference_count: int
    reference_dates: tuple[date, ...]
    source_refs: tuple[str, ...]
    policy: str


@dataclass(frozen=True)
class SaleProfitProjection:
    sale_id: str
    branch: str
    sale_date: date
    item_key: str
    quantity: Decimal
    sales_before_tax: Decimal
    estimated_cogs: Decimal | None
    estimated_gross_profit: Decimal | None
    gross_margin_pct: Decimal | None
    cost: CostEstimate


class FinancialHealthEngine:
    """Read-only financial projection engine.

    Purchase-cost policy:
      1. explicit sale-linked acquisition cost, when supplied, is exact;
      2. otherwise use external purchase evidence for the item dated no later
         than the sale;
      3. prefer the sale financial year; if absent, walk backwards through
         prior financial years;
      4. within the selected year, use up to the latest four prices (LIFO-like
         grab) and use their median as a robust reference cost;
      5. one reference is weak; two or more references are strong; none is
         unknown.

    The engine never guesses an expense category. Unclassified expenses remain
    explicit unknowns and are excluded from classified operating-P&L totals
    while still being reported separately.
    """

    @staticmethod
    def financial_year(d: date) -> tuple[int, int]:
        start = d.year if d.month >= 4 else d.year - 1
        return start, start + 1

    @staticmethod
    def _median(values: Sequence[Decimal]) -> Decimal:
        ordered = sorted(Decimal(v) for v in values)
        n = len(ordered)
        if n % 2:
            return ordered[n // 2]
        return (ordered[n // 2 - 1] + ordered[n // 2]) / Decimal("2")

    def estimate_cost(
        self,
        sale: SaleLineEvidence,
        purchases: Iterable[PurchasePriceEvidence],
    ) -> CostEstimate:
        if sale.explicit_cost_before_tax is not None:
            return CostEstimate(
                unit_cost=money(sale.explicit_cost_before_tax),
                confidence=CostConfidence.EXACT,
                reference_count=1,
                reference_dates=(sale.sale_date,),
                source_refs=((sale.source_ref,) if sale.source_ref else ()),
                policy="explicit sale-linked acquisition cost",
            )

        eligible = [
            p
            for p in purchases
            if p.item_key == sale.item_key
            and p.purchase_date <= sale.sale_date
            and not p.is_stock_transfer
            and p.cost_before_tax > 0
        ]
        if not eligible:
            return CostEstimate(None, CostConfidence.UNKNOWN, 0, (), (), "no valid purchase evidence")

        sale_fy = self.financial_year(sale.sale_date)[0]
        by_fy: dict[int, list[PurchasePriceEvidence]] = {}
        for p in eligible:
            by_fy.setdefault(self.financial_year(p.purchase_date)[0], []).append(p)

        selected_fy = max((fy for fy in by_fy if fy <= sale_fy), default=None)
        if selected_fy is None:
            return CostEstimate(None, CostConfidence.UNKNOWN, 0, (), (), "no prior purchase evidence")

        year_rows = sorted(
            by_fy[selected_fy],
            key=lambda p: (p.purchase_date, p.source_ref or ""),
            reverse=True,
        )[:4]

        reference = money(self._median([p.cost_before_tax for p in year_rows]))
        confidence = CostConfidence.STRONG if len(year_rows) >= 2 else CostConfidence.WEAK
        source_refs = tuple(p.source_ref for p in year_rows if p.source_ref)
        policy = f"latest {len(year_rows)} external purchase price(s) from FY {selected_fy}-{str(selected_fy + 1)[-2:]}"
        return CostEstimate(
            unit_cost=reference,
            confidence=confidence,
            reference_count=len(year_rows),
            reference_dates=tuple(p.purchase_date for p in year_rows),
            source_refs=source_refs,
            policy=policy,
        )

    def project_sale(
        self,
        sale: SaleLineEvidence,
        purchases: Iterable[PurchasePriceEvidence],
    ) -> SaleProfitProjection:
        cost = self.estimate_cost(sale, purchases)
        sales = money(sale.sale_before_tax)
        if cost.unit_cost is None:
            cogs = gp = margin = None
        else:
            cogs = money(abs(sale.quantity) * cost.unit_cost)
            gp = money(sales - cogs)
            margin = None if sales == 0 else (gp / sales * Decimal("100")).quantize(Decimal("0.01"))
        return SaleProfitProjection(
            sale_id=sale.sale_id,
            branch=sale.branch,
            sale_date=sale.sale_date,
            item_key=sale.item_key,
            quantity=sale.quantity,
            sales_before_tax=sales,
            estimated_cogs=cogs,
            estimated_gross_profit=gp,
            gross_margin_pct=margin,
            cost=cost,
        )

    def summarize(
        self,
        sales: Iterable[SaleLineEvidence],
        purchases: Iterable[PurchasePriceEvidence],
        expenses: Iterable[ExpenseEvidence] = (),
    ) -> dict[str, object]:
        purchase_rows = tuple(purchases)
        projected = tuple(self.project_sale(s, purchase_rows) for s in sales)
        classified_expenses = [e for e in expenses if e.category and e.classification_confidence != "unknown"]
        unknown_expenses = [e for e in expenses if not e.category or e.classification_confidence == "unknown"]

        sales_total = money(sum((p.sales_before_tax for p in projected), Decimal("0")))
        known_cogs = money(sum((p.estimated_cogs or Decimal("0") for p in projected), Decimal("0")))
        known_gp = money(sum((p.estimated_gross_profit or Decimal("0") for p in projected), Decimal("0")))
        expense_total = money(sum((abs(e.amount) for e in classified_expenses), Decimal("0")))
        unknown_expense_total = money(sum((abs(e.amount) for e in unknown_expenses), Decimal("0")))
        unknown_cost_sales = sum(1 for p in projected if p.cost.confidence == CostConfidence.UNKNOWN)

        return {
            "sales_before_tax": sales_total,
            "estimated_cogs_known": known_cogs,
            "estimated_gross_profit_known": known_gp,
            "classified_operating_expenses": expense_total,
            "estimated_operating_profit_known": money(known_gp - expense_total),
            "unclassified_expenses": unknown_expense_total,
            "sale_lines": len(projected),
            "sale_lines_unknown_cost": unknown_cost_sales,
            "cost_coverage_pct": (
                Decimal("0.00")
                if not projected
                else (Decimal(len(projected) - unknown_cost_sales) / Decimal(len(projected)) * Decimal("100")).quantize(Decimal("0.01"))
            ),
            "projections": projected,
            "unknown_expense_evidence": tuple(unknown_expenses),
        }
