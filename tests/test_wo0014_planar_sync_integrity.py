from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path("scripts/sync_planar_to_echo.py")


def load_module():
    spec = importlib.util.spec_from_file_location("sync_planar_to_echo", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load Planar sync script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PlanarSyncIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()
        cls.source = SCRIPT.read_text(encoding="utf-8")

    def test_logical_source_locator_is_machine_independent(self):
        self.assertEqual(
            self.module.DEFAULT_SOURCE_LOCATOR,
            "TAGRO_AWS_OS_WAREHOUSE/databases/planar.sqlite",
        )
        args = self.module.parser().parse_args(
            [
                "--database", "T:/warehouse/databases/planar.sqlite",
                "--manifest", "T:/warehouse/manifests/latest.json",
                "--checkpoint", "T:/runtime/state/checkpoint.json",
                "--enterprise-id", "enterprise-test",
            ]
        )
        self.assertEqual(args.source_locator, self.module.DEFAULT_SOURCE_LOCATOR)

    def test_file_digest_is_real_content_digest(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "planar.sqlite"
            path.write_bytes(b"planar-test")
            self.assertEqual(
                self.module.sha256_file(path),
                "1463a3b728685ec5b949fbebe2dfe77e878f1921b0671f8563485e0dc5bcfc68",
            )

    def test_manifest_digest_mismatch_is_a_hard_stop(self):
        self.assertIn("digest does not match warehouse manifest", self.source)
        self.assertIn("refusing to ingest a mixed/stale warehouse snapshot", self.source)

    def test_physical_path_is_provenance_not_source_identity(self):
        self.assertIn('"physical_database_path": str(database)', self.source)
        self.assertIn('"source_locator": source_locator', self.source)


if __name__ == "__main__":
    unittest.main()
