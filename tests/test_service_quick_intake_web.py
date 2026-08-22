from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ServiceQuickIntakeWebTests(unittest.TestCase):
    def test_primary_service_intake_is_customer_machine_complaint_accept(self):
        text = (ROOT / "web" / "service.html").read_text(encoding="utf-8")
        self.assertIn("Customer → Machine → Complaint → Accept", text)
        self.assertIn('id="customer"', text)
        self.assertIn('id="model"', text)
        self.assertIn('id="complaint"', text)
        self.assertIn('id="accept"', text)

    def test_secondary_details_are_collapsed(self):
        text = (ROOT / "web" / "service.html").read_text(encoding="utf-8")
        self.assertIn('<details id="more"', text)
        self.assertIn("More details", text)
        self.assertIn('id="serial"', text)
        self.assertIn('id="branch"', text)

    def test_branch_is_remembered_locally_not_guessed(self):
        text = (ROOT / "web" / "service.html").read_text(encoding="utf-8")
        self.assertIn("tagro-service-branch", text)
        self.assertIn("Select the counter once", text)


if __name__ == "__main__":
    unittest.main()
