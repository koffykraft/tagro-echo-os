from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IMPORTER = ROOT / "src/aws_runtime/import_reconciliation.py"
EXPORTER = ROOT / "scripts/export_financial_projection_observations.py"
LOADER = ROOT / "scripts/import_financial_projection_observations.ps1"
ON_CALL = ROOT / "src/aws_runtime/on_call_runtime.py"


class FinancialObservationBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.importer = IMPORTER.read_text(encoding="utf-8")
        cls.exporter = EXPORTER.read_text(encoding="utf-8")
        cls.loader = LOADER.read_text(encoding="utf-8")
        cls.on_call = ON_CALL.read_text(encoding="utf-8")

    def test_financial_dimensions_are_explicit_and_supporting_only(self):
        self.assertIn('"financial_sale_line"', self.importer)
        self.assertIn('"financial_snapshot"', self.importer)
        self.assertIn('"financial.sale_cost_evidence"', self.importer)
        self.assertIn('"financial.export_manifest"', self.importer)
        self.assertIn("never inserts or updates canonical sales", self.importer)

    def test_exporter_reuses_verified_busy_voucher_semantics(self):
        self.assertIn("v.vch_type=9", self.exporter)
        self.assertIn("v.vch_type=2", self.exporter)
        self.assertIn("coalesce(v.cancelled,0)=0", self.exporter)
        self.assertIn("coalesce(v.vch_cancelled,0)=0", self.exporter)
        self.assertIn("[:4]", self.exporter)
        self.assertIn('"purchase_references"', self.exporter)
        self.assertIn('"canonical_write": False', self.exporter)

    def test_exporter_emits_manifest_separately_from_chunks(self):
        self.assertIn('"manifest-package.json"', self.exporter)
        self.assertIn('"chunk_files"', self.exporter)
        self.assertIn('"run_hash"', self.exporter)
        self.assertLess(self.exporter.index('path.write_text(json.dumps(package'), self.exporter.index('manifest_path.write_text'))

    def test_loader_preflights_account_and_imports_manifest_last(self):
        self.assertIn("get-caller-identity", self.loader)
        self.assertIn("272037674623", self.loader)
        self.assertIn("canonical_write=false", self.loader.lower())
        chunk_pos = self.loader.index("foreach ($name in $chunks)")
        manifest_pos = self.loader.index("Import-Package $manifestPackagePath 'manifest-final'")
        self.assertLess(chunk_pos, manifest_pos)

    def test_on_call_uses_only_complete_manifest_run(self):
        self.assertIn("financial.export_manifest", self.on_call)
        self.assertIn("incomplete_financial_observation_run", self.on_call)
        self.assertIn("if len(rows) != expected", self.on_call)
        self.assertIn("warehouse_financial_projection_included", self.on_call)
        self.assertIn("busy_booking_reconciliation_required", self.on_call)

    def test_bridge_does_not_write_canonical_business_tables(self):
        combined = (self.importer + self.exporter + self.loader + self.on_call).lower()
        for forbidden in (
            "insert into sale_headers",
            "insert into sale_lines",
            "insert into purchase_headers",
            "insert into purchase_lines",
            "update sale_headers",
            "update purchase_headers",
        ):
            self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main()
