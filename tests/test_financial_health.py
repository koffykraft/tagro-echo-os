from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal

from src.financial.health import (
    CostConfidence,
    ExpenseEvidence,
    FinancialHealthEngine,
    PurchasePriceEvidence,
    SaleLineEvidence,
)


class FinancialHealthTests(unittest.TestCase):
    def setUp(self):
        self.engine = FinancialHealthEngine()

    def test_current_fy_purchase_history_preferred_and_four_price_grab(self):
        sale = SaleLineEvidence("S1", date(2026, 8, 20), "KVR", "ITEM1", Decimal("2"), Decimal("300"))
        purchases = [
            PurchasePriceEvidence("ITEM1", date(2026, 8, 19), Decimal("100"), "KVR", source_ref="P1"),
            PurchasePriceEvidence("ITEM1", date(2026, 8, 10), Decimal("110"), "KVR", source_ref="P2"),
            PurchasePriceEvidence("ITEM1", date(2026, 7, 1), Decimal("90"), "PKM", source_ref="P3"),
            PurchasePriceEvidence("ITEM1", date(2026, 6, 1), Decimal("105"), "NDD", source_ref="P4"),
            PurchasePriceEvidence("ITEM1", date(2025, 3, 20), Decimal("70"), "KVR", source_ref="OLD"),
        ]
        result = self.engine.project_sale(sale, purchases)
        self.assertEqual(result.cost.confidence, CostConfidence.STRONG)
        self.assertEqual(result.cost.reference_count, 4)
        self.assertEqual(result.cost.unit_cost, Decimal("102.50"))
        self.assertEqual(result.estimated_cogs, Decimal("205.00"))
        self.assertEqual(result.estimated_gross_profit, Decimal("95.00"))

    def test_falls_back_to_prior_financial_year(self):
        sale = SaleLineEvidence("S2", date(2026, 5, 1), "KVR", "ITEM2", Decimal("1"), Decimal("250"))
        purchases = [
            PurchasePriceEvidence("ITEM2", date(2026, 3, 31), Decimal("150"), "KVR", source_ref="P1"),
            PurchasePriceEvidence("ITEM2", date(2025, 12, 10), Decimal("140"), "KVR", source_ref="P2"),
        ]
        result = self.engine.project_sale(sale, purchases)
        self.assertEqual(result.cost.confidence, CostConfidence.STRONG)
        self.assertEqual(result.cost.unit_cost, Decimal("145.00"))
        self.assertIn("FY 2025-26", result.cost.policy)

    def test_stock_transfers_do_not_create_cost_reference(self):
        sale = SaleLineEvidence("S3", date(2026, 8, 1), "KVR", "ITEM3", Decimal("1"), Decimal("200"))
        purchases = [PurchasePriceEvidence("ITEM3", date(2026, 7, 1), Decimal("100"), is_stock_transfer=True)]
        result = self.engine.project_sale(sale, purchases)
        self.assertEqual(result.cost.confidence, CostConfidence.UNKNOWN)
        self.assertIsNone(result.estimated_gross_profit)

    def test_explicit_cost_is_exact(self):
        sale = SaleLineEvidence(
            "S4", date(2026, 8, 1), "KVR", "ITEM4", Decimal("3"), Decimal("600"), explicit_cost_before_tax=Decimal("120")
        )
        result = self.engine.project_sale(sale, ())
        self.assertEqual(result.cost.confidence, CostConfidence.EXACT)
        self.assertEqual(result.estimated_cogs, Decimal("360.00"))
        self.assertEqual(result.estimated_gross_profit, Decimal("240.00"))

    def test_unclassified_expenses_are_visible_but_not_guessed_into_operating_profit(self):
        sale = SaleLineEvidence(
            "S5", date(2026, 8, 1), "KVR", "ITEM5", Decimal("1"), Decimal("500"), explicit_cost_before_tax=Decimal("300")
        )
        expenses = [
            ExpenseEvidence("E1", date(2026, 8, 1), Decimal("50"), "KVR", "rent", "cash:E1", "exact"),
            ExpenseEvidence("E2", date(2026, 8, 1), Decimal("25"), "KVR", None, "bank:E2", "unknown"),
        ]
        summary = self.engine.summarize([sale], (), expenses)
        self.assertEqual(summary["estimated_gross_profit_known"], Decimal("200.00"))
        self.assertEqual(summary["classified_operating_expenses"], Decimal("50.00"))
        self.assertEqual(summary["estimated_operating_profit_known"], Decimal("150.00"))
        self.assertEqual(summary["unclassified_expenses"], Decimal("25.00"))


if __name__ == "__main__":
    unittest.main()
