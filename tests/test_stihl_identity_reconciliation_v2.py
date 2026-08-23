from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from scripts.reconcile_stihl_busy_identity_v2 import reconcile


class StihlIdentityReconciliationV2Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def _csv(self, name: str, fields: list[str], rows: list[dict]) -> Path:
        path = self.root / name
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def _td(self, rows: list[dict]) -> Path:
        fields = [
            "branch", "item_code", "busy_name", "busy_alias", "busy_part_key", "print_name", "match_status",
            "tagro_name", "tagro_part_no", "tagro_alias", "tagro_unit", "stihl_part_no", "stihl_name",
            "gst", "price", "price_plus_gst", "mrp",
        ]
        return self._csv("td.csv", fields, rows)

    def _master(self, rows: list[dict]) -> Path:
        fields = [
            "Branch", "Source row", "Item Name", "Alias / Part No", "Part No Normalized", "Parent Group",
            "Opening Stock", "Unit", "Name Key", "Same part number row count", "Same name row count", "Import status/comment",
        ]
        return self._csv("master.csv", fields, rows)

    def _admission(self, rows: list[dict]) -> Path:
        fields = [
            "Branch", "Original TAGRO item name", "TAGRO display name", "BUSY item codes", "BUSY alias",
            "STIHL part number", "Official STIHL name", "Ready for BUSY",
        ]
        return self._csv("admission.csv", fields, rows)

    def _run(self, td_rows, master_rows, admission_rows):
        out = self.root / "out"
        summary = reconcile(self._td(td_rows), self._master(master_rows), self._admission(admission_rows), out)
        return summary, out

    def test_exact_official_seed_expands_same_busy_part_to_other_branches_and_preserves_raw_text(self):
        part = "41801201800"
        summary, out = self._run(
            [{
                "branch": "KVR", "item_code": "1221", "busy_name": "Air Filter FS 130", "busy_alias": part,
                "busy_part_key": part, "print_name": "Air Filter FS 130", "match_status": "matched_price",
                "tagro_name": "Air Filter FS 130", "tagro_part_no": part, "tagro_alias": part, "tagro_unit": "Pcs",
                "stihl_part_no": part, "stihl_name": "FILTER", "gst": "18", "price": "128",
            }],
            [
                {"Branch": "KVR", "Source row": "64", "Item Name": "Air Filter FS 130", "Alias / Part No": part, "Part No Normalized": part, "Parent Group": "Spare parts", "Opening Stock": "27", "Unit": "Pcs"},
                {"Branch": "PKM", "Source row": "91", "Item Name": "AIR FILTER  FS130", "Alias / Part No": part, "Part No Normalized": part, "Parent Group": "Spare parts", "Opening Stock": "", "Unit": "Nos"},
            ],
            [],
        )
        self.assertEqual(1, summary["counts"]["exact_seed_unique_parts"])
        self.assertEqual(2, summary["counts"]["exact_part_accepted_rows"])
        self.assertEqual(1, summary["counts"]["exact_part_cross_branch_expansion_rows"])
        self.assertEqual(0, summary["counts"]["canonical_parts_with_unit_conflicts"])
        accepted = (out / "01-exact-part-accepted-all-branches.csv").read_text(encoding="utf-8-sig")
        self.assertIn("Air Filter FS 130", accepted)
        self.assertIn("AIR FILTER  FS130", accepted)
        self.assertIn("Pcs", accepted)
        self.assertIn("Nos", accepted)

    def test_existing_admission_exact_part_can_seed_identity_without_price_dependency(self):
        part = "11481404406"
        summary, _ = self._run(
            [],
            [
                {"Branch": "KVR", "Source row": "81", "Item Name": "Air filter, MS 182", "Alias / Part No": part, "Part No Normalized": part, "Parent Group": "Spare parts", "Opening Stock": "5", "Unit": "Pcs"},
                {"Branch": "SKT", "Source row": "77", "Item Name": "AIR FILTER MS182", "Alias / Part No": part, "Part No Normalized": part, "Parent Group": "Spare parts", "Opening Stock": "", "Unit": "Pcs"},
            ],
            [{"Branch": "KVR", "Original TAGRO item name": "Air filter, MS 182", "TAGRO display name": "Air filter, MS 182", "BUSY item codes": "6462", "BUSY alias": part, "STIHL part number": part, "Official STIHL name": "AIR FILTER PA", "Ready for BUSY": "Yes"}],
        )
        self.assertEqual(1, summary["counts"]["exact_seed_unique_parts"])
        self.assertEqual(2, summary["counts"]["exact_part_accepted_rows"])
        self.assertFalse(summary["policy"]["prices_required_for_identity"])

    def test_tagro_master_candidate_is_not_promoted_when_official_stihl_part_is_missing(self):
        busy_part = "36230001640"
        summary, _ = self._run(
            [{
                "branch": "KVR", "item_code": "1200", "busy_name": "33RSC Sawchain STIHL", "busy_alias": busy_part,
                "busy_part_key": busy_part, "print_name": "33RSC Sawchain STIHL", "match_status": "matched_tagro_master_price_only",
                "tagro_name": "33RSC Sawchain STIHL", "tagro_part_no": "34999", "tagro_alias": busy_part,
                "tagro_unit": "Links", "stihl_part_no": "", "stihl_name": "", "price": "28248",
            }],
            [{"Branch": "KVR", "Source row": "12", "Item Name": "33RSC Sawchain STIHL", "Alias / Part No": busy_part, "Part No Normalized": busy_part, "Parent Group": "Accessories", "Opening Stock": "", "Unit": "Links"}],
            [{"Branch": "PKM", "Original TAGRO item name": "Known Seed", "TAGRO display name": "Known Seed", "BUSY item codes": "1", "BUSY alias": "41801201800", "STIHL part number": "41801201800", "Official STIHL name": "FILTER", "Ready for BUSY": "Yes"}],
        )
        self.assertEqual(1, summary["counts"]["exact_seed_unique_parts"])
        self.assertEqual(0, summary["counts"]["exact_part_accepted_rows"])
        self.assertEqual(1, summary["counts"]["tagro_master_part_candidates_review"])

    def test_official_corrected_part_number_remains_review_not_first_pass_acceptance(self):
        summary, _ = self._run(
            [{
                "branch": "KVR", "item_code": "1204", "busy_name": "4 MM Round File (STIHL)", "busy_alias": "56057724006",
                "busy_part_key": "56057724006", "print_name": "4 MM Round File (STIHL)", "match_status": "matched_price",
                "tagro_name": "4 MM Round File (STIHL)", "tagro_part_no": "56057734006", "tagro_alias": "56057724006",
                "tagro_unit": "Pcs", "stihl_part_no": "56057734006", "stihl_name": "ROUND FILE 4.0X200MM",
            }],
            [{"Branch": "KVR", "Source row": "17", "Item Name": "4 MM Round File (STIHL)", "Alias / Part No": "56057724006", "Part No Normalized": "56057724006", "Parent Group": "Accessories", "Opening Stock": "442", "Unit": "Pcs"}],
            [{"Branch": "PKM", "Original TAGRO item name": "Known Seed", "TAGRO display name": "Known Seed", "BUSY item codes": "1", "BUSY alias": "41801201800", "STIHL part number": "41801201800", "Official STIHL name": "FILTER", "Ready for BUSY": "Yes"}],
        )
        self.assertEqual(0, summary["counts"]["exact_part_accepted_rows"])
        self.assertEqual(1, summary["counts"]["official_part_corrections_review"])

    def test_name_match_is_candidate_only_and_conflicting_part_is_reported(self):
        proven = "41801201800"
        other = "99999999999"
        summary, _ = self._run(
            [{
                "branch": "KVR", "item_code": "1221", "busy_name": "Air Filter FS 130", "busy_alias": proven,
                "busy_part_key": proven, "print_name": "Air Filter FS 130", "match_status": "matched_price",
                "tagro_name": "Air Filter FS 130", "tagro_part_no": proven, "tagro_alias": proven,
                "tagro_unit": "Pcs", "stihl_part_no": proven, "stihl_name": "FILTER",
            }],
            [
                {"Branch": "KVR", "Source row": "64", "Item Name": "Air Filter FS 130", "Alias / Part No": proven, "Part No Normalized": proven, "Parent Group": "Spare parts", "Opening Stock": "", "Unit": "Pcs"},
                {"Branch": "NDD", "Source row": "44", "Item Name": "Air Filter FS 130", "Alias / Part No": "", "Part No Normalized": "", "Parent Group": "Spare parts", "Opening Stock": "", "Unit": "Pcs"},
                {"Branch": "MDM", "Source row": "45", "Item Name": "Air Filter FS 130", "Alias / Part No": other, "Part No Normalized": other, "Parent Group": "Spare parts", "Opening Stock": "", "Unit": "Pcs"},
            ],
            [],
        )
        self.assertEqual(1, summary["counts"]["name_candidates_need_part_evidence"])
        self.assertEqual(1, summary["counts"]["name_candidate_part_conflicts"])
        self.assertEqual(0, summary["counts"]["name_candidates_part_revalidated"])

    def test_unit_conflict_does_not_block_exact_identity_and_no_conversion_is_inferred(self):
        part = "38740001640"
        summary, out = self._run(
            [{
                "branch": "KVR", "item_code": "1300", "busy_name": "33RSK Chain reel RAPID SUPER", "busy_alias": part,
                "busy_part_key": part, "print_name": "33RSK Chain reel RAPID SUPER", "match_status": "matched_price",
                "tagro_name": "33RSK Chain reel RAPID SUPER", "tagro_part_no": part, "tagro_alias": part,
                "tagro_unit": "Links", "stihl_part_no": part, "stihl_name": "33RSK CHAIN REEL RAPID SUPER",
            }],
            [
                {"Branch": "KVR", "Source row": "13", "Item Name": "33RSK Chain reel RAPID SUPER", "Alias / Part No": part, "Part No Normalized": part, "Parent Group": "Accessories", "Opening Stock": "", "Unit": "Links"},
                {"Branch": "PKM", "Source row": "14", "Item Name": "33 RSK CHAIN REEL", "Alias / Part No": part, "Part No Normalized": part, "Parent Group": "Accessories", "Opening Stock": "", "Unit": "Pcs"},
            ],
            [],
        )
        self.assertEqual(2, summary["counts"]["exact_part_accepted_rows"])
        self.assertEqual(1, summary["counts"]["canonical_parts_with_unit_conflicts"])
        unit_report = (out / "03-exact-part-unit-variants.csv").read_text(encoding="utf-8-sig")
        self.assertIn("CONFLICT_REVIEW", unit_report)
        self.assertIn("False", unit_report)


if __name__ == "__main__":
    unittest.main()
