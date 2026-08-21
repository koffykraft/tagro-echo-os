from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal

from src.financial.expense_reconciliation import reconcile_expense_evidence
from src.financial.health import ExpenseEvidence, ExpenseRole


D = date(2026, 8, 21)


def expense(
    expense_id: str,
    amount: str,
    *,
    branch: str | None = "KVR",
    category: str | None = None,
    confidence: str = "unknown",
    role: ExpenseRole = ExpenseRole.UNKNOWN,
    source_ref: str | None = None,
) -> ExpenseEvidence:
    return ExpenseEvidence(
        expense_id=expense_id,
        expense_date=D,
        amount=Decimal(amount),
        branch=branch,
        category=category,
        source_ref=source_ref or expense_id,
        classification_confidence=confidence,
        role=role,
    )


class ExpenseReconciliationTests(unittest.TestCase):
    def test_closing_cash_aggregate_only_adds_unrepresented_residual(self):
        entries = [
            expense("cash:1", "200", category="courier", confidence="exact", role=ExpenseRole.BRANCH),
            expense("cash:2", "300"),
        ]
        aggregate = [expense("closing:1", "700", source_ref="postgres:cash-closing:1")]

        result = reconcile_expense_evidence(entries, (), aggregate)

        self.assertEqual(len(result.admitted), 3)
        self.assertEqual(len(result.aggregate_residuals), 1)
        residual = result.aggregate_residuals[0]
        self.assertEqual(residual.amount, Decimal("200.00"))
        self.assertIsNone(residual.category)
        self.assertEqual(residual.role, ExpenseRole.UNKNOWN)
        self.assertEqual(residual.classification_confidence, "unknown")

    def test_accounting_observation_in_closing_cash_slice_is_visible_but_not_double_counted(self):
        accounting = [
            expense(
                "acct:1",
                "250",
                category="shop_rent",
                confidence="strong",
                role=ExpenseRole.BRANCH,
                source_ref="busy:voucher:1",
            )
        ]
        aggregate = [expense("closing:1", "500")]

        result = reconcile_expense_evidence((), accounting, aggregate)

        self.assertEqual(sum((row.amount for row in result.admitted), Decimal("0")), Decimal("500.00"))
        self.assertEqual(result.excluded_supporting, tuple(accounting))
        self.assertEqual(result.excluded_supporting_amount, Decimal("250.00"))

    def test_accounting_observation_is_admitted_when_no_closing_cash_overlap_exists(self):
        accounting = [
            expense(
                "acct:2",
                "1250",
                category="shop_rent",
                confidence="strong",
                role=ExpenseRole.BRANCH,
            )
        ]

        result = reconcile_expense_evidence((), accounting, ())

        self.assertEqual(result.admitted, tuple(accounting))
        self.assertEqual(result.excluded_supporting, ())
        self.assertEqual(result.aggregate_residuals, ())

    def test_entry_total_above_aggregate_is_flagged_without_negative_residual_or_suppression(self):
        entries = [expense("cash:1", "400"), expense("cash:2", "250")]
        aggregate = [expense("closing:1", "500")]

        result = reconcile_expense_evidence(entries, (), aggregate)

        self.assertEqual(result.admitted, tuple(entries))
        self.assertEqual(result.aggregate_residuals, ())
        self.assertEqual(len(result.inconsistencies), 1)
        issue = result.inconsistencies[0]
        self.assertEqual(issue["type"], "closing_cash_entry_total_exceeds_aggregate")
        self.assertEqual(issue["difference"], Decimal("150.00"))

    def test_unallocated_accounting_observation_is_not_assumed_to_overlap_branch_closing(self):
        accounting = [expense("acct:u", "100", branch=None, category="audit", confidence="exact", role=ExpenseRole.CENTRAL)]
        aggregate = [expense("closing:1", "500", branch="KVR")]

        result = reconcile_expense_evidence((), accounting, aggregate)

        self.assertIn(accounting[0], result.admitted)
        self.assertEqual(result.excluded_supporting, ())


if __name__ == "__main__":
    unittest.main()
