from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "schemas" / "migrations" / "nonprod_v0_1_manifest.json"


def git_blob_sha(content: bytes) -> str:
    header = f"blob {len(content)}\0".encode("utf-8")
    return hashlib.sha1(header + content).hexdigest()


class Wo0012SchemaMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.migrations = cls.manifest["migrations"]

    def test_manifest_has_expected_order(self) -> None:
        self.assertEqual(
            [m["id"] for m in self.migrations],
            [
                "0001-canonical-business-v0.1",
                "0002-counter-operations-v0.1",
                "0003-operational-extensions-v0.2",
            ],
        )

    def test_manifest_sources_exist_and_match_admitted_git_blobs(self) -> None:
        for migration in self.migrations:
            source = ROOT / migration["path"]
            self.assertTrue(source.is_file(), migration["path"])
            self.assertEqual(git_blob_sha(source.read_bytes()), migration["git_blob_sha"])

    def test_dependencies_precede_dependents(self) -> None:
        positions = {m["id"]: index for index, m in enumerate(self.migrations)}
        for migration in self.migrations:
            for dependency in migration.get("depends_on", []):
                self.assertIn(dependency, positions)
                self.assertLess(positions[dependency], positions[migration["id"]])

    def test_canonical_model_retains_derived_stock_truth(self) -> None:
        sql = (ROOT / "schemas/business/canonical_tables.sql").read_text(encoding="utf-8").lower()
        self.assertIn("create table stock_movements", sql)
        self.assertIn("create view stock_position", sql)
        self.assertNotIn("create table stock_position", sql)

    def test_migrations_do_not_contain_destructive_ddl(self) -> None:
        forbidden = ("drop table", "drop schema", "truncate ", "delete from ")
        for migration in self.migrations:
            sql = (ROOT / migration["path"]).read_text(encoding="utf-8").lower()
            for token in forbidden:
                self.assertNotIn(token, sql, f"{token} in {migration['path']}")


if __name__ == "__main__":
    unittest.main()
