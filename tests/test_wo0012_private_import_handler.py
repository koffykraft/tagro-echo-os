from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HANDLER = ROOT / "src/aws_runtime/import_handler.py"
TEMPLATE = ROOT / "architecture/aws/nonprod-runtime-template.yaml"


class Wo0012PrivateImportHandlerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.handler = HANDLER.read_text(encoding="utf-8")
        cls.lower = cls.handler.lower()
        cls.template = TEMPLATE.read_text(encoding="utf-8").lower()

    def test_explicit_confirmation_required(self) -> None:
        self.assertIn('CONFIRMATION = "SYNC_OPERATIONAL_TWIN_V1"', self.handler)
        self.assertIn("explicit_confirmation_required", self.handler)
        self.assertIn('event.get("confirm") != CONFIRMATION', self.handler)

    def test_handler_preserves_source_and_planar_ingestion_lanes(self) -> None:
        self.assertIn("sync_source_records", self.handler)
        self.assertIn("sync_planar_records", self.handler)
        self.assertIn("tagro.planar-export/1", self.handler)
        self.assertIn('"planar_preserved": True', self.handler)
        self.assertIn('"database_primary": True', self.handler)
        for forbidden in (
            "insert into branches",
            "insert into users",
            "insert into principals",
            "insert into enterprise_memberships",
            "insert into sale_headers",
            "insert into stock_movements",
        ):
            self.assertNotIn(forbidden, self.lower)

    def test_ingest_lambda_has_no_api_event_source(self) -> None:
        self.assertIn("echoobservationimportfunction:", self.template)
        block = self.template.split("echoobservationimportfunction:", 1)[1]
        block = block.split("outputs:", 1)[0]
        self.assertNotIn("events:", block)
        self.assertIn("src.aws_runtime.import_handler.lambda_handler", block)

    def test_record_limit_is_bounded(self) -> None:
        self.assertIn("MAX_RECORDS = 1000", self.handler)
        self.assertIn("record_limit_exceeded", self.handler)
        self.assertIn("len(records) > MAX_RECORDS", self.handler)


if __name__ == "__main__":
    unittest.main()
