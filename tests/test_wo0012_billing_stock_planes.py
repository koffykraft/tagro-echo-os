from __future__ import annotations

import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from src.aws_runtime.billing_runtime import _stock_assessment

ROOT = Path(__file__).resolve().parents[1]


class BillingStockPlaneTests(unittest.TestCase):
    def test_unknown_provisional_stock_is_not_false_zero_shortage(self):
        lines = [{"product_id": "P1", "quantity": Decimal("1")}]
        provisional, shortages, unknown = _stock_assessment(lines, [])
        self.assertEqual({}, provisional)
        self.assertEqual([], shortages)
        self.assertEqual([lines[0]], unknown)

    def test_known_provisional_shortage_is_distinct_from_unknown(self):
        when = datetime(2026, 8, 21, tzinfo=timezone.utc)
        lines = [{"product_id": "P1", "quantity": Decimal("3")}]
        rows = [("P1", Decimal("2"), "obs-1", when, "provisional_count_plus_movements")]
        provisional, shortages, unknown = _stock_assessment(lines, rows)
        self.assertEqual(Decimal("2"), provisional["P1"]["quantity"])
        self.assertEqual([lines[0]], shortages)
        self.assertEqual([], unknown)

    def test_provisional_view_advances_count_with_later_movements(self):
        sql = (ROOT / "schemas/business/stock_observation_planes_v0_4.sql").read_text(encoding="utf-8").lower()
        self.assertIn("movement_delta_since_count", sql)
        self.assertIn("m.occurred_at>c.observed_at", sql)
        self.assertIn("c.counted_qty + coalesce(sum(m.quantity_delta),0) quantity", sql)
        self.assertIn("provisional_count_plus_movements", sql)

    def test_billing_uses_provisional_plane_and_preserves_canonical_as_comparison(self):
        text = (ROOT / "src/aws_runtime/billing_runtime.py").read_text(encoding="utf-8")
        self.assertIn("from provisional_stock_position", text)
        self.assertIn("partial_or_full_unknown", text)
        self.assertIn("canonical_movement_comparison", text)
        self.assertIn("known provisional stock shortage", text)
        self.assertNotIn('stock.get(row["product_id"], Decimal("0"))', text)


if __name__ == "__main__":
    unittest.main()
