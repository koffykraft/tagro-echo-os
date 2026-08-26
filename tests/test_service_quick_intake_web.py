from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ServiceQuickIntakeWebTests(unittest.TestCase):
    def test_primary_service_intake_is_customer_machine_complaint_accept(self):
        text = (ROOT / "web" / "service.html").read_text(encoding="utf-8")
        self.assertIn("Customer → Machine → Complaint → ACCEPT", text)
        self.assertIn('id="customerSearch"', text)
        self.assertIn('id="customerId"', text)
        self.assertIn('id="model"', text)
        self.assertIn('id="complaint"', text)
        self.assertIn('id="accept"', text)
        self.assertIn("EchoRuntime.reference('customers'", text)

    def test_secondary_details_are_collapsed(self):
        text = (ROOT / "web" / "service.html").read_text(encoding="utf-8")
        self.assertIn("<details>", text)
        self.assertIn("More details", text)
        self.assertIn('id="serial"', text)
        self.assertIn('id="productSearch"', text)
        self.assertIn('id="branch"', text)

    def test_branch_is_remembered_locally_not_guessed(self):
        text = (ROOT / "web" / "service.html").read_text(encoding="utf-8")
        self.assertIn("echo.service.branch", text)
        self.assertIn("Select counter", text)
        self.assertIn("localStorage.getItem", text)
        self.assertIn("localStorage.setItem", text)
        self.assertNotIn("else if(b.items.length===1)", text)


if __name__ == "__main__":
    unittest.main()
