from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.export_aws_runtime_branch_state import export_branch_state


class AwsRuntimeBranchExportTests(unittest.TestCase):
    def _fixture(self, root: Path) -> None:
        state_dir = root / "data/canonical/tagro-data-platform/state"
        verify_dir = root / "data/canonical/tagro-data-platform/verification"
        state_dir.mkdir(parents=True)
        verify_dir.mkdir(parents=True)

        branches = ["KVR", "PKM", "NDD", "MDM", "SKT"]
        state = {
            "status": "complete",
            "checked_at": "2026-08-17T20:51:14+05:30",
            "through_date": "2026-08-15",
            "financial_year": "2026-27",
            "sources": [{"branch": b, "exists": True} for b in branches],
            "extra": {"database_sha256": "abc123"},
        }
        verify = {
            "batch_id": "batch-1",
            "verified": True,
            "quick_check": "ok",
            "foreign_key_errors": 0,
            "database": {"sha256": "abc123"},
            "coverage": [{"branch": b} for b in branches],
        }
        (state_dir / "current_fy_refresh_state.json").write_text(json.dumps(state), encoding="utf-8")
        (verify_dir / "refresh_through_2026-08-15.json").write_text(json.dumps(verify), encoding="utf-8")

    def test_exports_five_branches_three_dimensions_each(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            package = export_branch_state(root)
            self.assertEqual(package["source_system"], "TAGRO_AWS_RUNTIME")
            self.assertEqual(package["source_class"], "aws_runtime_verified_current_fy")
            self.assertEqual(package["through_date"], "2026-08-15")
            self.assertEqual(len(package["observations"]), 15)
            states = [o for o in package["observations"] if o["dimension_code"] == "branch.operational_state"]
            self.assertEqual(len(states), 5)
            self.assertTrue(all(o["value"] == "active" and o["confidence"] == 0.95 for o in states))

    def test_refuses_unverified_source(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._fixture(root)
            verify_path = root / "data/canonical/tagro-data-platform/verification/refresh_through_2026-08-15.json"
            verify = json.loads(verify_path.read_text(encoding="utf-8"))
            verify["verified"] = False
            verify_path.write_text(json.dumps(verify), encoding="utf-8")
            with self.assertRaises(RuntimeError):
                export_branch_state(root)


if __name__ == "__main__":
    unittest.main()
