from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.sync_stihl_catalog_to_echo import build_records


class StihlCatalogSyncTests(unittest.TestCase):
    def _root(self) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return Path(tmp.name)

    def _official(self, root: Path, rows) -> Path:
        path = root / "stihl.json"
        path.write_text(json.dumps({"source": "test", "rows": rows}), encoding="utf-8")
        return path

    def _aliases(self, root: Path, rows) -> Path:
        path = root / "aliases.csv"
        fields = ["Branch", "Original TAGRO item name", "TAGRO display name", "BUSY item codes", "BUSY alias", "STIHL part number"]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def _busy(self, root: Path, rows) -> Path:
        path = root / "busy.csv"
        fields = ["Branch", "Item Name", "Part No Normalized", "Alias / Part No", "Parent Group", "Unit"]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_only_existing_busy_items_are_admitted_and_june_price_is_enrichment(self):
        root = self._root()
        official = self._official(root, [
            {"type": "MACHINES", "part_no": "11192000261", "name": "MS 382", "hsn": "84678100", "gst": 18.0, "price": 52260.0, "mrp": 69067.0},
            {"type": "PARTS", "part_no": "99999999999", "name": "Not in BUSY", "hsn": "", "gst": 18, "price": 100.0, "mrp": 118.0},
        ])
        aliases = self._aliases(root, [
            {"Branch": "KVR", "Original TAGRO item name": "MS382 OLD BUSY NAME", "TAGRO display name": "MS 382", "BUSY item codes": "A1 | A2", "BUSY alias": "382", "STIHL part number": "11192000261"},
        ])
        busy = self._busy(root, [
            {"Branch": "KVR", "Item Name": "MS382 OLD BUSY NAME", "Part No Normalized": "11192000261", "Alias / Part No": "11192000261", "Parent Group": "STIHL", "Unit": "Nos"},
        ])
        records, stats = build_records(official, tagro_alias_csv=aliases, busy_item_master=busy)
        self.assertEqual(1, len(records))
        self.assertEqual("11192000261", records[0]["sku"])
        self.assertEqual("Pcs", records[0]["unit"])
        self.assertEqual(3, len(records[0]["prices"]))
        self.assertEqual("STIHL June 2026", stats["price_base"])
        self.assertEqual(1, stats["not_introduced_from_full_stihl_catalogue"])
        alias_values = {a["value"] for a in records[0]["aliases"]}
        self.assertIn("MS382 OLD BUSY NAME", alias_values)
        self.assertIn("A1", alias_values)
        self.assertIn("A2", alias_values)
        self.assertFalse(stats["busy_writeback"])
        self.assertFalse(stats["new_non_busy_products_allowed"])

    def test_numeric_duplicate_normalization_is_safe(self):
        root = self._root()
        official = self._official(root, [
            {"type": "MACHINES", "part_no": "11192000261", "name": "MS 382", "hsn": "84678100", "gst": 18, "price": 52260, "mrp": 69067},
            {"type": "MACHINES", "part_no": "1119 200 0261", "name": "MS 382", "hsn": "84678100", "gst": 18.0, "price": 52260.00, "mrp": 69067.0},
        ])
        aliases = self._aliases(root, [{"Branch": "KVR", "Original TAGRO item name": "MS382", "TAGRO display name": "MS 382", "BUSY item codes": "A1", "BUSY alias": "382", "STIHL part number": "11192000261"}])
        busy = self._busy(root, [{"Branch": "KVR", "Item Name": "MS382", "Part No Normalized": "11192000261", "Alias / Part No": "11192000261", "Parent Group": "STIHL", "Unit": "Pcs"}])
        records, stats = build_records(official, tagro_alias_csv=aliases, busy_item_master=busy)
        self.assertEqual(1, len(records))
        self.assertEqual(1, stats["duplicate_official_rows"])

    def test_reel_links_is_flagged_but_multiplier_is_not_invented(self):
        root = self._root()
        official = self._official(root, [{"type": "ACCESSORIES", "part_no": "38740001640", "name": "33RSK Chain reel", "hsn": "82024000", "gst": 18, "price": 1000, "mrp": 1200}])
        aliases = self._aliases(root, [{"Branch": "KVR", "Original TAGRO item name": "33RSK Chain reel RAPID SUPER", "TAGRO display name": "33RSK Chain reel RAPID SUPER", "BUSY item codes": "C1", "BUSY alias": "38740001640", "STIHL part number": "38740001640"}])
        busy = self._busy(root, [{"Branch": "KVR", "Item Name": "33RSK Chain reel RAPID SUPER", "Part No Normalized": "38740001640", "Alias / Part No": "38740001640", "Parent Group": "Accessories", "Unit": "Links"}])
        records, stats = build_records(official, tagro_alias_csv=aliases, busy_item_master=busy)
        self.assertEqual("Links", records[0]["unit"])
        self.assertEqual([], records[0]["unit_conversions"])
        self.assertEqual(1, stats["unit_conversion_candidates"])

    def test_non_equivalent_busy_unit_conflict_is_refused(self):
        root = self._root()
        official = self._official(root, [{"type": "PARTS", "part_no": "11111111111", "name": "Part A", "hsn": "1", "gst": 18}])
        aliases = self._aliases(root, [
            {"Branch": "KVR", "Original TAGRO item name": "Part A", "TAGRO display name": "Part A", "BUSY item codes": "X", "BUSY alias": "A", "STIHL part number": "11111111111"},
            {"Branch": "PKM", "Original TAGRO item name": "Part A", "TAGRO display name": "Part A", "BUSY item codes": "Y", "BUSY alias": "A", "STIHL part number": "11111111111"},
        ])
        busy = self._busy(root, [
            {"Branch": "KVR", "Item Name": "Part A", "Part No Normalized": "11111111111", "Alias / Part No": "11111111111", "Parent Group": "Parts", "Unit": "Pcs"},
            {"Branch": "PKM", "Item Name": "Part A", "Part No Normalized": "11111111111", "Alias / Part No": "11111111111", "Parent Group": "Parts", "Unit": "Links"},
        ])
        with self.assertRaisesRegex(RuntimeError, "unit conflicts"):
            build_records(official, tagro_alias_csv=aliases, busy_item_master=busy)


if __name__ == "__main__":
    unittest.main()
