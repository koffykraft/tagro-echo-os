from pathlib import Path
import unittest


class TdLiveInstallerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = Path('scripts/install_td_live_receiver.ps1').read_text(encoding='utf-8')

    def test_uses_aws_runtime_and_unattended_administrator_identity(self) -> None:
        self.assertIn("T:\\TAGRO_AWS_RUNTIME", self.text)
        self.assertIn('$env:COMPUTERNAME\\Administrator', self.text)
        self.assertIn('Get-Credential', self.text)
        self.assertIn('-RunLevel Highest', self.text)

    def test_installs_exact_live_receiver_and_config(self) -> None:
        self.assertIn('ingest_td_live_to_aws_runtime.ps1', self.text)
        self.assertIn('td_live_sources.json', self.text)
        self.assertIn('raw.githubusercontent.com/koffykraft/tagro-echo-os', self.text)
        self.assertIn("@($parsed.branches).Count -ne 5", self.text)

    def test_schedules_five_minute_non_overlapping_runs(self) -> None:
        self.assertIn("New-TimeSpan -Minutes 5", self.text)
        self.assertIn('MultipleInstances IgnoreNew', self.text)
        self.assertIn("New-TimeSpan -Minutes 4", self.text)

    def test_performs_immediate_verification_run_and_requires_state_file(self) -> None:
        self.assertIn('& $ps -NoProfile -ExecutionPolicy Bypass -File $receiver', self.text)
        self.assertIn("state\\td-live\\latest.json", self.text)
        self.assertIn("TD receiver installed, but no state file was produced", self.text)


if __name__ == '__main__':
    unittest.main()
