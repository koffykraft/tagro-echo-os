from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HANDLER = ROOT / "src/aws_runtime/import_handler.py"
TEMPLATE = ROOT / "architecture/aws/nonprod-runtime-template.yaml"


class Wo0012PrivateImportHandlerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.handler = HANDLER.read_text(encoding="utf-8").lower()
        cls.template = TEMPLATE.read_text(encoding="utf-8").lower()

    def test_explicit_confirmation_required(self) -> None:
        self.assertIn("import_nonprod_observations_v0_1", self.handler)
        self.assertIn("explicit_confirmation_required", self.handler)

    def test_handler_uses_observation_writer_only(self) -> None:
        self.assertIn("record_observations", self.handler)
        self.assertIn('"canonical_write": false', self.handler)
        for forbidden in (
            "insert into branches",
            "insert into users",
            "insert into principals",
            "insert into enterprise_memberships",
        ):
            self.assertNotIn(forbidden, self.handler)

    def test_ingest_lambda_has_no_api_event_source(self) -> None:
        self.assertIn("echoobservationimportfunction:", self.template)
        block = self.template.split("echoobservationimportfunction:", 1)[1]
        block = block.split("outputs:", 1)[0]
        self.assertNotIn("events:", block)
        self.assertIn("src.aws_runtime.import_handler.lambda_handler", block)

    def test_observation_limit_is_bounded(self) -> None:
        self.assertIn("max_observations = 500", self.handler)
        self.assertIn("observation_limit_exceeded", self.handler)


if __name__ == "__main__":
    unittest.main()
