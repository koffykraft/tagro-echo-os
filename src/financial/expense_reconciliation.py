from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

from .health import ExpenseEvidence, ExpenseRole, money


@dataclass(frozen=True)
class ExpenseReconciliationResult:
    """Deterministic expense evidence partition for financial projections.

    Numeric admission follows a conservative precedence rule:
      1. canonical Closing Cash entry evidence is admitted;
      2. a Closing Cash aggregate contributes only the positive residual not
         already represented by canonical entries in the same branch/date;
      3. accounting observations are admitted only where no Closing Cash
         aggregate exists for the same branch/date slice;
      4. potentially overlapping accounting observations remain visible as
         excluded supporting evidence, never silently discarded or summed;
      5. if canonical entry evidence exceeds its Closing Cash aggregate, the
         entries are retained and the inconsistency is surfaced for review.

    This utility never infers category or P&L role from narration, amount,
    account name, voucher type, or cash/bank direction.
    """

    admitted: tuple[ExpenseEvidence, ...]
    excluded_supporting: tuple[ExpenseEvidence, ...]
    aggregate_residuals: tuple[ExpenseEvidence, ...]
    inconsistencies: tuple[dict[str, object], ...]

    @property
    def excluded_supporting_amount(self) -> Decimal:
        return money(sum((abs(row.amount) for row in self.excluded_supporting), Decimal("0")))


def _slice_key(row: ExpenseEvidence) -> tuple[str | None, date]:
    branch = str(row.branch).strip().upper() if row.branch else None
    return branch, row.expense_date


def reconcile_expense_evidence(
    canonical_cash_entries: Iterable[ExpenseEvidence],
    accounting_observations: Iterable[ExpenseEvidence],
    closing_cash_aggregates: Iterable[ExpenseEvidence],
) -> ExpenseReconciliationResult:
    """Reconcile expense evidence without fabricating cross-source identity.

    Same branch/date is only an overlap boundary, not a claim that two source
    rows are the same expense. Accounting observations inside a Closing Cash
    aggregate slice are therefore held out of the numeric projection until a
    deterministic mapping exists. They remain available for drill-down/review.
    """

    entries = tuple(canonical_cash_entries)
    accounting = tuple(accounting_observations)
    aggregates = tuple(closing_cash_aggregates)

    entry_totals: dict[tuple[str | None, date], Decimal] = {}
    for row in entries:
        key = _slice_key(row)
        entry_totals[key] = entry_totals.get(key, Decimal("0")) + abs(row.amount)

    aggregate_keys = {_slice_key(row) for row in aggregates}
    admitted: list[ExpenseEvidence] = list(entries)
    residuals: list[ExpenseEvidence] = []
    inconsistencies: list[dict[str, object]] = []

    for aggregate in aggregates:
        key = _slice_key(aggregate)
        aggregate_amount = abs(aggregate.amount)
        represented = entry_totals.get(key, Decimal("0"))
        residual = aggregate_amount - represented
        if residual > 0:
            residual_row = ExpenseEvidence(
                expense_id=f"{aggregate.expense_id}:residual",
                expense_date=aggregate.expense_date,
                amount=money(residual),
                branch=aggregate.branch,
                category=None,
                source_ref=aggregate.source_ref,
                classification_confidence="unknown",
                role=ExpenseRole.UNKNOWN,
            )
            admitted.append(residual_row)
            residuals.append(residual_row)
        elif residual < 0:
            inconsistencies.append(
                {
                    "type": "closing_cash_entry_total_exceeds_aggregate",
                    "branch": key[0],
                    "business_date": key[1],
                    "aggregate_expense": money(aggregate_amount),
                    "entry_expense": money(represented),
                    "difference": money(represented - aggregate_amount),
                    "source_ref": aggregate.source_ref,
                }
            )

    excluded: list[ExpenseEvidence] = []
    for row in accounting:
        if _slice_key(row) in aggregate_keys:
            excluded.append(row)
        else:
            admitted.append(row)

    return ExpenseReconciliationResult(
        admitted=tuple(admitted),
        excluded_supporting=tuple(excluded),
        aggregate_residuals=tuple(residuals),
        inconsistencies=tuple(inconsistencies),
    )
