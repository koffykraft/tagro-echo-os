from __future__ import annotations

import unittest
from decimal import Decimal

from src.aws_runtime.billing_runtime import _stock_assessment


class BillingStockPassageTests(unittest.TestCase):
    def test_duplicate_invoice_lines_are_aggregated_before_shortage_decision(self):
        lines = [
            {"product_id": "P1", "quantity": Decimal("3")},
            {"product_id": "P1", "quantity": Decimal("3")},
        ]
        provisional_rows = [("P1", Decimal("5"), "obs-1", "2026-08-21T10:00:00Z", "provisional_count_plus_movements")]
        _provisional, shortages, unknown = _stock_assessment(lines, provisional_rows)
        self.assertEqual([], unknown)
        self.assertEqual([{"product_id": "P1", "quantity": Decimal("6")}], shortages)

    def test_unknown_stock_is_unique_by_product_and_is_not_false_zero_shortage(self):
        lines = [
            {"product_id": "P1", "quantity": Decimal("1")},
            {"product_id": "P1", "quantity": Decimal("2")},
            {"product_id": "P2", "quantity": Decimal("1")},
        ]
        _provisional, shortages, unknown = _stock_assessment(lines, [])
        self.assertEqual([], shortages)
        self.assertEqual(
            [
                {"product_id": "P1", "quantity": Decimal("3")},
                {"product_id": "P2", "quantity": Decimal("1")},
            ],
            unknown,
        )

    def test_known_provisional_stock_passes_when_aggregate_demand_is_within_quantity(self):
        lines = [
            {"product_id": "P1", "quantity": Decimal("2")},
            {"product_id": "P1", "quantity": Decimal("3")},
        ]
        provisional_rows = [("P1", Decimal("5"), "obs-1", "2026-08-21T10:00:00Z", "provisional_count_plus_movements")]
        provisional, shortages, unknown = _stock_assessment(lines, provisional_rows)
        self.assertEqual(Decimal("5"), provisional["P1"]["quantity"])
        self.assertEqual([], shortages)
        self.assertEqual([], unknown)


if __name__ == "__main__":
    unittest.main()
