from pathlib import Path
import unittest


class HistoricalBootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.launcher = Path('scripts/start_historical_echo_sweep.ps1').read_text(encoding='utf-8')
        cls.builder = Path('scripts/build_sealed_historical_from_canonical.py').read_text(encoding='utf-8')

    def test_launcher_falls_back_to_canonical_history(self):
        self.assertIn('tagro_history.sqlite', self.launcher)
        self.assertIn('build_sealed_historical_from_canonical.py', self.launcher)
        self.assertIn('rebuilding locally from canonical history', self.launcher)

    def test_builder_hard_stops_at_locked_boundary(self):
        self.assertIn('BOUNDARY = "2026-03-31"', self.builder)
        self.assertIn('where vch_date<=?', self.builder)
        self.assertIn("out_max>BOUNDARY", self.builder)

    def test_builder_uses_verified_catalog_count_when_available(self):
        self.assertIn("warehouse_catalog.json", self.builder)
        self.assertIn('Historical voucher count differs from verified catalog', self.builder)

    def test_source_is_read_only_and_output_verified(self):
        self.assertIn('?mode=ro', self.builder)
        self.assertIn("pragma foreign_key_check", self.builder)
        self.assertIn("pragma quick_check", self.builder)
        self.assertIn("canonical_write':False", self.builder)

    def test_launcher_starts_worker_only_after_preflight(self):
        bootstrap = self.launcher.index('& python $builder')
        preflight = self.launcher.index('Historical preflight:')
        start = self.launcher.index('Start-Process')
        self.assertLess(bootstrap, preflight)
        self.assertLess(preflight, start)


if __name__ == '__main__':
    unittest.main()
