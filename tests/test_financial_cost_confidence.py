from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal

from src.financial.cost_confidence import confidence_breakdown
from src.financial.health import FinancialHealthEngine, PurchasePriceEvidence, SaleLineEvidence


class FinancialCostConfidenceTests(unittest.TestCase):
    def test_revenue_weighted_breakdown_prevents_line_count_false_comfort(self):
        engine = FinancialHealthEngine()
        sales = [
            SaleLineEvidence(
                "EXACT",
                date(2026, 8, 20),
                "KVR",
                "A",
                Decimal("1"),
                Decimal("100"),
                explicit_cost_before_tax=Decimal("60"),
                source_ref="sale:exact",
            ),
            SaleLineEvidence(
                "STRONG",
                date(2026, 8, 20),
                "KVR",
                "B",
                Decimal("1"),
                Decimal("200"),
            ),
            SaleLineEvidence(
                "UNKNOWN",
                date(2026, 8, 20),
                "KVR",
                "C",
                Decimal("1"),
                Decimal("700"),
            ),
        ]
        purchases = [
            PurchasePriceEvidence("B", date(2026, 8, 19), Decimal("100"), "KVR", source_ref="p1"),
            PurchasePriceEvidence("B", date(2026, 8, 10), Decimal("101"), "KVR", source_ref="p2"),
            PurchasePriceEvidence("B", date(2026, 8, 1), Decimal("99"), "KVR", source_ref="p3"),
        ]
        projections = [engine.project_sale(sale, purchases) for sale in sales]
        result = confidence_breakdown(projections)

        self.assertEqual(result["sales_before_tax"], Decimal("1000.00"))
        self.assertEqual(result["exact_or_strong_sales_before_tax"], Decimal("300.00"))
        self.assertEqual(result["weak_or_unknown_sales_before_tax"], Decimal("700.00"))
        self.assertEqual(result["exact_or_strong_revenue_coverage_pct"], Decimal("30.00"))
        self.assertEqual(result["weak_or_unknown_revenue_exposure_pct"], Decimal("70.00"))
        self.assertEqual(result["by_confidence"]["exact"]["line_count"], 1)
        self.assertEqual(result["by_confidence"]["strong"]["line_count"], 1)
        self.assertEqual(result["by_confidence"]["unknown"]["line_count"], 1)
        self.assertEqual(result["by_confidence"]["unknown"]["sales_before_tax"], Decimal("700.00"))

    def test_zero_revenue_has_zero_percentages(self):
        self.assertEqual(
            confidence_breakdown(()),
            {
                "sales_before_tax": Decimal("0.00"),
                "exact_or_strong_sales_before_tax": Decimal("0.00"),
                "weak_or_unknown_sales_before_tax": Decimal("0.00"),
                "exact_or_strong_revenue_coverage_pct": Decimal("0.00"),
                "weak_or_unknown_revenue_exposure_pct": Decimal("0.00"),
                "by_confidence": {
                    "exact": {"line_count": 0, "sales_before_tax": Decimal("0.00"), "sales_share_pct": Decimal("0.00"), "estimated_cogs": Decimal("0.00"), "estimated_gross_profit": Decimal("0.00"), "source_refs": ()},
                    "strong": {"line_count": 0, "sales_before_tax": Decimal("0.00"), "sales_share_pct": Decimal("0.00"), "estimated_cogs": Decimal("0.00"), "estimated_gross_profit": Decimal("0.00"), "source_refs": ()},
                    "weak": {"line_count": 0, "sales_before_tax": Decimal("0.00"), "sales_share_pct": Decimal("0.00"), "estimated_cogs": Decimal("0.00"), "estimated_gross_profit": Decimal("0.00"), "source_refs": ()},
                    "unknown": {"line_count": 0, "sales_before_tax": Decimal("0.00"), "sales_share_pct": Decimal("0.00"), "estimated_cogs": Decimal("0.00"), "estimated_gross_profit": Decimal("0.00"), "source_refs": ()},
                },
            },
        )


if __name__ == "__main__":
    unittest.main()
