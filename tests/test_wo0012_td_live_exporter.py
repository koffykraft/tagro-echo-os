from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "export_td_live_phase1.py"
SPEC = importlib.util.spec_from_file_location("export_td_live_phase1", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TdLiveExporterTests(unittest.TestCase):
    def test_feed_state_is_not_operational_state(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "latest.json"
            state.write_text(json.dumps({
                "schema": "tagro.echo-os.td-live-intake-state/1",
                "checked_at": "2026-08-20T13:30:00+00:00",
                "canonical_write": False,
                "results": [
                    {"branch": "KVR", "status": "verified_current", "age_minutes": 1.2,
                     "source_last_modified": "2026-08-20T13:28:00+00:00"},
                    {"branch": "NDD", "status": "stale", "age_minutes": 120.0},
                ],
            }), encoding="utf-8")
            package = MODULE.build_package(state)
        dims = [o["dimension_code"] for o in package["observations"]]
        self.assertIn("branch.feed_state", dims)
        self.assertIn("branch.feed_age_minutes", dims)
        self.assertNotIn("branch.operational_state", dims)
        states = [o["value"] for o in package["observations"] if o["dimension_code"] == "branch.feed_state"]
        self.assertEqual(states, ["verified_current", "stale"])

    def test_package_remains_observation_only(self) -> None:
        text = MODULE_PATH.read_text(encoding="utf-8").lower()
        self.assertIn("verified_live_feed_health", text)
        for forbidden in ("insert into branches", "update branches", "canonical_write"):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
