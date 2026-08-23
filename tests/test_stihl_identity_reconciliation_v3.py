from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from scripts.reconcile_stihl_busy_identity_v3 import reconcile, unit_family


class StihlIdentityReconciliationV3Tests(unittest.TestCase):
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

    def _td(self, rows):
        return self._csv("td.csv", [
            "branch", "item_code", "busy_name", "busy_alias", "busy_part_key", "print_name", "match_status",
            "tagro_name", "tagro_part_no", "tagro_alias", "tagro_unit", "stihl_part_no", "stihl_name",
        ], rows)

    def _master(self, rows):
        return self._csv("master.csv", [
            "Branch", "Source row", "Item Name", "Alias / Part No", "Part No Normalized", "Parent Group",
            "Opening Stock", "Unit", "Name Key", "Same part number row count", "Same name row count", "Import status/comment",
        ], rows)

    def _admission(self, rows):
        return self._csv("admission.csv", [
            "Branch", "Original TAGRO item name", "TAGRO display name", "BUSY item codes", "BUSY alias",
            "STIHL part number", "Official STIHL name", "Ready for BUSY",
        ], rows)

    def test_equivalent_unit_labels_are_not_conflicts(self):
        self.assertEqual("LTR", unit_family("Ltr"))
        self.assertEqual("LTR", unit_family("Ltrs"))
        self.assertEqual("EACH", unit_family("Pcs"))
        self.assertEqual("EACH", unit_family("Units"))
        self.assertEqual("LINK", unit_family("Links"))
        self.assertEqual("PKT", unit_family("Pkt"))

    def test_sdm_segments_collapse_operationally_but_raw_source_is_preserved(self):
        part = "41801201800"
        td = self._td([{
            "branch": "KVR", "item_code": "1221", "busy_name": "Air Filter FS 130", "busy_alias": part,
            "busy_part_key": part, "print_name": "Air Filter FS 130", "match_status": "matched_price",
            "tagro_name": "Air Filter FS 130", "tagro_part_no": part, "tagro_alias": part, "tagro_unit": "Pcs",
            "stihl_part_no": part, "stihl_name": "FILTER",
        }])
        master = self._master([
            {"Branch": "KVR", "Source row": "64", "Item Name": "Air Filter FS 130", "Alias / Part No": part, "Part No Normalized": part, "Parent Group": "Spare parts", "Opening Stock": "", "Unit": "Pcs"},
            {"Branch": "SDM JAIN", "Source row": "64", "Item Name": "AIR FILTER FS130", "Alias / Part No": part, "Part No Normalized": part, "Parent Group": "Spare parts", "Opening Stock": "", "Unit": "Units"},
            {"Branch": "SDM STIHL", "Source row": "64", "Item Name": "AIR FILTER FS 130", "Alias / Part No": part, "Part No Normalized": part, "Parent Group": "Spare parts", "Opening Stock": "", "Unit": "Nos"},
        ])
        admission = self._admission([])
        out = self.root / "out"
        summary = reconcile(td, master, admission, out)

        self.assertEqual("tagro.echo.stihl-identity-reconciliation/3", summary["schema"])
        self.assertEqual(2, summary["counts"]["exact_part_accepted_branches"])
        self.assertEqual(0, summary["counts"]["canonical_parts_with_unit_conflicts"])
        self.assertIn("SDM", summary["by_branch"])
        self.assertNotIn("SDM JAIN", summary["by_branch"])
        self.assertNotIn("SDM STIHL", summary["by_branch"])

        with (out / "01-exact-part-accepted-all-branches.csv").open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        sdm = [row for row in rows if row["branch"] == "SDM"]
        self.assertEqual(2, len(sdm))
        self.assertEqual({"SDM JAIN", "SDM STIHL"}, {row["source_branch_raw"] for row in sdm})
        self.assertEqual({"Units", "Nos"}, {row["busy_unit_raw"] for row in sdm})

    def test_true_link_vs_each_conflict_remains_review_only(self):
        part = "36170001640"
        td = self._td([{
            "branch": "KVR", "item_code": "1", "busy_name": "CHAIN", "busy_alias": part,
            "busy_part_key": part, "print_name": "CHAIN", "match_status": "matched_price",
            "tagro_name": "CHAIN", "tagro_part_no": part, "tagro_alias": part, "tagro_unit": "Links",
            "stihl_part_no": part, "stihl_name": "CHAIN REEL",
        }])
        master = self._master([
            {"Branch": "KVR", "Source row": "1", "Item Name": "CHAIN", "Alias / Part No": part, "Part No Normalized": part, "Parent Group": "Accessories", "Opening Stock": "", "Unit": "Links"},
            {"Branch": "PKM", "Source row": "2", "Item Name": "CHAIN", "Alias / Part No": part, "Part No Normalized": part, "Parent Group": "Accessories", "Opening Stock": "", "Unit": "Pcs"},
        ])
        out = self.root / "out2"
        summary = reconcile(td, master, self._admission([]), out)
        self.assertEqual(1, summary["counts"]["canonical_parts_with_unit_conflicts"])
        unit_text = (out / "03-exact-part-unit-variants.csv").read_text(encoding="utf-8-sig")
        self.assertIn("CONFLICT_REVIEW", unit_text)
        self.assertIn("False", unit_text)


if __name__ == "__main__":
    unittest.main()
