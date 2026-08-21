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


class FinancialHealthTests(unittest.TestCase):
    def setUp(self):
        self.engine = FinancialHealthEngine()

    def test_current_fy_same_branch_purchase_history_preferred_and_four_price_grab(self):
        sale = SaleLineEvidence("S1", date(2026, 8, 20), "KVR", "ITEM1", Decimal("2"), Decimal("300"))
        purchases = [
            PurchasePriceEvidence("ITEM1", date(2026, 8, 19), Decimal("100"), "KVR", source_ref="P1"),
            PurchasePriceEvidence("ITEM1", date(2026, 8, 10), Decimal("110"), "KVR", source_ref="P2"),
            PurchasePriceEvidence("ITEM1", date(2026, 7, 1), Decimal("90"), "KVR", source_ref="P3"),
            PurchasePriceEvidence("ITEM1", date(2026, 6, 1), Decimal("105"), "KVR", source_ref="P4"),
            PurchasePriceEvidence("ITEM1", date(2026, 5, 1), Decimal("80"), "PKM", source_ref="OTHER"),
        ]
        result = self.engine.project_sale(sale, purchases)
        self.assertEqual(result.cost.confidence, CostConfidence.STRONG)
        self.assertEqual(result.cost.reference_count, 4)
        self.assertEqual(result.cost.unit_cost, Decimal("102.50"))
        self.assertEqual(result.cost.reference_low, Decimal("90.00"))
        self.assertEqual(result.cost.reference_high, Decimal("110.00"))
        self.assertEqual(result.cost.latest_reference, Decimal("100.00"))
        self.assertEqual(result.cost.reference_scope, "same_branch")
        self.assertEqual(result.estimated_cogs, Decimal("205.00"))
        self.assertEqual(result.estimated_gross_profit, Decimal("95.00"))

    def test_falls_back_to_prior_financial_year(self):
        sale = SaleLineEvidence("S2", date(2026, 5, 1), "KVR", "ITEM2", Decimal("1"), Decimal("250"))
        purchases = [
            PurchasePriceEvidence("ITEM2", date(2026, 3, 31), Decimal("150"), "KVR", source_ref="P1"),
            PurchasePriceEvidence("ITEM2", date(2025, 12, 10), Decimal("140"), "KVR", source_ref="P2"),
        ]
        result = self.engine.project_sale(sale, purchases)
        self.assertEqual(result.cost.confidence, CostConfidence.WEAK)
        self.assertEqual(result.cost.unit_cost, Decimal("145.00"))
        self.assertIn("FY 2025-26", result.cost.policy)

    def test_enterprise_fallback_when_branch_has_no_purchase_history(self):
        sale = SaleLineEvidence("S2B", date(2026, 8, 1), "KVR", "ITEM2", Decimal("1"), Decimal("250"))
        purchases = [
            PurchasePriceEvidence("ITEM2", date(2026, 7, 1), Decimal("120"), "PKM", source_ref="P1"),
            PurchasePriceEvidence("ITEM2", date(2026, 6, 1), Decimal("130"), "NDD", source_ref="P2"),
            PurchasePriceEvidence("ITEM2", date(2026, 5, 1), Decimal("125"), "MDM", source_ref="P3"),
        ]
        result = self.engine.project_sale(sale, purchases)
        self.assertEqual(result.cost.reference_scope, "enterprise_fallback")
        self.assertEqual(result.cost.confidence, CostConfidence.STRONG)

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
            ExpenseEvidence("E1", date(2026, 8, 1), Decimal("50"), "KVR", "rent", "cash:E1", "exact", ExpenseRole.BRANCH),
            ExpenseEvidence("E2", date(2026, 8, 1), Decimal("25"), "KVR", None, "bank:E2", "unknown"),
        ]
        summary = self.engine.summarize([sale], (), expenses)
        self.assertEqual(summary["estimated_gross_profit_known"], Decimal("200.00"))
        self.assertEqual(summary["classified_operating_expenses"], Decimal("50.00"))
        self.assertEqual(summary["estimated_operating_profit_known"], Decimal("150.00"))
        self.assertEqual(summary["unclassified_expenses"], Decimal("25.00"))
        self.assertFalse(summary["projection_complete"])

    def test_partial_cost_coverage_is_explicit(self):
        sales = [
            SaleLineEvidence("K", date(2026, 8, 1), "KVR", "KNOWN", Decimal("1"), Decimal("500"), explicit_cost_before_tax=Decimal("300")),
            SaleLineEvidence("U", date(2026, 8, 1), "KVR", "UNKNOWN", Decimal("1"), Decimal("1000")),
        ]
        summary = self.engine.summarize(sales, ())
        self.assertEqual(summary["sales_before_tax"], Decimal("1500.00"))
        self.assertEqual(summary["sales_with_known_cost"], Decimal("500.00"))
        self.assertEqual(summary["sales_without_known_cost"], Decimal("1000.00"))
        self.assertEqual(summary["cost_coverage_pct"], Decimal("50.00"))
        self.assertEqual(summary["cost_revenue_coverage_pct"], Decimal("33.33"))
        self.assertFalse(summary["projection_complete"])

    def test_finance_cost_is_separate_from_operating_profit(self):
        sale = SaleLineEvidence("S6", date(2026, 8, 1), "KVR", "ITEM", Decimal("1"), Decimal("500"), explicit_cost_before_tax=Decimal("300"))
        expenses = [
            ExpenseEvidence("R", date(2026, 8, 1), Decimal("50"), "KVR", "rent", "cash:R", "exact", ExpenseRole.BRANCH),
            ExpenseEvidence("I", date(2026, 8, 1), Decimal("20"), None, "interest", "bank:I", "exact", ExpenseRole.FINANCE),
        ]
        summary = self.engine.summarize([sale], (), expenses)
        self.assertEqual(summary["estimated_operating_profit_known"], Decimal("150.00"))
        self.assertEqual(summary["estimated_profit_after_finance_known"], Decimal("130.00"))


if __name__ == "__main__":
    unittest.main()
