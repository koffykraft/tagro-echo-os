from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal

from src.financial.health import ExpenseRole
from src.financial.prism import AdaptivePrism, PrismCandidate, PrismDepth, PrismObservation
from src.financial.prism_health_bridge import prism_expense_evidence


class PrismHealthBridgeTests(unittest.TestCase):
    def observation(self):
        return PrismObservation(
            observation_id="obs-1",
            source_kind="bank_statement",
            source_ref="bank:stmt:10",
            amount=Decimal("18000"),
            direction="debit",
            branch="KVR",
            narration="salary",
        )

    def bridge(self, result):
        return prism_expense_evidence(
            result=result,
            expense_id="expense-1",
            expense_date=date(2026, 8, 21),
            amount=Decimal("18000"),
            branch="KVR",
            source_ref="bank:stmt:10",
        )

    def test_business_meaning_alone_cannot_affect_pnl(self):
        result = AdaptivePrism().resolve(
            self.observation(),
            (PrismCandidate("SALARY", 0.99, PrismDepth.BUSINESS_MEANING, "known salary wording"),),
        )
        self.assertIsNone(self.bridge(result))

    def test_low_confidence_consequence_is_stepped_back_and_cannot_affect_pnl(self):
        result = AdaptivePrism().resolve(
            self.observation(),
            (PrismCandidate("BRANCH_OPERATING_EXPENSE", 0.88, PrismDepth.FINANCIAL_CONSEQUENCE, "single-source suggestion"),),
        )
        self.assertIsNone(self.bridge(result))

    def test_strong_supported_consequence_can_feed_financial_health(self):
        result = AdaptivePrism().resolve(
            self.observation(),
            (PrismCandidate("BRANCH_OPERATING_EXPENSE", 0.97, PrismDepth.FINANCIAL_CONSEQUENCE, "owner-approved corroborated rule"),),
        )
        evidence = self.bridge(result)
        self.assertIsNotNone(evidence)
        self.assertEqual(evidence.role, ExpenseRole.BRANCH)
        self.assertEqual(evidence.amount, Decimal("18000"))

    def test_internal_transfer_is_preserved_but_not_operating_expense(self):
        result = AdaptivePrism().resolve(
            self.observation(),
            (PrismCandidate("NO_PNL_INTERNAL_TRANSFER", 0.98, PrismDepth.FINANCIAL_CONSEQUENCE, "paired bank/cash evidence"),),
        )
        evidence = self.bridge(result)
        self.assertIsNotNone(evidence)
        self.assertEqual(evidence.role, ExpenseRole.INTERNAL_TRANSFER)

    def test_unknown_consequence_label_does_not_enter_financial_health(self):
        result = AdaptivePrism().resolve(
            self.observation(),
            (PrismCandidate("SOMETHING_NEW", 0.99, PrismDepth.FINANCIAL_CONSEQUENCE, "not governed"),),
        )
        self.assertIsNone(self.bridge(result))


if __name__ == "__main__":
    unittest.main()
