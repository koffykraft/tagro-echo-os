from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from scripts.reconcile_stihl_busy_identity_v2 import reconcile


TD_FIELDS = [
    "branch", "item_code", "busy_name", "busy_alias", "busy_part_key", "print_name", "match_status",
    "tagro_name", "tagro_part_no", "tagro_alias", "tagro_unit", "stihl_part_no", "stihl_name",
    "gst", "price", "price_plus_gst", "mrp",
]
MASTER_FIELDS = [
    "Branch", "Source row", "Item Name", "Alias / Part No", "Part No Normalized", "Parent Group",
    "Opening Stock", "Unit", "Name Key", "Same part number row count", "Same name row count", "Import status/comment",
]
ADMISSION_FIELDS = [
    "Branch", "Original TAGRO item name", "TAGRO display name", "BUSY item codes", "BUSY alias",
    "STIHL part number", "Official STIHL name", "Ready for BUSY",
]


class StihlIdentityReconciliationV2Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def _csv(self, name, fields, rows):
        path = self.root / name
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def _run(self, td, master, admission):
        out = self.root / "out"
        return reconcile(
            self._csv("td.csv", TD_FIELDS, td),
            self._csv("master.csv", MASTER_FIELDS, master),
            self._csv("admission.csv", ADMISSION_FIELDS, admission),
            out,
        ), out

    @staticmethod
    def td_exact(branch, code, name, part, unit="Pcs"):
        return {
            "branch": branch, "item_code": code, "busy_name": name, "busy_alias": part,
            "busy_part_key": part, "print_name": name, "match_status": "matched_price",
            "tagro_name": name, "tagro_part_no": part, "tagro_alias": part, "tagro_unit": unit,
            "stihl_part_no": part, "stihl_name": name.upper(),
        }

    @staticmethod
    def master(branch, source_row, name, part="", unit="Pcs"):
        return {
            "Branch": branch, "Source row": source_row, "Item Name": name, "Alias / Part No": part,
            "Part No Normalized": part, "Parent Group": "Spare parts", "Opening Stock": "", "Unit": unit,
        }

    def test_proven_part_expands_to_all_busy_branches_and_preserves_raw_names(self):
        part = "41801201800"
        summary, out = self._run(
            [self.td_exact("KVR", "1221", "Air Filter FS 130", part)],
            [
                self.master("KVR", "64", "Air Filter FS 130", part, "Pcs"),
                self.master("PKM", "91", "AIR FILTER  FS130", part, "Nos"),
            ],
            [],
        )
        self.assertEqual(2, summary["counts"]["exact_part_accepted_rows"])
        self.assertEqual(1, summary["counts"]["exact_part_cross_branch_expansion_rows"])
        self.assertEqual(0, summary["counts"]["canonical_parts_with_unit_conflicts"])
        report = (out / "01-exact-part-accepted-all-branches.csv").read_text(encoding="utf-8-sig")
        self.assertIn("Air Filter FS 130", report)
        self.assertIn("AIR FILTER  FS130", report)
        self.assertIn("Pcs", report)
        self.assertIn("Nos", report)

    def test_prior_exact_admission_seeds_identity_without_any_price(self):
        part = "11481404406"
        admission = [{
            "Branch": "KVR", "Original TAGRO item name": "Air filter, MS 182", "TAGRO display name": "Air filter, MS 182",
            "BUSY item codes": "6462", "BUSY alias": part, "STIHL part number": part,
            "Official STIHL name": "AIR FILTER PA", "Ready for BUSY": "Yes",
        }]
        summary, _ = self._run([], [
            self.master("KVR", "81", "Air filter, MS 182", part),
            self.master("SKT", "77", "AIR FILTER MS182", part),
        ], admission)
        self.assertEqual(1, summary["counts"]["exact_seed_unique_parts"])
        self.assertEqual(2, summary["counts"]["exact_part_accepted_rows"])
        self.assertFalse(summary["policy"]["prices_required_for_identity"])

    def test_tagro_only_bad_part_value_never_becomes_canonical_identity(self):
        busy_part = "36230001640"
        td = [{
            "branch": "KVR", "item_code": "1200", "busy_name": "33RSC Sawchain STIHL", "busy_alias": busy_part,
            "busy_part_key": busy_part, "print_name": "33RSC Sawchain STIHL", "match_status": "matched_tagro_master_price_only",
            "tagro_name": "33RSC Sawchain STIHL", "tagro_part_no": "34999", "tagro_alias": busy_part,
            "tagro_unit": "Links", "stihl_part_no": "", "stihl_name": "", "price": "28248",
        }]
        seed = [{
            "Branch": "PKM", "Original TAGRO item name": "Known Seed", "TAGRO display name": "Known Seed",
            "BUSY item codes": "1", "BUSY alias": "41801201800", "STIHL part number": "41801201800",
            "Official STIHL name": "FILTER", "Ready for BUSY": "Yes",
        }]
        summary, _ = self._run(td, [self.master("KVR", "12", "33RSC Sawchain STIHL", busy_part, "Links")], seed)
        self.assertEqual(0, summary["counts"]["exact_part_accepted_rows"])
        self.assertEqual(0, summary["counts"]["tagro_master_part_candidates_review"])
        self.assertEqual(1, summary["counts"]["unmatched_stihl_clue_rows"])

    def test_official_corrected_part_stays_review_until_revalidated(self):
        td = [{
            "branch": "KVR", "item_code": "1204", "busy_name": "4 MM Round File (STIHL)", "busy_alias": "56057724006",
            "busy_part_key": "56057724006", "print_name": "4 MM Round File (STIHL)", "match_status": "matched_price",
            "tagro_name": "4 MM Round File (STIHL)", "tagro_part_no": "56057734006", "tagro_alias": "56057724006",
            "tagro_unit": "Pcs", "stihl_part_no": "56057734006", "stihl_name": "ROUND FILE 4.0X200MM",
        }]
        seed = [{
            "Branch": "PKM", "Original TAGRO item name": "Known Seed", "TAGRO display name": "Known Seed",
            "BUSY item codes": "1", "BUSY alias": "41801201800", "STIHL part number": "41801201800",
            "Official STIHL name": "FILTER", "Ready for BUSY": "Yes",
        }]
        summary, _ = self._run(td, [self.master("KVR", "17", "4 MM Round File (STIHL)", "56057724006")], seed)
        self.assertEqual(0, summary["counts"]["exact_part_accepted_rows"])
        self.assertEqual(1, summary["counts"]["official_part_corrections_review"])

    def test_name_logic_never_silently_overrides_part_evidence(self):
        proven = "41801201800"
        summary, _ = self._run(
            [self.td_exact("KVR", "1221", "Air Filter FS 130", proven)],
            [
                self.master("KVR", "64", "Air Filter FS 130", proven),
                self.master("NDD", "44", "Air Filter FS 130", ""),
                self.master("MDM", "45", "Air Filter FS 130", "99999999999"),
            ],
            [],
        )
        self.assertEqual(1, summary["counts"]["name_candidates_need_part_evidence"])
        self.assertEqual(1, summary["counts"]["name_candidate_part_conflicts"])
        self.assertEqual(0, summary["counts"]["name_candidates_part_revalidated"])

    def test_unit_conflict_is_reported_without_blocking_identity_or_inventing_conversion(self):
        part = "38740001640"
        summary, out = self._run(
            [self.td_exact("KVR", "1300", "33RSK Chain reel RAPID SUPER", part, "Links")],
            [
                self.master("KVR", "13", "33RSK Chain reel RAPID SUPER", part, "Links"),
                self.master("PKM", "14", "33 RSK CHAIN REEL", part, "Pcs"),
            ],
            [],
        )
        self.assertEqual(2, summary["counts"]["exact_part_accepted_rows"])
        self.assertEqual(1, summary["counts"]["canonical_parts_with_unit_conflicts"])
        report = (out / "03-exact-part-unit-variants.csv").read_text(encoding="utf-8-sig")
        self.assertIn("CONFLICT_REVIEW", report)
        self.assertIn("False", report)


if __name__ == "__main__":
    unittest.main()
