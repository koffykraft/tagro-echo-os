from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from src.aws_runtime.billing_runtime import RuntimeBillingError
from src.aws_runtime.billing_runtime_v2 import issue_bill


class BillingTaxGuardTests(unittest.TestCase):
    def _membership(self):
        return {"enterprise_id": "ENT", "capabilities": ["SELL"], "role_code": "OWNER"}

    def _payload(self):
        return {
            "enterprise_id": "ENT",
            "branch_code": "KVR",
            "idempotency_key": "guard-test",
            "payment_mode": "credit",
            "lines": [{"product_id": "P1", "quantity": 1, "unit_price_before_tax": 100, "gst_rate": 18}],
        }

    @patch("src.aws_runtime.billing_runtime_v2._issue_bill")
    @patch("src.aws_runtime.billing_runtime_v2.connect")
    def test_unknown_gst_is_rejected_before_proven_engine(self, connect, delegate):
        conn = MagicMock()
        connect.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchall.return_value = [("P1", None, False)]
        with self.assertRaisesRegex(RuntimeBillingError, "GST incomplete"):
            issue_bill(None, principal_id="PRINCIPAL", membership=self._membership(), payload=self._payload())
        delegate.assert_not_called()

    @patch("src.aws_runtime.billing_runtime_v2._issue_bill")
    @patch("src.aws_runtime.billing_runtime_v2.connect")
    def test_known_gst_delegates_to_proven_engine(self, connect, delegate):
        conn = MagicMock()
        connect.return_value.__enter__.return_value = conn
        conn.execute.return_value.fetchall.return_value = [("P1", 18, True)]
        delegate.return_value = {"bill_id": "B1"}
        result = issue_bill(None, principal_id="PRINCIPAL", membership=self._membership(), payload=self._payload())
        self.assertEqual("B1", result["bill_id"])
        delegate.assert_called_once()


if __name__ == "__main__":
    unittest.main()
