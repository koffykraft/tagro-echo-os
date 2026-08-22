from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPORTER = ROOT / "src/aws_runtime/import_reconciliation.py"
HANDLER = ROOT / "src/aws_runtime/handler.py"
TEMPLATE = ROOT / "architecture/aws/nonprod-runtime-template.yaml"


class Wo0012ImportReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.importer = IMPORTER.read_text(encoding="utf-8").lower()
        cls.handler = HANDLER.read_text(encoding="utf-8").lower()
        cls.template = TEMPLATE.read_text(encoding="utf-8").lower()

    def test_ingestion_writes_only_observation_layer(self) -> None:
        self.assertIn("insert into import_sources", self.importer)
        self.assertIn("insert into import_observations", self.importer)
        for forbidden in (
            "insert into branches",
            "insert into users",
            "insert into principals",
            "insert into enterprise_memberships",
            "update branches",
            "update users",
        ):
            self.assertNotIn(forbidden, self.importer)

    def test_observation_dimensions_are_explicitly_limited(self) -> None:
        for dimension in (
            '"branch.code"',
            '"branch.name"',
            '"branch.operational_state"',
            '"person.name"',
            '"person.branch_code"',
            '"person.role"',
            '"person.phone"',
            '"person.email"',
            '"person.active_state"',
        ):
            self.assertIn(dimension, self.importer)

    def test_reconciliation_route_requires_owner_authority(self) -> None:
        self.assertIn('raw_path == "/import-reconciliation"', self.handler)
        self.assertIn('role_code") == "owner"', self.handler)
        self.assertIn("owner_authority_required", self.handler)
        self.assertIn("enterprise_selection_required", self.handler)

    def test_reconciliation_route_is_jwt_protected_in_sam(self) -> None:
        self.assertIn("path: /import-reconciliation", self.template)
        block = self.template.split("importreconciliation:", 1)[1]
        block = block.split("echoschemamigrationfunction:", 1)[0]
        self.assertNotIn("authorizer: none", block)

    def test_readback_is_separate_from_ingestion(self) -> None:
        self.assertIn("def reconciliation_readback", self.importer)
        self.assertIn("def record_observations", self.importer)
        self.assertIn("observation presence", (ROOT / "schemas/business/platform_import_observations_v0_2_3.sql").read_text(encoding="utf-8").lower())


if __name__ == "__main__":
    unittest.main()
