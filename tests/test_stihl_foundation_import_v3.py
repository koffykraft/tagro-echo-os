from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_stihl_foundation_import_v3 import build_pack


class StihlFoundationImportV3Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.scout = self.root / "scout"
        self.recon = self.scout / "identity-reconciliation"
        self.recon.mkdir(parents=True)

    def _csv(self, path: Path, fields: list[str], rows: list[dict]) -> None:
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def _make_report(self, accepted: list[dict], unit_rows: list[dict], *, conflict_count: int = 0) -> None:
        parts = {row["canonical_stihl_part_key"] for row in accepted}
        scout_summary = {
            "schema": "tagro.echo.wo0014-stihl-scout/4",
            "status": "scout_complete",
            "git_head": "abc123",
            "deploy_executed": False,
            "migration_executed": False,
            "live_import_executed": False,
        }
        (self.scout / "99-scout-summary.json").write_text(json.dumps(scout_summary), encoding="utf-8")
        recon_summary = {
            "schema": "tagro.echo.stihl-identity-reconciliation/3",
            "validation": {
                "source_branch_preserved": True,
                "operational_branch_segments_collapsed": True,
                "unit_conversion_inferred": False,
                "corrected_part_numbers_auto_admitted": False,
                "name_candidates_auto_admitted": False,
            },
            "counts": {
                "exact_part_accepted_rows": len(accepted),
                "exact_part_accepted_unique_parts": len(parts),
                "canonical_parts_with_unit_conflicts": conflict_count,
            },
        }
        (self.recon / "00-summary.json").write_text(json.dumps(recon_summary), encoding="utf-8")
        accepted_fields = [
            "branch", "source_branch_raw", "source_row", "busy_item_codes_evidence", "busy_name_raw",
            "busy_alias_raw", "busy_part_key", "busy_unit_raw", "busy_unit_family", "busy_parent_group_raw",
            "canonical_stihl_part_key", "identity_class", "identity_method", "direct_seed_evidence",
        ]
        self._csv(self.recon / "01-exact-part-accepted-all-branches.csv", accepted_fields, accepted)
        self._csv(
            self.recon / "03-exact-part-unit-variants.csv",
            ["canonical_stihl_part_key", "branches", "busy_units_exact", "unit_families", "unit_state", "conversion_inferred"],
            unit_rows,
        )

    @staticmethod
    def row(part: str, branch: str, source_branch: str, source_row: str, name: str, alias: str, unit: str,
            group: str, codes: str = "", direct: str = "True") -> dict:
        return {
            "branch": branch,
            "source_branch_raw": source_branch,
            "source_row": source_row,
            "busy_item_codes_evidence": codes,
            "busy_name_raw": name,
            "busy_alias_raw": alias,
            "busy_part_key": part,
            "busy_unit_raw": unit,
            "busy_unit_family": "",
            "busy_parent_group_raw": group,
            "canonical_stihl_part_key": part,
            "identity_class": "EXACT_PART_ACCEPT",
            "identity_method": "busy_master_alias_equals_proven_stihl_part",
            "direct_seed_evidence": direct,
        }

    def test_builds_identity_only_record_and_preserves_raw_evidence(self):
        part = "41801201800"
        accepted = [
            self.row(part, "KVR", "KVR", "64", "Air Filter FS 130", part, "Pcs", "Spare parts", "1221"),
            self.row(part, "SDM", "SDM JAIN", "64", "AIR FILTER FS130", part, "Units", "Spare parts", "", "False"),
            self.row(part, "SDM", "SDM STIHL", "65", "AIR FILTER FS 130", part, "Nos", "Spare parts", "", "False"),
        ]
        self._make_report(accepted, [])
        out = self.root / "out"
        summary = build_pack(self.scout, out)

        self.assertEqual(1, summary["counts"]["canonical_records_ready"])
        self.assertEqual(0, summary["counts"]["total_parts_blocked"])
        records = json.loads((out / "01-canonical-records.json").read_text(encoding="utf-8"))
        self.assertEqual(1, len(records))
        record = records[0]
        self.assertEqual(part, record["sku"])
        self.assertEqual("Air Filter FS 130", record["name"])
        self.assertEqual("Pcs", record["unit"])
        self.assertEqual("", record["gst_rate"])
        self.assertEqual("", record["hsn_code"])
        self.assertEqual([], record["prices"])
        self.assertEqual([], record["unit_conversions"])
        alias_keys = {(a["type"], a["value"], a["branch_code"]) for a in record["aliases"]}
        self.assertIn(("busy_original_name", "AIR FILTER FS130", "SDM"), alias_keys)
        evidence = (out / "02-busy-evidence.csv").read_text(encoding="utf-8-sig")
        self.assertIn("SDM JAIN", evidence)
        self.assertIn("SDM STIHL", evidence)

    def test_true_unit_conflict_blocks_product_without_guessing(self):
        part = "36170001640"
        accepted = [
            self.row(part, "KVR", "KVR", "1", "Saw chain", part, "Links", "Accessories"),
            self.row(part, "PKM", "PKM", "2", "Saw chain", part, "Pcs", "Accessories"),
        ]
        unit_rows = [{
            "canonical_stihl_part_key": part,
            "branches": "KVR | PKM",
            "busy_units_exact": "Links | Pcs",
            "unit_families": "EACH | LINK",
            "unit_state": "CONFLICT_REVIEW",
            "conversion_inferred": "False",
        }]
        self._make_report(accepted, unit_rows, conflict_count=1)
        out = self.root / "out"
        summary = build_pack(self.scout, out)
        self.assertEqual(0, summary["counts"]["canonical_records_ready"])
        self.assertEqual(1, summary["counts"]["unit_conflict_parts_blocked"])
        blocked = (out / "03-blocked-unit-parts.csv").read_text(encoding="utf-8-sig")
        self.assertIn(part, blocked)
        self.assertIn("UNIT_FAMILY_CONFLICT", blocked)

    def test_equivalent_unit_labels_do_not_block(self):
        part = "07813198410"
        accepted = [
            self.row(part, "KVR", "KVR", "1", "Oil", part, "Ltrs", "Accessories"),
            self.row(part, "PKM", "PKM", "2", "Oil", part, "Ltr", "Accessories", direct="False"),
        ]
        unit_rows = [{
            "canonical_stihl_part_key": part,
            "branches": "KVR | PKM",
            "busy_units_exact": "Ltrs | Ltr",
            "unit_families": "LTR",
            "unit_state": "LABEL_VARIANT_ONLY",
            "conversion_inferred": "False",
        }]
        self._make_report(accepted, unit_rows, conflict_count=0)
        out = self.root / "out"
        summary = build_pack(self.scout, out)
        self.assertEqual(1, summary["counts"]["canonical_records_ready"])
        record = json.loads((out / "01-canonical-records.json").read_text(encoding="utf-8"))[0]
        self.assertEqual("Ltrs", record["unit"])
        self.assertEqual([], record["unit_conversions"])

    def test_ambiguous_busy_name_is_evidence_but_not_runtime_alias(self):
        p1 = "11111111111"
        p2 = "22222222222"
        accepted = [
            self.row(p1, "KVR", "KVR", "1", "FILTER", p1, "Pcs", "Spare parts", "101"),
            self.row(p2, "KVR", "KVR", "2", "FILTER", p2, "Pcs", "Spare parts", "102"),
        ]
        self._make_report(accepted, [])
        out = self.root / "out"
        summary = build_pack(self.scout, out)
        self.assertEqual(2, summary["counts"]["canonical_records_ready"])
        self.assertEqual(1, summary["counts"]["ambiguous_alias_keys_omitted"])
        records = json.loads((out / "01-canonical-records.json").read_text(encoding="utf-8"))
        for record in records:
            self.assertNotIn(
                ("busy_original_name", "FILTER", "KVR"),
                {(a["type"], a["value"], a["branch_code"]) for a in record["aliases"]},
            )
        collisions = (out / "04-alias-collisions-review.csv").read_text(encoding="utf-8-sig")
        self.assertIn("FILTER", collisions)
        self.assertIn(p1, collisions)
        self.assertIn(p2, collisions)

    def test_rejects_mutated_scout_source(self):
        part = "41801201800"
        self._make_report([self.row(part, "KVR", "KVR", "1", "Filter", part, "Pcs", "Spare parts")], [])
        summary = json.loads((self.scout / "99-scout-summary.json").read_text(encoding="utf-8"))
        summary["live_import_executed"] = True
        (self.scout / "99-scout-summary.json").write_text(json.dumps(summary), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "mutation-free"):
            build_pack(self.scout, self.root / "out")


if __name__ == "__main__":
    unittest.main()
