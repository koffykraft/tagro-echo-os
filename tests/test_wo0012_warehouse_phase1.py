from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.export_warehouse_phase1 import export_phase1, sha256


class Wo0012WarehousePhase1Tests(unittest.TestCase):
    def _warehouse(self, root: Path) -> Path:
        (root / "databases").mkdir(parents=True)
        (root / "manifests").mkdir(parents=True)
        planar = root / "databases" / "planar.sqlite"
        with sqlite3.connect(planar) as db:
            db.execute("create table branches(branch_id text primary key,name text,status text)")
            db.executemany(
                "insert into branches values(?,?,?)",
                [("KVR", "KVR", "active"), ("OYR", "OYR", "historical")],
            )
        manifest = {
            "run_id": "test-run",
            "completed_at": "2026-08-20T12:00:00+05:30",
            "databases": {"planar": {"sha256": sha256(planar)}},
        }
        (root / "manifests" / "latest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return planar

    def test_export_is_branch_observation_package_not_canonical_write(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._warehouse(root)
            package = export_phase1(root)
            self.assertEqual(package["source_class"], "warehouse_derived_historical_backbone")
            self.assertEqual(package["phase"], "warehouse_phase1_branches")
            self.assertEqual(len(package["observations"]), 6)
            self.assertTrue(all(o["subject_kind"] == "branch" for o in package["observations"]))
            self.assertFalse(any("canonical" in key for key in package for _ in [0]))

    def test_derived_operational_state_is_lower_confidence(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._warehouse(root)
            package = export_phase1(root)
            state = [o for o in package["observations"] if o["dimension_code"] == "branch.operational_state"]
            identity = [o for o in package["observations"] if o["dimension_code"] == "branch.code"]
            self.assertTrue(all(o["confidence"] < 1.0 for o in state))
            self.assertTrue(all(o["confidence"] == 1.0 for o in identity))

    def test_digest_drift_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            planar = self._warehouse(root)
            manifest_path = root / "manifests" / "latest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["databases"]["planar"]["sha256"] = "0" * 64
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaises(RuntimeError):
                export_phase1(root)

    def test_sqlite_is_opened_read_only(self) -> None:
        text = (Path(__file__).resolve().parents[1] / "scripts" / "export_warehouse_phase1.py").read_text(encoding="utf-8")
        self.assertIn("?mode=ro", text)
        self.assertNotIn("insert into branches", text.lower())
        self.assertNotIn("update branches", text.lower())
        self.assertNotIn("delete from branches", text.lower())


if __name__ == "__main__":
    unittest.main()
