from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ReportsWebTests(unittest.TestCase):
    def test_reports_hub_links_financial_health_to_owner_on_call(self):
        text = (ROOT / "web" / "reports.html").read_text(encoding="utf-8")
        self.assertIn('href="on-call.html"', text)
        self.assertIn("Financial Health", text)
        self.assertIn("estimated COGS", text)

    def test_local_report_counts_are_explicitly_not_sync_confirmation(self):
        text = (ROOT / "web" / "reports.html").read_text(encoding="utf-8")
        self.assertIn("LOCAL DEVICE EVIDENCE", text)
        self.assertIn("not synchronization confirmation", text)
        self.assertIn("without financial or historical classification", text)

    def test_reports_hub_reads_canonical_echo_form_state_without_reclassifying_it(self):
        text = (ROOT / "web" / "reports.html").read_text(encoding="utf-8")
        self.assertIn("'echo.form.'+type", text)
        for form in ("closing", "invoice", "service", "purchase", "stock", "receipt", "payment"):
            self.assertIn(f"presence('{form}')", text)
        self.assertIn("canonicalView(type)", text)
        self.assertNotIn("reconciliation_status='matched'", text)

    def test_reports_hub_links_canonical_forms_lane(self):
        text = (ROOT / "web" / "reports.html").read_text(encoding="utf-8")
        self.assertIn('href="forms/index.html"', text)
        self.assertIn('href="forms/closing-cash.html"', text)
        self.assertIn('href="forms/form.html?type=invoice"', text)
        self.assertIn('href="forms/form.html?type=stock"', text)

    def test_reports_page_is_linked_and_cached(self):
        index = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        sw = (ROOT / "web" / "sw.js").read_text(encoding="utf-8")
        self.assertIn('href="reports.html"', index)
        self.assertIn("'./reports.html'", sw)


if __name__ == "__main__":
    unittest.main()
