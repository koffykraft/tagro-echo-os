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


class ExpenseRole(str, Enum):
    """Governed financial role; never inferred from narration by this engine."""

    DIRECT = "direct_selling_cost"
    BRANCH = "branch_operating_expense"
    CENTRAL = "central_overhead"
    FINANCE = "finance_cost"
    NON_OPERATING = "non_operating"
    CAPITAL = "capital_movement"
    INTERNAL_TRANSFER = "internal_transfer"
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
    role: ExpenseRole = ExpenseRole.UNKNOWN


@dataclass(frozen=True)
class CostEstimate:
    unit_cost: Decimal | None
    confidence: CostConfidence
    reference_count: int
    reference_dates: tuple[date, ...]
    source_refs: tuple[str, ...]
    policy: str
    reference_scope: str = "unknown"
    reference_low: Decimal | None = None
    reference_high: Decimal | None = None
    latest_reference: Decimal | None = None


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
      4. in the chosen year prefer same-branch purchase evidence when present,
         otherwise use enterprise-wide evidence;
      5. take up to the latest four prices (LIFO-like grab), expose the full
         comparison band, and use their median as the reference cost;
      6. three/four references are strong, one/two are weak, none is unknown.

    Expense categories/roles are authoritative inputs. The engine never guesses
    them from narration. Unknown evidence remains visible and is excluded from
    classified P&L while its value is reported explicitly.
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
            exact = money(sale.explicit_cost_before_tax)
            return CostEstimate(
                unit_cost=exact,
                confidence=CostConfidence.EXACT,
                reference_count=1,
                reference_dates=(sale.sale_date,),
                source_refs=((sale.source_ref,) if sale.source_ref else ()),
                policy="explicit sale-linked acquisition cost",
                reference_scope="sale_linked",
                reference_low=exact,
                reference_high=exact,
                latest_reference=exact,
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

        year_rows = by_fy[selected_fy]
        same_branch = [p for p in year_rows if p.branch == sale.branch]
        scoped_rows = same_branch if same_branch else year_rows
        scope = "same_branch" if same_branch else "enterprise_fallback"
        selected = sorted(
            scoped_rows,
            key=lambda p: (p.purchase_date, p.source_ref or ""),
            reverse=True,
        )[:4]

        values = [p.cost_before_tax for p in selected]
        reference = money(self._median(values))
        confidence = CostConfidence.STRONG if len(selected) >= 3 else CostConfidence.WEAK
        source_refs = tuple(p.source_ref for p in selected if p.source_ref)
        fy_label = f"FY {selected_fy}-{str(selected_fy + 1)[-2:]}"
        policy = f"latest {len(selected)} external purchase price(s) from {fy_label}; {scope}"
        return CostEstimate(
            unit_cost=reference,
            confidence=confidence,
            reference_count=len(selected),
            reference_dates=tuple(p.purchase_date for p in selected),
            source_refs=source_refs,
            policy=policy,
            reference_scope=scope,
            reference_low=money(min(values)),
            reference_high=money(max(values)),
            latest_reference=money(selected[0].cost_before_tax),
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

    @staticmethod
    def _classified(expense: ExpenseEvidence) -> bool:
        return (
            bool(expense.category)
            and expense.classification_confidence != "unknown"
            and expense.role != ExpenseRole.UNKNOWN
        )

    def summarize(
        self,
        sales: Iterable[SaleLineEvidence],
        purchases: Iterable[PurchasePriceEvidence],
        expenses: Iterable[ExpenseEvidence] = (),
    ) -> dict[str, object]:
        purchase_rows = tuple(purchases)
        projected = tuple(self.project_sale(s, purchase_rows) for s in sales)
        expense_rows = tuple(expenses)
        classified_expenses = [e for e in expense_rows if self._classified(e)]
        unknown_expenses = [e for e in expense_rows if not self._classified(e)]
        pnl_expenses = [
            e for e in classified_expenses
            if e.role in {ExpenseRole.DIRECT, ExpenseRole.BRANCH, ExpenseRole.CENTRAL, ExpenseRole.FINANCE}
        ]
        operating_expenses = [
            e for e in classified_expenses
            if e.role in {ExpenseRole.DIRECT, ExpenseRole.BRANCH, ExpenseRole.CENTRAL}
        ]
        finance_expenses = [e for e in classified_expenses if e.role == ExpenseRole.FINANCE]

        known_cost = [p for p in projected if p.estimated_cogs is not None]
        unknown_cost = [p for p in projected if p.estimated_cogs is None]
        sales_total = money(sum((p.sales_before_tax for p in projected), Decimal("0")))
        sales_known_cost = money(sum((p.sales_before_tax for p in known_cost), Decimal("0")))
        sales_unknown_cost = money(sum((p.sales_before_tax for p in unknown_cost), Decimal("0")))
        known_cogs = money(sum((p.estimated_cogs or Decimal("0") for p in known_cost), Decimal("0")))
        known_gp = money(sum((p.estimated_gross_profit or Decimal("0") for p in known_cost), Decimal("0")))
        operating_total = money(sum((abs(e.amount) for e in operating_expenses), Decimal("0")))
        finance_total = money(sum((abs(e.amount) for e in finance_expenses), Decimal("0")))
        classified_pnl_total = money(sum((abs(e.amount) for e in pnl_expenses), Decimal("0")))
        unknown_expense_total = money(sum((abs(e.amount) for e in unknown_expenses), Decimal("0")))

        line_coverage = (
            Decimal("0.00") if not projected
            else (Decimal(len(known_cost)) / Decimal(len(projected)) * Decimal("100")).quantize(Decimal("0.01"))
        )
        revenue_coverage = (
            Decimal("0.00") if sales_total == 0
            else (sales_known_cost / sales_total * Decimal("100")).quantize(Decimal("0.01"))
        )
        known_margin = (
            None if sales_known_cost == 0
            else (known_gp / sales_known_cost * Decimal("100")).quantize(Decimal("0.01"))
        )
        confidence_counts = {c.value: sum(1 for p in projected if p.cost.confidence == c) for c in CostConfidence}
        role_totals = {
            role.value: money(sum((abs(e.amount) for e in classified_expenses if e.role == role), Decimal("0")))
            for role in ExpenseRole if role != ExpenseRole.UNKNOWN
        }

        return {
            "sales_before_tax": sales_total,
            "sales_with_known_cost": sales_known_cost,
            "sales_without_known_cost": sales_unknown_cost,
            "estimated_cogs_known": known_cogs,
            "estimated_gross_profit_known": known_gp,
            "gross_margin_pct_on_known_cost_sales": known_margin,
            "classified_operating_expenses": operating_total,
            "classified_finance_costs": finance_total,
            "classified_pnl_expenses": classified_pnl_total,
            "estimated_operating_profit_known": money(known_gp - operating_total),
            "estimated_profit_after_finance_known": money(known_gp - operating_total - finance_total),
            "unclassified_expenses": unknown_expense_total,
            "expense_role_totals": role_totals,
            "sale_lines": len(projected),
            "sale_lines_unknown_cost": len(unknown_cost),
            "cost_coverage_pct": line_coverage,
            "cost_revenue_coverage_pct": revenue_coverage,
            "cost_confidence_counts": confidence_counts,
            "projection_complete": not unknown_cost and not unknown_expenses,
            "projections": projected,
            "unknown_expense_evidence": tuple(unknown_expenses),
        }
