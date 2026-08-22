from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal

from src.financial.health import (
    CostConfidence,
    ExpenseEvidence,
    ExpenseRole,
    FinancialHealthEngine,
    PurchasePriceEvidence,
    SaleLineEvidence,
)


class FinancialHealthConfidenceV02Tests(unittest.TestCase):
    def setUp(self):
        self.engine = FinancialHealthEngine()

    def test_volatile_recent_purchase_band_is_weak_not_strong(self):
        sale = SaleLineEvidence("S-VOL", date(2026, 8, 20), "KVR", "ITEM", Decimal("1"), Decimal("500"))
        purchases = (
            PurchasePriceEvidence("ITEM", date(2026, 8, 19), Decimal("100"), "KVR", source_ref="P1"),
            PurchasePriceEvidence("ITEM", date(2026, 8, 18), Decimal("145"), "KVR", source_ref="P2"),
            PurchasePriceEvidence("ITEM", date(2026, 8, 17), Decimal("95"), "KVR", source_ref="P3"),
        )
        result = self.engine.project_sale(sale, purchases)
        self.assertEqual(result.cost.unit_cost, Decimal("100.00"))
        self.assertEqual(result.cost.confidence, CostConfidence.WEAK)
        self.assertEqual(result.cost.recent_reference_count, 3)
        self.assertGreater(result.cost.recent_dispersion_pct, Decimal("30"))
        self.assertIn("volatile", result.cost.confidence_reason)

    def test_prior_fy_fallback_is_always_weak_even_with_many_prices(self):
        sale = SaleLineEvidence("S-OLD", date(2026, 5, 20), "KVR", "ITEM", Decimal("1"), Decimal("500"))
        purchases = tuple(
            PurchasePriceEvidence("ITEM", d, c, "KVR", source_ref=f"P{i}")
            for i, (d, c) in enumerate((
                (date(2026, 3, 31), Decimal("100")),
                (date(2026, 3, 20), Decimal("101")),
                (date(2026, 3, 10), Decimal("99")),
            ), 1)
        )
        result = self.engine.project_sale(sale, purchases)
        self.assertEqual(result.cost.confidence, CostConfidence.WEAK)
        self.assertIn("prior financial year", result.cost.confidence_reason)

    def test_contribution_layers_keep_direct_branch_and_central_costs_distinct(self):
        sale = SaleLineEvidence(
            "S1", date(2026, 8, 20), "KVR", "ITEM", Decimal("1"), Decimal("500"),
            explicit_cost_before_tax=Decimal("300"),
        )
        expenses = (
            ExpenseEvidence("D", date(2026, 8, 20), Decimal("20"), "KVR", "delivery", "D", "exact", ExpenseRole.DIRECT),
            ExpenseEvidence("B", date(2026, 8, 20), Decimal("30"), "KVR", "rent", "B", "exact", ExpenseRole.BRANCH),
            ExpenseEvidence("C", date(2026, 8, 20), Decimal("40"), None, "office", "C", "exact", ExpenseRole.CENTRAL),
            ExpenseEvidence("F", date(2026, 8, 20), Decimal("10"), None, "interest", "F", "exact", ExpenseRole.FINANCE),
        )
        summary = self.engine.summarize((sale,), (), expenses)
        self.assertEqual(summary["estimated_gross_profit_known"], Decimal("200.00"))
        self.assertEqual(summary["estimated_contribution_known"], Decimal("180.00"))
        self.assertEqual(summary["estimated_branch_contribution_known"], Decimal("150.00"))
        self.assertEqual(summary["estimated_operating_profit_known"], Decimal("110.00"))
        self.assertEqual(summary["estimated_profit_after_finance_known"], Decimal("100.00"))


if __name__ == "__main__":
    unittest.main()
