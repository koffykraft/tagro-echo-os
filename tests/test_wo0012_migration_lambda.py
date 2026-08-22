from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Wo0012MigrationLambdaTests(unittest.TestCase):
    def test_migration_lambda_has_no_api_or_event_source(self) -> None:
        template = (ROOT / "architecture/aws/nonprod-runtime-template.yaml").read_text(encoding="utf-8")
        block = template.split("EchoSchemaMigrationFunction:", 1)[1].split("Outputs:", 1)[0]
        self.assertNotIn("Events:", block)
        self.assertNotIn("Type: HttpApi", block)
        self.assertIn("FunctionName: echo-nonprod-schema-migrate", block)

    def test_migration_requires_current_explicit_confirmation(self) -> None:
        handler = (ROOT / "src/aws_runtime/migration_handler.py").read_text(encoding="utf-8")
        self.assertIn('CONFIRMATION = "APPLY_NONPROD_V0_3"', handler)
        self.assertIn('event.get("confirm") != CONFIRMATION', handler)
        self.assertIn('"migration_set": "nonprod_v0_3"', handler)

    def test_build_packages_scripts_and_schemas(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertIn("cp -r scripts $(ARTIFACTS_DIR)/scripts", makefile)
        self.assertIn("cp -r schemas $(ARTIFACTS_DIR)/schemas", makefile)
        self.assertIn("build-EchoSchemaMigrationFunction", makefile)


if __name__ == "__main__":
    unittest.main()
