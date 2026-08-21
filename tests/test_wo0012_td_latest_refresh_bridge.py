from pathlib import Path
import unittest


class TdLatestRefreshBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = Path('scripts/refresh_current_fy_from_td_latest.ps1').read_text(encoding='utf-8')

    def test_selects_exact_five_td_sources(self) -> None:
        self.assertIn("$branches.Count -ne 5", self.text)
        self.assertIn("latest\\db12026.bds", self.text)
        self.assertIn("newest_available_td_snapshot_per_branch", self.text)

    def test_preserves_freshness_separately(self) -> None:
        self.assertIn("heartbeat_state", self.text)
        self.assertIn("heartbeat_checked_at", self.text)
        self.assertIn("source_modified_utc", self.text)
        self.assertIn("source_sha256", self.text)

    def test_adapts_direct_bds_to_existing_zip_stager(self) -> None:
        self.assertIn("Compress-Archive", self.text)
        self.assertIn("kind = 'zip'", self.text)
        self.assertIn("auto_refresh_current_fy.ps1", self.text)

    def test_refresh_is_forced_and_verified_complete(self) -> None:
        self.assertIn("-ThroughDate $ThroughDate -Force", self.text)
        self.assertIn("current_fy_refresh_state.json", self.text)
        self.assertIn("$state.status -ne 'complete'", self.text)

    def test_password_is_not_printed_or_persisted(self) -> None:
        self.assertIn("Read-Host 'Enter the BUSY database password (input is hidden)' -AsSecureString", self.text)
        self.assertIn("Remove-Item Env:\\TAGRO_BUSY_DB_PASSWORD", self.text)


if __name__ == '__main__':
    unittest.main()
