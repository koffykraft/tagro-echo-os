from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.aws_runtime.billing_runtime import RuntimeBillingError
from src.aws_runtime.billing_runtime_v2 import issue_bill
from src.aws_runtime.reference_runtime import reference_search


ROOT = Path(__file__).resolve().parents[1]


class MobileSalesOperationalTests(unittest.TestCase):
    @staticmethod
    def _payload(price="12.84", discount="0"):
        return {
            "enterprise_id": "ENT",
            "branch_code": "KVR",
            "idempotency_key": "mobile-sale-1",
            "payment_mode": "cash",
            "lines": [{
                "product_id": "CHAIN",
                "quantity": 66,
                "unit_price_before_tax": price,
                "discount_before_tax": discount,
                "gst_rate": 18,
            }],
        }

    @staticmethod
    def _membership(role="STAFF"):
        return {"enterprise_id": "ENT", "capabilities": ["SELL"], "role_code": role}

    @staticmethod
    def _connection(rows):
        connection = MagicMock()
        connection.execute.return_value.fetchall.return_value = rows
        manager = MagicMock()
        manager.__enter__.return_value = connection
        return manager, connection

    @patch("src.aws_runtime.reference_runtime.connect")
    def test_product_lookup_preserves_unit_and_current_approved_price(self, connect):
        manager, connection = self._connection([(
            "CHAIN", "36210001640", "36RSC", "36RSC Sawchain", "CHAIN",
            Decimal("18"), "Links", False, "82024000", "36210001640",
            True, Decimal("12.84"), "tagro_approved_sale", date(2026, 8, 25),
        )])
        connect.return_value = manager

        result = reference_search(None, enterprise_id="ENT", kind="products", query="36RSC", branch_code="kvr")
        item = result["items"][0]

        self.assertEqual("Links", item["unit"])
        self.assertEqual("12.84", item["approved_price_before_tax"])
        self.assertEqual("2026-08-25", item["approved_price_effective_from"])
        sql, parameters = connection.execute.call_args.args
        self.assertIn("tagro_approved_sale", sql)
        self.assertIn("pa.branch_code", sql)
        self.assertEqual(("KVR", "KVR"), parameters[:2])
        self.assertEqual(sql.count("%s"), len(parameters))

    @patch("src.aws_runtime.reference_runtime.connect")
    def test_missing_approved_price_is_unknown_not_zero(self, connect):
        manager, _ = self._connection([(
            "CHAIN", "36210001640", "36RSC", "36RSC Sawchain", "CHAIN",
            Decimal("18"), "Links", False, "82024000", "36210001640",
            True, None, None, None,
        )])
        connect.return_value = manager

        item = reference_search(None, enterprise_id="ENT", kind="products", branch_code="KVR")["items"][0]
        self.assertIsNone(item["approved_price_before_tax"])

    @patch("src.aws_runtime.billing_runtime_v2._issue_bill")
    @patch("src.aws_runtime.billing_runtime_v2.connect")
    def test_staff_cannot_sell_without_owner_approved_price(self, connect, delegate):
        tax, _ = self._connection([("CHAIN", Decimal("18"), True)])
        prices, _ = self._connection([("CHAIN", None)])
        connect.side_effect = [tax, prices]

        with self.assertRaisesRegex(RuntimeBillingError, "owner approval required"):
            issue_bill(None, principal_id="STAFF", membership=self._membership(), payload=self._payload())
        delegate.assert_not_called()

    @patch("src.aws_runtime.billing_runtime_v2._issue_bill")
    @patch("src.aws_runtime.billing_runtime_v2.connect")
    def test_staff_cannot_change_owner_approved_price(self, connect, delegate):
        tax, _ = self._connection([("CHAIN", Decimal("18"), True)])
        prices, _ = self._connection([("CHAIN", Decimal("12.84"))])
        connect.side_effect = [tax, prices]

        with self.assertRaisesRegex(RuntimeBillingError, "differs from the approved TAGRO price"):
            issue_bill(None, principal_id="STAFF", membership=self._membership(), payload=self._payload("11.00"))
        delegate.assert_not_called()

    @patch("src.aws_runtime.billing_runtime_v2._issue_bill")
    @patch("src.aws_runtime.billing_runtime_v2.connect")
    def test_staff_cannot_bypass_control_with_discount(self, connect, delegate):
        tax, _ = self._connection([("CHAIN", Decimal("18"), True)])
        prices, _ = self._connection([("CHAIN", Decimal("12.84"))])
        connect.side_effect = [tax, prices]

        with self.assertRaisesRegex(RuntimeBillingError, "discount requires owner approval"):
            issue_bill(None, principal_id="STAFF", membership=self._membership(), payload=self._payload(discount="5"))
        delegate.assert_not_called()

    @patch("src.aws_runtime.billing_runtime_v2._issue_bill")
    @patch("src.aws_runtime.billing_runtime_v2.connect")
    def test_staff_approved_price_reaches_existing_atomic_engine(self, connect, delegate):
        tax, _ = self._connection([("CHAIN", Decimal("18"), True)])
        prices, _ = self._connection([("CHAIN", Decimal("12.84"))])
        connect.side_effect = [tax, prices]
        delegate.return_value = {"bill_id": "SALE-1"}

        result = issue_bill(None, principal_id="STAFF", membership=self._membership(), payload=self._payload())

        self.assertEqual("SALE-1", result["bill_id"])
        delegate.assert_called_once()

    @patch("src.aws_runtime.billing_runtime_v2._issue_bill")
    @patch("src.aws_runtime.billing_runtime_v2.connect")
    def test_owner_can_set_rate_while_controlled_price_book_is_built(self, connect, delegate):
        tax, _ = self._connection([("CHAIN", Decimal("18"), True)])
        connect.return_value = tax
        delegate.return_value = {"bill_id": "OWNER-SALE-1"}

        result = issue_bill(None, principal_id="OWNER", membership=self._membership("OWNER"), payload=self._payload())

        self.assertEqual("OWNER-SALE-1", result["bill_id"])
        self.assertEqual(1, connect.call_count)

    def test_mobile_page_shows_real_units_and_keeps_staff_rate_locked(self):
        text = (ROOT / "web" / "billing.html").read_text(encoding="utf-8")
        self.assertIn('class="unit"', text)
        self.assertIn("row.unit=String(p.unit||'').trim()", text)
        self.assertIn("approved_price_before_tax", text)
        self.assertIn("(isOwner?'':' readonly')", text)
        self.assertIn("Choose a verified customer or clear the field for a cash sale", text)
        self.assertIn("billing-product-cache-v1", text)
        self.assertIn("billing-context-v1", text)
        self.assertIn("billing-branches-v1", text)
        self.assertNotIn("Stock truth", text)

    def test_branch_scoped_reference_keeps_existing_callers_compatible(self):
        runtime = (ROOT / "web" / "runtime-client.js").read_text(encoding="utf-8")
        handler = (ROOT / "src" / "aws_runtime" / "handler.py").read_text(encoding="utf-8")
        self.assertIn("{branchCode=''}={}", runtime)
        self.assertIn("p.set('branch'", runtime)
        self.assertIn('reference_options["branch_code"]', handler)


if __name__ == "__main__":
    unittest.main()
