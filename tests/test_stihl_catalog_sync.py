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

    def test_full_catalogue_identity_without_invented_price_date(self):
        root = self._root()
        official = self._official(root, [
            {"type": "MACHINES", "part_no": "11192000261", "name": "MS 382", "hsn": "84678100", "gst": 18.0, "price": 52260.0, "mrp": 69067.0},
            {"type": "PARTS", "part_no": "00001234567", "name": "Service Part", "hsn": "", "gst": None, "price": 100.0, "mrp": 118.0},
        ])
        aliases = self._aliases(root, [
            {"Branch": "KVR", "Original TAGRO item name": "MS382", "TAGRO display name": "MS 382", "BUSY item codes": "A1 | A2", "BUSY alias": "382", "STIHL part number": "11192000261"},
        ])
        busy = self._busy(root, [
            {"Branch": "KVR", "Item Name": "MS382", "Part No Normalized": "11192000261", "Alias / Part No": "11192000261", "Parent Group": "STIHL", "Unit": "Nos"},
        ])

        records, stats = build_records(official, tagro_alias_csv=aliases, busy_item_master=busy, effective_from=None)
        self.assertEqual(2, len(records))
        self.assertEqual(0, stats["prices"])
        self.assertFalse(stats["prices_included"])
        ms382 = next(r for r in records if r["sku"] == "11192000261")
        self.assertEqual("84678100", ms382["hsn_code"])
        self.assertEqual("18", ms382["gst_rate"])
        self.assertEqual("Nos", ms382["unit"])
        self.assertEqual(5, len(ms382["aliases"]))
        incomplete = next(r for r in records if r["sku"] == "00001234567")
        self.assertEqual("", incomplete["hsn_code"])
        self.assertEqual("", incomplete["gst_rate"])

    def test_numeric_duplicate_normalization_and_dated_prices(self):
        root = self._root()
        official = self._official(root, [
            {"type": "MACHINES", "part_no": "11192000261", "name": "MS 382", "hsn": "84678100", "gst": 18, "price": 52260, "mrp": 69067},
            {"type": "MACHINES", "part_no": "1119 200 0261", "name": "MS 382", "hsn": "84678100", "gst": 18.0, "price": 52260.00, "mrp": 69067.0},
        ])
        records, stats = build_records(official, effective_from="2026-06-30")
        self.assertEqual(1, len(records))
        self.assertEqual(1, stats["duplicate_official_rows"])
        self.assertEqual(3, len(records[0]["prices"]))

    def test_alias_collision_is_refused_before_aws(self):
        root = self._root()
        official = self._official(root, [
            {"type": "PARTS", "part_no": "11111111111", "name": "Part A", "hsn": "1", "gst": 18},
            {"type": "PARTS", "part_no": "22222222222", "name": "Part B", "hsn": "2", "gst": 18},
        ])
        aliases = self._aliases(root, [
            {"Branch": "KVR", "Original TAGRO item name": "Same", "TAGRO display name": "Part A", "BUSY item codes": "X", "BUSY alias": "SAME", "STIHL part number": "11111111111"},
            {"Branch": "KVR", "Original TAGRO item name": "Same", "TAGRO display name": "Part B", "BUSY item codes": "X", "BUSY alias": "SAME", "STIHL part number": "22222222222"},
        ])
        with self.assertRaisesRegex(RuntimeError, "alias collisions"):
            build_records(official, tagro_alias_csv=aliases)

    def test_conflicting_known_official_gst_is_refused(self):
        root = self._root()
        official = self._official(root, [
            {"type": "PARTS", "part_no": "11111111111", "name": "Part A", "hsn": "1", "gst": 18},
            {"type": "PARTS", "part_no": "11111111111", "name": "Part A", "hsn": "1", "gst": 12},
        ])
        with self.assertRaisesRegex(RuntimeError, "conflicting official gst"):
            build_records(official)


if __name__ == "__main__":
    unittest.main()
