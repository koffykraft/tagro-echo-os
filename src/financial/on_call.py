from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Iterable, Mapping

from .cost_confidence import confidence_breakdown
from .health import ExpenseEvidence, ExpenseRole, FinancialHealthEngine, PurchasePriceEvidence, SaleLineEvidence


class OwnerOnCall:
    """Read-only owner financial status projection.

    This layer reports known, unknown, and stale evidence separately. It does
    not mutate transactions or classify ambiguous evidence. Profitability is
    always accompanied by cost/evidence coverage so partial projections cannot
    masquerade as complete business P&L.
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
        prism_status: Mapping[str, object] | None = None,
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
        cost_confidence = confidence_breakdown(projections)
        by_branch: dict[str, dict[str, object]] = defaultdict(
            lambda: {
                "sales_before_tax": Decimal("0"),
                "sales_with_known_cost": Decimal("0"),
                "sales_without_known_cost": Decimal("0"),
                "estimated_cogs_known": Decimal("0"),
                "estimated_gross_profit_known": Decimal("0"),
                "sale_lines": 0,
                "unknown_cost_lines": 0,
                "classified_direct_selling_costs": Decimal("0"),
                "classified_branch_operating_expenses": Decimal("0"),
                "classified_central_overhead": Decimal("0"),
                "classified_finance_costs": Decimal("0"),
                "classified_pnl_expenses": Decimal("0"),
                "unclassified_expenses": Decimal("0"),
            }
        )
        for projection in projections:
            row = by_branch[projection.branch]
            row["sales_before_tax"] += projection.sales_before_tax
            row["sale_lines"] += 1
            if projection.estimated_cogs is None:
                row["unknown_cost_lines"] += 1
                row["sales_without_known_cost"] += projection.sales_before_tax
            else:
                row["sales_with_known_cost"] += projection.sales_before_tax
                row["estimated_cogs_known"] += projection.estimated_cogs
                row["estimated_gross_profit_known"] += projection.estimated_gross_profit or Decimal("0")

        role_keys = {
            ExpenseRole.DIRECT: "classified_direct_selling_costs",
            ExpenseRole.BRANCH: "classified_branch_operating_expenses",
            ExpenseRole.CENTRAL: "classified_central_overhead",
            ExpenseRole.FINANCE: "classified_finance_costs",
        }
        pnl_roles = set(role_keys)
        for e in expense_rows:
            key = e.branch or "UNALLOCATED"
            row = by_branch[key]
            classified = self.engine._classified(e)
            if not classified:
                row["unclassified_expenses"] += abs(e.amount)
                continue
            if e.role in pnl_roles:
                amount = abs(e.amount)
                row[role_keys[e.role]] += amount
                row["classified_pnl_expenses"] += amount

        for row in by_branch.values():
            total = row["sales_before_tax"]
            known = row["sales_with_known_cost"]
            row["cost_revenue_coverage_pct"] = (
                Decimal("0.00") if total == 0
                else (known / total * Decimal("100")).quantize(Decimal("0.01"))
            )
            row["estimated_contribution_known"] = (
                row["estimated_gross_profit_known"] - row["classified_direct_selling_costs"]
            ).quantize(Decimal("0.01"))
            row["estimated_branch_contribution_known"] = (
                row["estimated_contribution_known"] - row["classified_branch_operating_expenses"]
            ).quantize(Decimal("0.01"))
            row["estimated_operating_profit_known"] = (
                row["estimated_branch_contribution_known"] - row["classified_central_overhead"]
            ).quantize(Decimal("0.01"))
            row["estimated_profit_after_finance_known"] = (
                row["estimated_operating_profit_known"] - row["classified_finance_costs"]
            ).quantize(Decimal("0.01"))

        attention: list[dict[str, object]] = []
        if summary["sale_lines_unknown_cost"]:
            attention.append({
                "type": "unknown_cost",
                "count": summary["sale_lines_unknown_cost"],
                "revenue": summary["sales_without_known_cost"],
                "message": "Sale lines lack reliable purchase-cost evidence; profit is partial.",
            })
        if cost_confidence["weak_or_unknown_sales_before_tax"]:
            attention.append({
                "type": "cost_confidence_exposure",
                "amount": cost_confidence["weak_or_unknown_sales_before_tax"],
                "coverage_pct": cost_confidence["exact_or_strong_revenue_coverage_pct"],
                "message": "Part of sales revenue is supported only by weak or unknown acquisition-cost evidence.",
            })
        if summary["unclassified_expenses"]:
            attention.append({
                "type": "unclassified_expense",
                "amount": summary["unclassified_expenses"],
                "message": "Expense evidence exists but is not authoritatively classified.",
            })
        if prism_status:
            unresolved_count = int(prism_status.get("unresolved_count", 0) or 0)
            tight_count = int(prism_status.get("tight_split_count", 0) or 0)
            if unresolved_count:
                attention.append({
                    "type": "prism_unresolved",
                    "count": unresolved_count,
                    "amount": prism_status.get("unresolved_amount"),
                    "message": "Financial movements remain at a broader Prism meaning pending stronger evidence.",
                })
            if tight_count:
                attention.append({
                    "type": "prism_tight_split",
                    "count": tight_count,
                    "amount": prism_status.get("tight_split_amount"),
                    "message": "Competing meanings are too close; ECHO deliberately stepped back instead of forcing a classification.",
                })
        if not summary["projection_complete"]:
            attention.append({
                "type": "projection_incomplete",
                "message": "Profitability is a governed projection, not accounting-final P&L.",
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
            "sales_with_known_cost": summary["sales_with_known_cost"],
            "sales_without_known_cost": summary["sales_without_known_cost"],
            "estimated_cogs_known": summary["estimated_cogs_known"],
            "estimated_gross_profit_known": summary["estimated_gross_profit_known"],
            "gross_margin_pct_on_known_cost_sales": summary["gross_margin_pct_on_known_cost_sales"],
            "classified_direct_selling_costs": summary["classified_direct_selling_costs"],
            "classified_branch_operating_expenses": summary["classified_branch_operating_expenses"],
            "classified_central_overhead": summary["classified_central_overhead"],
            "classified_operating_expenses": summary["classified_operating_expenses"],
            "classified_finance_costs": summary["classified_finance_costs"],
            "estimated_contribution_known": summary["estimated_contribution_known"],
            "estimated_branch_contribution_known": summary["estimated_branch_contribution_known"],
            "estimated_operating_profit_known": summary["estimated_operating_profit_known"],
            "estimated_profit_after_finance_known": summary["estimated_profit_after_finance_known"],
            "unclassified_expenses": summary["unclassified_expenses"],
            "expense_role_totals": summary["expense_role_totals"],
            "cost_coverage_pct": summary["cost_coverage_pct"],
            "cost_revenue_coverage_pct": summary["cost_revenue_coverage_pct"],
            "cost_confidence_counts": summary["cost_confidence_counts"],
            "cost_confidence_revenue": summary["cost_confidence_revenue"],
            "cost_confidence": cost_confidence,
            "projection_complete": summary["projection_complete"],
            "cash_position": cash_position,
            "bank_position": bank_position,
            "evidence_as_of": evidence_as_of,
            "freshness_seconds": freshness_seconds,
            "prism_status": dict(prism_status) if prism_status else None,
            "branches": dict(by_branch),
            "attention": tuple(attention),
            "drilldown": {
                "sale_projections": projections,
                "unknown_expense_evidence": summary["unknown_expense_evidence"],
                "prism_review_queue": tuple(prism_status.get("review_queue", ())) if prism_status else (),
            },
            "status": "projection_not_accounting_final",
        }
