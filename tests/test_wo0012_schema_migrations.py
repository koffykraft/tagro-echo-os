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
                "0006-platform-spectral-routing-v0.2.2",
                "0007-platform-import-observations-v0.2.3",
                "0008-stock-observation-planes-v0.4",
                "0009-payment-receipt-evidence-v0.4",
                "0010-cash-entry-evidence-v0.4",
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

    def test_vibgyor_prism_is_filter_not_new_truth(self) -> None:
        sql = (ROOT / "schemas/business/platform_spectral_routing_v0_2_2.sql").read_text(encoding="utf-8").lower()
        self.assertIn("create table spectral_bands", sql)
        for code in ("'v'", "'i'", "'b'", "'g'", "'y'", "'o'", "'r'"):
            self.assertIn(code, sql)
        self.assertIn("alter table vector_definitions", sql)
        self.assertIn("spectrum_code", sql)
        self.assertIn("create table spectral_receiver_rules", sql)
        self.assertIn("non-matching spectral projection is semantically inert", sql)
        self.assertIn("presence at a receiver does not create business meaning", sql)
        self.assertNotIn("delete from echo_events", sql)

    def test_import_observations_do_not_become_canonical_by_presence(self) -> None:
        sql = (ROOT / "schemas/business/platform_import_observations_v0_2_3.sql").read_text(encoding="utf-8").lower()
        for table in ("import_sources", "import_observations", "reconciliation_candidates", "canonical_admissions"):
            self.assertIn(f"create table {table}", sql)
        self.assertIn("observation presence never grants canonical authority", sql)
        self.assertIn("only an accepted", sql)
        self.assertIn("reconciliation candidate plus authorised admission", sql)
        self.assertIn("admitted_by_principal_id", sql)
        self.assertIn("authority_basis", sql)
        self.assertIn("provenance_ref", sql)

    def test_stock_count_plane_preserves_unknown_separately_from_canonical_stock(self) -> None:
        sql = (ROOT / "schemas/business/stock_observation_planes_v0_4.sql").read_text(encoding="utf-8").lower()
        self.assertIn("create table stock_count_observations", sql)
        self.assertIn("create view provisional_stock_position", sql)
        self.assertIn("provisional_eligible", sql)
        self.assertIn("identity_state", sql)
        self.assertIn("product_id text references products(product_id)", sql)
        self.assertNotIn("product_id text not null references products(product_id)", sql)
        self.assertIn("unknown, never zero by absence", sql)
        self.assertIn("cannot create stock movements", sql)
        self.assertNotIn("insert into stock_movements", sql)

    def test_payment_is_separate_evidence_not_implied_by_sale(self) -> None:
        sql = (ROOT / "schemas/business/payment_receipt_evidence_v0_4.sql").read_text(encoding="utf-8").lower()
        self.assertIn("create table payment_receipts", sql)
        self.assertIn("create table payment_allocations", sql)
        self.assertIn("a sale does not prove receipt", sql)
        self.assertIn("staff_affirmed_unreconciled", sql)
        self.assertIn("no direct bank-transaction foreign key", sql)
        self.assertNotIn("references bank_transactions", sql)

    def test_cash_entries_preserve_explicit_classification_and_transfers(self) -> None:
        sql = (ROOT / "schemas/business/cash_entry_evidence_v0_4.sql").read_text(encoding="utf-8").lower()
        self.assertIn("create table cash_day_sessions", sql)
        self.assertIn("create table cash_entry_evidence", sql)
        self.assertIn("classification_role", sql)
        self.assertIn("classification_confidence", sql)
        self.assertIn("'unknown'", sql)
        self.assertIn("'allocation_cash'", sql)
        self.assertIn("'deposit_cash'", sql)
        self.assertIn("'transfer_cash_out'", sql)
        self.assertIn("create view cash_day_session_review", sql)

    def test_business_tables_are_enterprise_scoped(self) -> None:
        for path in (
            "schemas/business/canonical_tables_v0_2.sql",
            "schemas/business/counter_ops_v0_2.sql",
            "schemas/business/operational_extensions_v0_3.sql",
            "schemas/business/stock_observation_planes_v0_4.sql",
            "schemas/business/payment_receipt_evidence_v0_4.sql",
            "schemas/business/cash_entry_evidence_v0_4.sql",
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
