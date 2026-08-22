from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class StockObservationRuntimeContractTests(unittest.TestCase):
    def test_count_runtime_preserves_unknown_instead_of_zero(self):
        text = (ROOT / "src/aws_runtime/operational_runtime.py").read_text(encoding="utf-8")
        self.assertIn("system_qty = Decimal(str(stock[0])) if stock else None", text)
        self.assertIn("variance = counted_qty - system_qty if system_qty is not None else None", text)
        self.assertNotIn('system_qty = Decimal(str(stock[0])) if stock else Decimal("0")', text)
        self.assertIn('"system_qty_known": system_qty is not None', text)

    def test_every_realtime_count_is_append_only_observation_and_provisional(self):
        text = (ROOT / "src/aws_runtime/operational_runtime.py").read_text(encoding="utf-8")
        self.assertIn("echo-stock-observation", text)
        self.assertIn("insert into stock_count_observations", text)
        self.assertIn("'staff_realtime_count'", text)
        self.assertIn("provisional_eligible", text)
        self.assertIn('"provisional_truth_state": "provisional_count"', text)
        self.assertIn("idempotency_key was reused with changed stock count payload", text)

    def test_legacy_variance_summary_is_not_written_when_canonical_is_unknown(self):
        text = (ROOT / "src/aws_runtime/operational_runtime.py").read_text(encoding="utf-8")
        marker = "if system_qty is not None:"
        self.assertIn(marker, text)
        after = text.split(marker, 1)[1]
        self.assertIn("insert into stock_count_lines", after)
        self.assertIn("UNKNOWN and must never be encoded as numeric zero", text)

    def test_migration_keeps_count_and_movement_planes_separate(self):
        sql = (ROOT / "schemas/business/stock_observation_planes_v0_4.sql").read_text(encoding="utf-8").lower()
        self.assertIn("canonical_system_qty numeric(14,3)", sql)
        self.assertIn("variance_to_canonical numeric(14,3)", sql)
        self.assertIn("create view provisional_stock_position", sql)
        self.assertNotIn("insert into stock_movements", sql)
        self.assertIn("cannot create stock movements", sql)


if __name__ == "__main__":
    unittest.main()
