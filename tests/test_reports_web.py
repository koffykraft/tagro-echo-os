from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ReportsWebTests(unittest.TestCase):
    def test_reports_hub_links_financial_health_to_owner_on_call(self):
        text = (ROOT / "web" / "reports.html").read_text(encoding="utf-8")
        self.assertIn('href="on-call.html"', text)
        self.assertIn("Financial Health", text)

    def test_local_report_counts_are_explicitly_not_sync_confirmation(self):
        text = (ROOT / "web" / "reports.html").read_text(encoding="utf-8")
        self.assertIn("LOCAL DEVICE EVIDENCE", text)
        self.assertIn("not synchronization confirmation", text)
        self.assertIn("LOCAL DRAFT · NOT ISSUED", text)

    def test_reports_utility_is_retained_but_business_is_primary_home_projection(self):
        index = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        sw = (ROOT / "web" / "sw.js").read_text(encoding="utf-8")
        self.assertTrue((ROOT / "web" / "reports.html").is_file())
        self.assertIn('href="business.html"', index)
        self.assertNotIn('href="reports.html"', index)
        self.assertNotIn("'./reports.html'", sw)


if __name__ == "__main__":
    unittest.main()
