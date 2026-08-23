from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from scripts.sync_stihl_master_to_echo import build_records


FIELDS = [
    "Branch", "Original TAGRO item name", "TAGRO display name", "BUSY item codes",
    "BUSY alias", "STIHL part number", "Official STIHL name", "Official type", "HSN",
    "GST %", "STIHL price before GST", "STIHL price incl GST", "STIHL MRP", "Ready for BUSY",
]


class StihlMasterSyncTests(unittest.TestCase):
    def _write(self, rows):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "stihl.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def _row(self, branch: str, busy_code: str, tagro_name: str):
        return {
            "Branch": branch,
            "Original TAGRO item name": tagro_name,
            "TAGRO display name": tagro_name,
            "BUSY item codes": busy_code,
            "BUSY alias": "MS382",
            "STIHL part number": "11192000261",
            "Official STIHL name": "MS 382 Chainsaw with 18 inch Guide bar & Saw Chain",
            "Official type": "MACHINES",
            "HSN": "84678100",
            "GST %": "18",
            "STIHL price before GST": "52260",
            "STIHL price incl GST": "61666.80",
            "STIHL MRP": "69067",
            "Ready for BUSY": "YES",
        }

    def test_branch_rows_deduplicate_to_official_part(self):
        records, stats = build_records(
            self._write([
                self._row("KVR", "KVR-382", "MS 382"),
                self._row("PKM", "PKM-382", "MS382 CHAINSAW"),
            ]),
            "2026-06-01",
        )
        self.assertEqual(1, len(records))
        product = records[0]
        self.assertEqual("11192000261", product["sku"])
        self.assertEqual("84678100", product["hsn_code"])
        self.assertEqual("18", product["gst_rate"])
        self.assertEqual(3, len(product["prices"]))
        self.assertEqual(2, stats["ready_rows"])
        self.assertEqual(1, stats["unique_products"])
        self.assertEqual(0, stats["unknown_hsn"])
        self.assertEqual(0, stats["unknown_gst"])
        alias_branches = {a["branch_code"] for a in product["aliases"]}
        self.assertEqual({"KVR", "PKM"}, alias_branches)

    def test_blank_hsn_and_gst_are_allowed(self):
        row = self._row("KVR", "KVR-382", "MS 382")
        row["HSN"] = ""
        row["GST %"] = ""
        records, stats = build_records(self._write([row]), "2026-06-01")
        self.assertEqual("", records[0]["hsn_code"])
        self.assertEqual("", records[0]["gst_rate"])
        self.assertEqual(1, stats["unknown_hsn"])
        self.assertEqual(1, stats["unknown_gst"])

    def test_blank_tax_fields_can_be_filled_by_another_branch(self):
        first = self._row("KVR", "KVR-382", "MS 382")
        first["HSN"] = ""
        first["GST %"] = ""
        second = self._row("PKM", "PKM-382", "MS 382")
        records, stats = build_records(self._write([first, second]), "2026-06-01")
        self.assertEqual("84678100", records[0]["hsn_code"])
        self.assertEqual("18", records[0]["gst_rate"])
        self.assertEqual(0, stats["unknown_hsn"])
        self.assertEqual(0, stats["unknown_gst"])

    def test_conflicting_hsn_is_refused(self):
        first = self._row("KVR", "KVR-382", "MS 382")
        second = self._row("PKM", "PKM-382", "MS 382")
        second["HSN"] = "99999999"
        with self.assertRaisesRegex(RuntimeError, "conflicting HSN"):
            build_records(self._write([first, second]), "2026-06-01")

    def test_conflicting_gst_is_refused(self):
        first = self._row("KVR", "KVR-382", "MS 382")
        second = self._row("PKM", "PKM-382", "MS 382")
        second["GST %"] = "12"
        with self.assertRaisesRegex(RuntimeError, "conflicting GST"):
            build_records(self._write([first, second]), "2026-06-01")


if __name__ == "__main__":
    unittest.main()
