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
            amount=Decimal("25000"),
            direction="debit",
            branch="KVR",
            narration="TRANSFER",
            business_date="2026-08-21",
        )

    def bridge(self, result):
        return prism_expense_evidence(
            result=result,
            expense_id="expense-1",
            expense_date=date(2026, 8, 21),
            amount=Decimal("25000"),
            branch="KVR",
            source_ref="bank:stmt:10",
        )

    def test_business_meaning_alone_never_becomes_expense(self):
        result = AdaptivePrism().resolve(
            self.observation(),
            (PrismCandidate("SALARY", 0.98, PrismDepth.BUSINESS_MEANING, "owner-approved wording"),),
        )
        self.assertIsNone(self.bridge(result))

    def test_low_confidence_consequence_is_not_admitted(self):
        result = AdaptivePrism(auto_consequence_threshold=0.80).resolve(
            self.observation(),
            (PrismCandidate("BRANCH_OPERATING_EXPENSE", 0.88, PrismDepth.FINANCIAL_CONSEQUENCE, "single source"),),
        )
        self.assertIsNone(self.bridge(result))

    def test_supported_operating_consequence_is_admitted(self):
        result = AdaptivePrism().resolve(
            self.observation(),
            (PrismCandidate("BRANCH_OPERATING_EXPENSE", 0.97, PrismDepth.FINANCIAL_CONSEQUENCE, "reconciled owner rule"),),
        )
        evidence = self.bridge(result)
        self.assertIsNotNone(evidence)
        self.assertEqual(evidence.role, ExpenseRole.BRANCH)
        self.assertEqual(evidence.classification_confidence, "prism:0.97")

    def test_internal_transfer_is_visible_but_not_operating_expense(self):
        result = AdaptivePrism().resolve(
            self.observation(),
            (PrismCandidate("NO_PNL_INTERNAL_TRANSFER", 0.99, PrismDepth.FINANCIAL_CONSEQUENCE, "paired bank/cash references"),),
        )
        evidence = self.bridge(result)
        self.assertIsNotNone(evidence)
        self.assertEqual(evidence.role, ExpenseRole.INTERNAL_TRANSFER)


if __name__ == "__main__":
    unittest.main()
