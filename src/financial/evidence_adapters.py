from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from src.bank.normalization import BankTransaction
from src.cash.closing import ClosingCash

from .health import ExpenseEvidence, ExpenseRole


@dataclass(frozen=True)
class ExpenseClassification:
    """Explicit, owner/governance supplied classification rule.

    Adapters never infer a category or financial role from narration. A caller
    may supply a rule keyed by an exact evidence identifier only after that rule
    has been governed.
    """

    category: str
    role: ExpenseRole
    confidence: str = "exact"


def closing_cash_expense_evidence(
    closing: ClosingCash,
    classifications: Mapping[str, ExpenseClassification] | None = None,
) -> ExpenseEvidence | None:
    """Expose Closing Cash expense as evidence without inventing an expense head."""
    amount = Decimal(closing.cash_expenses)
    if amount <= 0:
        return None
    evidence_id = f"closing-cash:{closing.closing_id}:expense"
    rule = (classifications or {}).get(evidence_id)
    return ExpenseEvidence(
        expense_id=evidence_id,
        expense_date=closing.business_date,
        amount=amount,
        branch=closing.branch_id,
        category=rule.category if rule else None,
        source_ref=f"closing-cash:{closing.closing_id}",
        classification_confidence=rule.confidence if rule else "unknown",
        role=rule.role if rule else ExpenseRole.UNKNOWN,
    )


def bank_debit_expense_evidence(
    transaction: BankTransaction,
    branch: str | None = None,
    classifications: Mapping[str, ExpenseClassification] | None = None,
) -> ExpenseEvidence | None:
    """Expose a bank debit as candidate expense evidence.

    Debit does not itself prove operating expense: it may be a supplier payment,
    transfer, capital movement, finance payment, owner movement, or expense.
    Therefore the default remains unclassified.
    """
    transaction.validate()
    if transaction.direction != "debit":
        return None
    evidence_id = f"bank:{transaction.transaction_id}"
    rule = (classifications or {}).get(evidence_id)
    return ExpenseEvidence(
        expense_id=evidence_id,
        expense_date=transaction.transaction_date,
        amount=Decimal(transaction.amount),
        branch=branch,
        category=rule.category if rule else None,
        source_ref=f"bank:{transaction.statement_id}:{transaction.source_row}",
        classification_confidence=rule.confidence if rule else "unknown",
        role=rule.role if rule else ExpenseRole.UNKNOWN,
    )


def collect_expense_evidence(
    cash_closings: tuple[ClosingCash, ...] = (),
    bank_transactions: tuple[BankTransaction, ...] = (),
    branch_by_account: Mapping[str, str] | None = None,
    classifications: Mapping[str, ExpenseClassification] | None = None,
) -> tuple[ExpenseEvidence, ...]:
    rows: list[ExpenseEvidence] = []
    for closing in cash_closings:
        row = closing_cash_expense_evidence(closing, classifications)
        if row is not None:
            rows.append(row)
    for transaction in bank_transactions:
        row = bank_debit_expense_evidence(
            transaction,
            branch=(branch_by_account or {}).get(transaction.account_id),
            classifications=classifications,
        )
        if row is not None:
            rows.append(row)
    return tuple(rows)
