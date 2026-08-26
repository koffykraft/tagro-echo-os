from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PaymentReceiptRuntimeContractTests(unittest.TestCase):
    def test_noncredit_sale_creates_separate_unreconciled_receipt_evidence(self):
        text = (ROOT / "src/aws_runtime/billing_runtime.py").read_text(encoding="utf-8")
        self.assertIn("insert into payment_receipts", text)
        self.assertIn("insert into payment_allocations", text)
        self.assertIn("payment.receipt_claimed", text)
        self.assertIn("staff_affirmed_unreconciled", text)
        self.assertIn('payment_status = "unpaid" if payment_mode == "credit" else "receipt_claimed_unreconciled"', text)
        self.assertNotIn('payment_status = "unpaid" if payment_mode == "credit" else "paid"', text)

    def test_credit_sale_does_not_create_payment_identity(self):
        text = (ROOT / "src/aws_runtime/billing_runtime.py").read_text(encoding="utf-8")
        self.assertIn('payment_id = None if payment_mode == "credit"', text)
        self.assertIn('payment_evidence_state = "none" if payment_mode == "credit"', text)

    def test_payment_event_explicitly_refuses_reconciliation_claim(self):
        text = (ROOT / "src/aws_runtime/billing_runtime.py").read_text(encoding="utf-8")
        self.assertIn('"reconciled": False', text)
        self.assertIn('"claim": "staff_affirmed_receipt_not_reconciled"', text)
        sql = (ROOT / "schemas/business/payment_receipt_evidence_v0_4.sql").read_text(encoding="utf-8").lower()
        self.assertIn("staff affirmation is not bank/cash reconciliation", sql)
        self.assertNotIn("references bank_transactions", sql)


if __name__ == "__main__":
    unittest.main()
