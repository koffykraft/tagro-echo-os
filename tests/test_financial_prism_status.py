from __future__ import annotations

import unittest
from decimal import Decimal

from src.financial.prism import AdaptivePrism, PrismCandidate, PrismDepth, PrismObservation
from src.financial.prism_status import PrismStatusRow, build_prism_status


class PrismStatusTests(unittest.TestCase):
    def obs(self, oid: str, amount: str = "1000"):
        return PrismObservation(
            observation_id=oid,
            source_kind="bank_statement",
            source_ref=f"bank:{oid}",
            amount=Decimal(amount),
            direction="debit",
            branch="KVR",
            narration="test",
            business_date="2026-08-20",
        )

    def test_unresolved_amount_is_not_treated_as_resolved_zero(self):
        obs = self.obs("u", "2500")
        result = AdaptivePrism().resolve(
            obs,
            (PrismCandidate("SALARY", 0.70, PrismDepth.BUSINESS_MEANING, "weak rule"),),
        )
        status = build_prism_status((PrismStatusRow(obs, result),))
        self.assertEqual(status["unresolved_amount"], Decimal("2500"))
        self.assertEqual(status["financial_consequence_resolved_amount"], Decimal("0"))

    def test_supported_consequence_contributes_to_resolution_coverage(self):
        obs = self.obs("r", "4000")
        result = AdaptivePrism().resolve(
            obs,
            (PrismCandidate("BRANCH_OPERATING_EXPENSE", 0.97, PrismDepth.FINANCIAL_CONSEQUENCE, "governed evidence"),),
        )
        status = build_prism_status((PrismStatusRow(obs, result),))
        self.assertEqual(status["financial_consequence_resolved_count"], 1)
        self.assertEqual(status["financial_consequence_amount_coverage_pct"], Decimal("100.00"))

    def test_tight_split_enters_review_queue(self):
        obs = self.obs("t")
        result = AdaptivePrism(descend_threshold=0.5).resolve(
            obs,
            (
                PrismCandidate("SUPPLIER_PAYMENT", 0.70, PrismDepth.BUSINESS_MEANING, "a"),
                PrismCandidate("INTERNAL_TRANSFER", 0.66, PrismDepth.BUSINESS_MEANING, "b"),
            ),
        )
        status = build_prism_status((PrismStatusRow(obs, result),))
        self.assertEqual(status["tight_split_count"], 1)
        self.assertEqual(len(status["review_queue"]), 1)
        self.assertEqual(len(status["review_queue"][0]["candidates"]), 2)


if __name__ == "__main__":
    unittest.main()
