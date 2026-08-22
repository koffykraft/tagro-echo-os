from __future__ import annotations

import unittest
from decimal import Decimal

from src.billing import BillingEngine, BillingError, BillingLine, BillingRequest, BusySeriesConfig


class BillingEngineTests(unittest.TestCase):
    def line(self, **kw):
        base = dict(
            product_id="P1",
            description="MS 382",
            quantity=Decimal("1"),
            unit_price_before_tax=Decimal("10000"),
            gst_rate=Decimal("18"),
            discount_before_tax=Decimal("0"),
        )
        base.update(kw)
        return BillingLine(**base)

    def request(self, **kw):
        base = dict(
            enterprise_id="TAGRO",
            branch_id="branch-kvr",
            branch_code="KVR",
            actor_id="user-1",
            actor_role="STAFF",
            customer_id=None,
            customer_name="Cash",
            lines=(self.line(),),
            payment_mode="cash",
            idempotency_key="bill-key-1",
        )
        base.update(kw)
        return BillingRequest(**base)

    def test_bill_calculates_gst_and_total(self):
        bill = BillingEngine().issue(self.request(), {"P1": Decimal("5")})
        self.assertEqual(bill.taxable_total, Decimal("10000.00"))
        self.assertEqual(bill.tax_total, Decimal("1800.00"))
        self.assertEqual(bill.invoice_total, Decimal("11800.00"))
        self.assertEqual(bill.status, "echo_issued")

    def test_idempotent_retry_returns_same_bill(self):
        engine = BillingEngine()
        a = engine.issue(self.request(), {"P1": Decimal("5")})
        b = engine.issue(self.request(), {"P1": Decimal("5")})
        self.assertEqual(a.bill_id, b.bill_id)

    def test_changed_payload_with_same_key_is_rejected(self):
        engine = BillingEngine()
        engine.issue(self.request(), {"P1": Decimal("5")})
        with self.assertRaises(BillingError):
            engine.issue(self.request(customer_name="Different"), {"P1": Decimal("5")})

    def test_insufficient_stock_requires_owner_override(self):
        with self.assertRaises(BillingError):
            BillingEngine().issue(self.request(), {"P1": Decimal("0")})

    def test_owner_can_override_stock_only_with_reason(self):
        engine = BillingEngine()
        with self.assertRaises(BillingError):
            engine.issue(
                self.request(actor_role="OWNER", owner_stock_override=True),
                {"P1": Decimal("0")},
            )
        bill = engine.issue(
            self.request(
                actor_role="OWNER",
                owner_stock_override=True,
                stock_override_reason="Physical stock seen; snapshot stale",
            ),
            {"P1": Decimal("0")},
        )
        self.assertTrue(bill.stock_exception)

    def test_busy_handoff_requires_configured_distinct_series(self):
        engine = BillingEngine()
        bill = engine.issue(self.request(), {"P1": Decimal("5")})
        with self.assertRaises(BillingError):
            engine.prepare_busy_handoff(bill, {})
        handoff = engine.prepare_busy_handoff(
            bill,
            {"KVR": BusySeriesConfig("KVR", "ECHO-KVR", "KVR")},
        )
        self.assertEqual(handoff.voucher_series, "ECHO-KVR")
        self.assertEqual(handoff.status, "queued_not_booked")
        self.assertEqual(handoff.payload["source"], "ECHO")
        self.assertEqual(handoff.payload["echo_bill_id"], bill.bill_id)


if __name__ == "__main__":
    unittest.main()
