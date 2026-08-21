from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Iterable

from .health import ExpenseEvidence, FinancialHealthEngine, PurchasePriceEvidence, SaleLineEvidence


class OwnerOnCall:
    """Read-only owner financial status projection.

    This layer intentionally reports known, unknown, and stale evidence
    separately. It does not mutate transactions or classify ambiguous evidence.
    """

    def __init__(self, engine: FinancialHealthEngine | None = None) -> None:
        self.engine = engine or FinancialHealthEngine()

    @staticmethod
    def _in_period(d: date, start: date | None, end: date | None) -> bool:
        return (start is None or d >= start) and (end is None or d <= end)

    def snapshot(
        self,
        sales: Iterable[SaleLineEvidence],
        purchases: Iterable[PurchasePriceEvidence],
        expenses: Iterable[ExpenseEvidence] = (),
        *,
        start: date | None = None,
        end: date | None = None,
        branch: str | None = None,
        cash_position: Decimal | None = None,
        bank_position: Decimal | None = None,
        evidence_as_of: datetime | None = None,
    ) -> dict[str, object]:
        sale_rows = tuple(
            s for s in sales
            if self._in_period(s.sale_date, start, end) and (branch is None or s.branch == branch)
        )
        expense_rows = tuple(
            e for e in expenses
            if self._in_period(e.expense_date, start, end) and (branch is None or e.branch in {None, branch})
        )
        purchase_rows = tuple(purchases)
        summary = self.engine.summarize(sale_rows, purchase_rows, expense_rows)

        projections = summary["projections"]
        by_branch: dict[str, dict[str, object]] = defaultdict(
            lambda: {
                "sales_before_tax": Decimal("0"),
                "estimated_cogs_known": Decimal("0"),
                "estimated_gross_profit_known": Decimal("0"),
                "sale_lines": 0,
                "unknown_cost_lines": 0,
            }
        )
        for projection in projections:
            row = by_branch[projection.branch]
            row["sales_before_tax"] += projection.sales_before_tax
            row["sale_lines"] += 1
            if projection.estimated_cogs is None:
                row["unknown_cost_lines"] += 1
            else:
                row["estimated_cogs_known"] += projection.estimated_cogs
                row["estimated_gross_profit_known"] += projection.estimated_gross_profit or Decimal("0")

        for e in expense_rows:
            key = e.branch or "UNALLOCATED"
            row = by_branch[key]
            expense_key = "classified_operating_expenses" if e.category and e.classification_confidence != "unknown" else "unclassified_expenses"
            row.setdefault(expense_key, Decimal("0"))
            row[expense_key] += abs(e.amount)

        attention: list[dict[str, object]] = []
        if summary["sale_lines_unknown_cost"]:
            attention.append({
                "type": "unknown_cost",
                "count": summary["sale_lines_unknown_cost"],
                "message": "Sale lines lack reliable purchase-cost evidence.",
            })
        if summary["unclassified_expenses"]:
            attention.append({
                "type": "unclassified_expense",
                "amount": summary["unclassified_expenses"],
                "message": "Expense evidence exists but is not authoritatively classified.",
            })

        now = datetime.now(timezone.utc)
        freshness_seconds = None
        if evidence_as_of is not None:
            as_of = evidence_as_of if evidence_as_of.tzinfo else evidence_as_of.replace(tzinfo=timezone.utc)
            freshness_seconds = max(0, int((now - as_of).total_seconds()))

        return {
            "period": {"start": start, "end": end},
            "branch": branch,
            "sales_before_tax": summary["sales_before_tax"],
            "estimated_cogs_known": summary["estimated_cogs_known"],
            "estimated_gross_profit_known": summary["estimated_gross_profit_known"],
            "classified_operating_expenses": summary["classified_operating_expenses"],
            "estimated_operating_profit_known": summary["estimated_operating_profit_known"],
            "unclassified_expenses": summary["unclassified_expenses"],
            "cost_coverage_pct": summary["cost_coverage_pct"],
            "cash_position": cash_position,
            "bank_position": bank_position,
            "evidence_as_of": evidence_as_of,
            "freshness_seconds": freshness_seconds,
            "branches": dict(by_branch),
            "attention": tuple(attention),
            "drilldown": {
                "sale_projections": projections,
                "unknown_expense_evidence": summary["unknown_expense_evidence"],
            },
            "status": "projection_not_accounting_final",
        }
