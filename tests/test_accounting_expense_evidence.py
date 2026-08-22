from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal

from src.financial.accounting_evidence import AccountingExpenseObservation, accounting_expense_evidence
from src.financial.health import ExpenseRole


class AccountingExpenseEvidenceTests(unittest.TestCase):
    def test_partial_accounting_classification_is_downgraded_to_unknown(self):
        row = AccountingExpenseObservation(
            observation_id="A1",
            business_date=date(2026, 8, 21),
            amount=Decimal("1250"),
            branch="KVR",
            category="rent",
            role=None,
            classification_confidence="exact",
            source_ref="busy:voucher:1",
        )
        evidence = accounting_expense_evidence(row)
        self.assertIsNotNone(evidence)
        self.assertIsNone(evidence.category)
        self.assertEqual(evidence.role, ExpenseRole.UNKNOWN)
        self.assertEqual(evidence.classification_confidence, "unknown")

    def test_complete_explicit_accounting_classification_is_preserved(self):
        row = AccountingExpenseObservation(
            observation_id="A2",
            business_date=date(2026, 8, 21),
            amount=Decimal("3000"),
            branch="KVR",
            category="shop_rent",
            role="branch_operating_expense",
            classification_confidence="strong",
            source_ref="busy:voucher:2",
        )
        evidence = accounting_expense_evidence(row)
        self.assertEqual(evidence.category, "shop_rent")
        self.assertEqual(evidence.role, ExpenseRole.BRANCH)
        self.assertEqual(evidence.classification_confidence, "strong")

    def test_exact_id_override_is_authoritative_but_invalid_override_falls_back_unknown(self):
        row = AccountingExpenseObservation(
            observation_id="A3",
            business_date=date(2026, 8, 21),
            amount=Decimal("500"),
        )
        evidence = accounting_expense_evidence(
            row,
            {"A3": ("courier", ExpenseRole.BRANCH, "exact")},
        )
        self.assertEqual(evidence.category, "courier")
        self.assertEqual(evidence.role, ExpenseRole.BRANCH)
        self.assertEqual(evidence.classification_confidence, "exact")

        invalid = accounting_expense_evidence(
            row,
            {"A3": ("courier", ExpenseRole.BRANCH, "invented")},
        )
        self.assertIsNone(invalid.category)
        self.assertEqual(invalid.role, ExpenseRole.UNKNOWN)
        self.assertEqual(invalid.classification_confidence, "unknown")

    def test_non_positive_observation_is_not_expense_evidence(self):
        row = AccountingExpenseObservation(
            observation_id="A4",
            business_date=date(2026, 8, 21),
            amount=Decimal("0"),
        )
        self.assertIsNone(accounting_expense_evidence(row))


if __name__ == "__main__":
    unittest.main()
