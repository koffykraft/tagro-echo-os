from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPORTER = ROOT / "src/aws_runtime/import_reconciliation.py"


class LegacyStockCountImportContractTests(unittest.TestCase):
    def test_historical_stock_counts_are_supporting_observations_only(self):
        text = IMPORTER.read_text(encoding="utf-8")
        self.assertIn('"stock_count_line"', text)
        self.assertIn('"stock_count.observation"', text)
        self.assertIn("historical stock-count lines", text)
        self.assertIn("supporting evidence", text)
        self.assertNotIn("insert into stock_movements", text)
        self.assertNotIn("insert into stock_count_observations", text)

    def test_raw_name_and_candidate_match_are_not_promoted_to_identity_by_importer(self):
        text = IMPORTER.read_text(encoding="utf-8")
        self.assertIn("raw item naming and a proposed name match", text)
        self.assertIn("neither is canonical identity", text)
        self.assertIn("'raw_supporting'", text)


if __name__ == "__main__":
    unittest.main()
