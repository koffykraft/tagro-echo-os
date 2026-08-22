from __future__ import annotations

import unittest
from decimal import Decimal

from src.billing import (
    BillingEngine,
    BillingError,
    BillingLine,
    BillingRequest,
    BusyBillingReconciler,
    BusySeriesConfig,
)


class BusyBillingReconciliationTests(unittest.TestCase):
    def handoff(self):
        engine = BillingEngine()
        request = BillingRequest(
            enterprise_id="TAGRO",
            branch_id="branch-kvr",
            branch_code="KVR",
            actor_id="staff-1",
            actor_role="STAFF",
            customer_id=None,
            customer_name="Cash",
            lines=(
                BillingLine(
                    product_id="P1",
                    description="MS 382",
                    quantity=Decimal("1"),
                    unit_price_before_tax=Decimal("10000"),
                    gst_rate=Decimal("18"),
                ),
            ),
            payment_mode="cash",
            idempotency_key="reconcile-test-1",
        )
        bill = engine.issue(request, {"P1": Decimal("2")})
        return engine.prepare_busy_handoff(
            bill,
            {"KVR": BusySeriesConfig("KVR", "ECHO-KVR", "KVR")},
        )

    def test_handoff_remains_unbooked_until_external_confirmation(self):
        handoff = self.handoff()
        r = BusyBillingReconciler()
        queued = r.queued(handoff)
        submitted = r.submitted(
            handoff,
            submitted_payload_hash=handoff.payload_hash,
            evidence_ref="transport:001",
        )
        self.assertEqual(queued.state, "queued_not_booked")
        self.assertEqual(submitted.state, "submitted_not_confirmed")
        self.assertIsNone(submitted.busy_voucher_ref)

    def test_booking_requires_same_payload_hash_and_busy_reference(self):
        handoff = self.handoff()
        r = BusyBillingReconciler()
        with self.assertRaises(BillingError):
            r.confirm_booked(
                handoff,
                confirmed_payload_hash="wrong",
                busy_voucher_ref="KVR/ECHO/1",
                evidence_ref="busy-readback:001",
            )
        with self.assertRaises(BillingError):
            r.confirm_booked(
                handoff,
                confirmed_payload_hash=handoff.payload_hash,
                busy_voucher_ref="",
                evidence_ref="busy-readback:001",
            )
        confirmed = r.confirm_booked(
            handoff,
            confirmed_payload_hash=handoff.payload_hash,
            busy_voucher_ref="KVR/ECHO/1",
            evidence_ref="busy-readback:001",
        )
        self.assertEqual(confirmed.state, "booked_confirmed")
        self.assertEqual(confirmed.busy_voucher_ref, "KVR/ECHO/1")

    def test_rejection_is_explicit_evidence_not_silent_failure(self):
        handoff = self.handoff()
        r = BusyBillingReconciler()
        rejected = r.reject(
            handoff,
            reason="BUSY validation rejected GST party mapping",
            evidence_ref="busy-error:009",
        )
        self.assertEqual(rejected.state, "rejected")
        self.assertIn("GST", rejected.reason)
        with self.assertRaises(BillingError):
            r.reject(handoff, reason="", evidence_ref="busy-error:010")


if __name__ == "__main__":
    unittest.main()
