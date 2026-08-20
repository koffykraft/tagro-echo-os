from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "schemas" / "migrations" / "nonprod_v0_2_manifest.json"


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
                "0001-platform-foundation-v0.2",
                "0002-canonical-business-v0.2",
                "0003-counter-operations-v0.2",
                "0004-operational-extensions-v0.3",
                "0005-platform-identity-constraints-v0.2.1",
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

    def test_platform_foundation_has_saas_and_planar_primitives(self) -> None:
        sql = (ROOT / "schemas/business/platform_foundation_v0_2.sql").read_text(encoding="utf-8").lower()
        for table in (
            "enterprises",
            "principals",
            "enterprise_memberships",
            "capabilities",
            "enterprise_entitlements",
            "echo_events",
            "vector_definitions",
            "event_vectors",
            "chord_definitions",
            "chord_vector_requirements",
            "chord_candidates",
            "sweeper_policies",
        ):
            self.assertIn(f"create table {table}", sql)
        self.assertIn("passage_state", sql)
        self.assertIn("strength_class", sql)
        self.assertIn("review_interval_seconds", sql)

    def test_identity_hardening_keeps_external_login_unique(self) -> None:
        sql = (ROOT / "schemas/business/platform_identity_constraints_v0_2_1.sql").read_text(encoding="utf-8").lower()
        self.assertIn("create unique index ux_principals_external_identity_ref", sql)
        self.assertIn("where external_identity_ref <> ''", sql)
        self.assertIn("idx_enterprise_memberships_principal", sql)
        self.assertIn("idx_enterprise_entitlements_active", sql)

    def test_business_tables_are_enterprise_scoped(self) -> None:
        for path in (
            "schemas/business/canonical_tables_v0_2.sql",
            "schemas/business/counter_ops_v0_2.sql",
            "schemas/business/operational_extensions_v0_3.sql",
        ):
            sql = (ROOT / path).read_text(encoding="utf-8").lower()
            self.assertIn("enterprise_id", sql, path)
            self.assertIn("references enterprises(enterprise_id)", sql, path)

    def test_identity_is_separate_from_enterprise_membership(self) -> None:
        sql = (ROOT / "schemas/business/platform_foundation_v0_2.sql").read_text(encoding="utf-8").lower()
        self.assertIn("create table principals", sql)
        self.assertIn("create table enterprise_memberships", sql)
        self.assertIn("principal_id text not null references principals(principal_id)", sql)

    def test_capability_entitlement_is_not_a_fixed_menu(self) -> None:
        sql = (ROOT / "schemas/business/platform_foundation_v0_2.sql").read_text(encoding="utf-8").lower()
        self.assertIn("create table capabilities", sql)
        self.assertIn("create table enterprise_entitlements", sql)
        self.assertIn("enabled','disabled','suspended','archived", sql)

    def test_canonical_model_retains_derived_stock_truth(self) -> None:
        sql = (ROOT / "schemas/business/canonical_tables_v0_2.sql").read_text(encoding="utf-8").lower()
        self.assertIn("create table stock_movements", sql)
        self.assertIn("create view stock_position", sql)
        self.assertNotIn("create table stock_position", sql)
        self.assertIn("enterprise_id, branch_id, product_id", sql)

    def test_bank_relationship_remains_candidate_not_direct_fk(self) -> None:
        sql = (ROOT / "schemas/business/operational_extensions_v0_3.sql").read_text(encoding="utf-8").lower()
        self.assertIn("candidate relationship/chord", sql)
        self.assertNotIn("sale_id text references", sql)
        self.assertNotIn("payment_id text references", sql)

    def test_sweeper_retirement_does_not_delete_event_truth(self) -> None:
        sql = (ROOT / "schemas/business/platform_foundation_v0_2.sql").read_text(encoding="utf-8").lower()
        self.assertIn("never deletes the originating event or evidence", sql)
        self.assertNotIn("delete from echo_events", sql)

    def test_migrations_do_not_contain_destructive_ddl(self) -> None:
        forbidden = ("drop table", "drop schema", "truncate ", "delete from ")
        for migration in self.migrations:
            sql = (ROOT / migration["path"]).read_text(encoding="utf-8").lower()
            for token in forbidden:
                self.assertNotIn(token, sql, f"{token} in {migration['path']}")


if __name__ == "__main__":
    unittest.main()
