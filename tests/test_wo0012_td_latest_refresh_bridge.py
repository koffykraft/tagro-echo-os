from pathlib import Path
import re
import unittest


class TdLatestRefreshBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = Path('scripts/refresh_current_fy_from_td_latest.ps1').read_text(encoding='utf-8')

    def test_selects_exact_five_td_sources(self) -> None:
        self.assertIn("$branches.Count -ne 5", self.text)
        self.assertIn("@('KVR','PKM','NDD','MDM','SKT')", self.text)
        self.assertIn("latest\\db12026.bds", self.text)
        self.assertIn("newest_available_td_snapshot_per_branch", self.text)

    def test_preserves_freshness_separately(self) -> None:
        self.assertIn("heartbeat_state", self.text)
        self.assertIn("heartbeat_checked_at", self.text)
        self.assertIn("source_modified_utc", self.text)
        self.assertIn("source_sha256", self.text)

    def test_adapts_direct_bds_to_existing_zip_stager(self) -> None:
        self.assertIn("Compress-Archive", self.text)
        self.assertIn("tar.exe -tf", self.text)
        self.assertIn("kind = 'zip'", self.text)
        self.assertIn("auto_refresh_current_fy.ps1", self.text)

    def test_preflight_parses_and_checks_all_runtime_dependencies(self) -> None:
        self.assertIn('Assert-PowerShellParses', self.text)
        for dependency in (
            'stage_busy_fy.ps1',
            'export_busy_fy.ps1',
            'complete_canonical_refresh.ps1',
            'build_history_db.py',
            'build_fluid_partition.py',
            'build_purchase_cost_evidence.py',
        ):
            self.assertIn(dependency, self.text)
        for command in ('Compress-Archive', 'Get-FileHash', 'tar.exe', 'python'):
            self.assertIn(f"Assert-Command '{command}'", self.text)
        self.assertIn('Microsoft.ACE.OLEDB.12.0', self.text)
        self.assertIn('Microsoft.Jet.OLEDB.4.0', self.text)

    def test_full_busy_open_export_preflight_happens_before_refresh(self) -> None:
        stage = self.text.index('& $stageScript')
        export = self.text.index('& $exportScript')
        refresh = self.text.index('& $refresh')
        self.assertLess(stage, export)
        self.assertLess(export, refresh)
        self.assertIn('sourceRecordCount -ne 5', self.text)
        self.assertIn('FULL PREFLIGHT PASSED - no canonical write has occurred.', self.text)
        self.assertIn('[switch]$PreflightOnly', self.text)

    def test_downstream_python_is_forced_to_aws_runtime_root(self) -> None:
        self.assertIn('$env:TAGRO_AWS_RUNTIME_ROOT = $RuntimeRoot', self.text)

    def test_refresh_is_forced_and_verified_complete(self) -> None:
        self.assertIn("-ThroughDate $ThroughDate -Force", self.text)
        self.assertIn("current_fy_refresh_state.json", self.text)
        self.assertIn("$state.status -ne 'complete'", self.text)

    def test_password_is_not_printed_or_persisted(self) -> None:
        self.assertIn("Read-Host 'Enter the BUSY database password (input is hidden)' -AsSecureString", self.text)
        self.assertIn("Remove-Item Env:\\TAGRO_BUSY_DB_PASSWORD", self.text)

    def test_no_ambiguous_variable_colon_interpolation(self) -> None:
        # "$name:" is invalid in interpolation; scoped forms such as "$env:NAME" are valid PowerShell.
        offenders = re.findall(r'\$(?!env:|global:|script:|local:|private:)[A-Za-z_][A-Za-z0-9_]*:', self.text)
        self.assertEqual([], offenders, f'ambiguous PowerShell variable interpolation: {offenders}')


if __name__ == '__main__':
    unittest.main()
