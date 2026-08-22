from __future__ import annotations

import importlib.util
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPORTER = ROOT / "scripts/export_financial_projection_observations.py"


spec = importlib.util.spec_from_file_location("financial_exporter", EXPORTER)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


class FinancialExportConfidenceAlignmentTests(unittest.TestCase):
    @staticmethod
    def rows(*costs: str):
        return [{"cost_before_tax": Decimal(cost)} for cost in costs]

    def test_strong_needs_three_coherent_same_fy_references(self):
        confidence, dispersion, reason = module.classify_cost_confidence(
            self.rows("100", "96", "102"),
            selected_fy=2026,
            sale_fy=2026,
        )
        self.assertEqual(confidence, "strong")
        self.assertLessEqual(dispersion, Decimal("30.00"))
        self.assertIn("sale financial year", reason)

    def test_three_prior_fy_references_are_weak_not_strong(self):
        confidence, _, reason = module.classify_cost_confidence(
            self.rows("100", "98", "101"),
            selected_fy=2025,
            sale_fy=2026,
        )
        self.assertEqual(confidence, "weak")
        self.assertIn("prior financial year", reason)

    def test_volatile_same_fy_band_is_weak(self):
        confidence, dispersion, reason = module.classify_cost_confidence(
            self.rows("100", "60", "140"),
            selected_fy=2026,
            sale_fy=2026,
        )
        self.assertEqual(confidence, "weak")
        self.assertGreater(dispersion, Decimal("30.00"))
        self.assertIn("volatile", reason)

    def test_no_reference_is_unknown(self):
        confidence, dispersion, reason = module.classify_cost_confidence(
            [],
            selected_fy=None,
            sale_fy=2026,
        )
        self.assertEqual(confidence, "unknown")
        self.assertIsNone(dispersion)
        self.assertIn("no qualifying", reason)

    def test_exact_is_reserved_not_inferred_by_historical_export(self):
        text = EXPORTER.read_text(encoding="utf-8")
        normalized = " ".join(text.split())
        self.assertIn('cost_counts = {"exact": 0, "strong": 0, "weak": 0, "unknown": 0}', text)
        self.assertIn("Exact is reserved for deterministic sale-linked acquisition cost", normalized)
        self.assertNotIn('return "exact"', text)


if __name__ == "__main__":
    unittest.main()
