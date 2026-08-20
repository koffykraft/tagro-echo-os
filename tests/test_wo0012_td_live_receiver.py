from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ingest_td_live_to_aws_runtime.ps1"
CONFIG = ROOT / "config" / "td_live_sources.json"


class TdLiveReceiverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.script = SCRIPT.read_text(encoding="utf-8").lower()
        cls.config = json.loads(CONFIG.read_text(encoding="utf-8"))

    def test_exact_five_branch_sources(self) -> None:
        branches = [row["branch"] for row in self.config["branches"]]
        self.assertEqual(branches, ["KVR", "PKM", "NDD", "MDM", "SKT"])
        for row in self.config["branches"]:
            self.assertIn("td2026", row["outbox"].lower())
            self.assertTrue(row["outbox"].lower().endswith("\\outbox"))

    def test_heartbeat_and_snapshot_are_verified(self) -> None:
        self.assertIn("heartbeat.json", self.script)
        self.assertIn("db12026.bds", self.script)
        self.assertIn("snapshot_hash_mismatch", self.script)
        self.assertIn("aws_intake_copy_hash_mismatch", self.script)

    def test_staleness_is_explicit(self) -> None:
        self.assertIn("staleminutes", self.script)
        self.assertIn("heartbeat_stale", self.script)
        self.assertIn("status = 'stale'", self.script)

    def test_receiver_does_not_claim_canonical_write(self) -> None:
        self.assertIn("canonical_write = $false", self.script)
        for forbidden in ("insert into branches", "update branches", "record_observations"):
            self.assertNotIn(forbidden, self.script)

    def test_runtime_destination_is_td_live_intake(self) -> None:
        self.assertIn("intake\\td-live", self.script)
        self.assertIn("state\\td-live", self.script)
        self.assertIn("archive\\td-live", self.script)


if __name__ == "__main__":
    unittest.main()
