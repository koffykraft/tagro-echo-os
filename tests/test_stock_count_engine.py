from __future__ import annotations

import unittest
from decimal import Decimal

from src.stock_count import CountStatus, StockCountEngine


class StockCountEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = StockCountEngine()
        self.count = self.engine.start(branch_id="branch-kvr", location="Main store", actor_id="staff-1")

    def test_finalized_count_reports_variance_without_mutating_stock(self):
        self.engine.record_line(
            self.count.count_id,
            item_key="P1",
            description="MS 382",
            counted_quantity="8",
            reference_quantity="10",
            evidence_refs=("photo:E1",),
        )
        final = self.engine.finalize(self.count.count_id, actor_id="staff-1")
        self.assertEqual(final.status, CountStatus.FINALIZED)
        self.assertEqual(final.variances[0].variance, Decimal("-2"))
        self.assertEqual(self.engine.events[-1]["event_type"], "count_finalized_without_stock_mutation")

    def test_unknown_reference_never_becomes_adjustment(self):
        self.engine.record_line(
            self.count.count_id,
            item_key="P1",
            description="Unknown reference item",
            counted_quantity="8",
            reference_quantity=None,
        )
        self.engine.finalize(self.count.count_id, actor_id="staff-1")
        with self.assertRaises(ValueError):
            self.engine.propose_adjustment(self.count.count_id, actor_id="staff-1", reason="Physical count differs")

    def test_variance_proposal_is_not_operational_until_owner_admits(self):
        self.engine.record_line(
            self.count.count_id,
            item_key="P1",
            description="MS 382",
            counted_quantity="8",
            reference_quantity="10",
            evidence_refs=("photo:E1", "sheet:E2"),
        )
        self.engine.finalize(self.count.count_id, actor_id="staff-1")
        proposed = self.engine.propose_adjustment(
            self.count.count_id,
            actor_id="manager-1",
            reason="Reconciled physical recount",
        )
        self.assertEqual(proposed.status, CountStatus.ADJUSTMENT_PROPOSED)
        with self.assertRaises(PermissionError):
            self.engine.admitted_adjustment_payload(self.count.count_id)

        admitted = self.engine.admit_adjustment(
            self.count.count_id,
            owner_actor_id="owner-1",
            owner_note="Admit reconciled physical count variance",
        )
        self.assertEqual(admitted.status, CountStatus.ADJUSTMENT_ADMITTED)
        payload = self.engine.admitted_adjustment_payload(self.count.count_id)
        self.assertEqual(payload["owner_actor_id"], "owner-1")
        self.assertEqual(payload["lines"][0]["variance"], Decimal("-2"))
        self.assertEqual(payload["lines"][0]["evidence_refs"], ("photo:E1", "sheet:E2"))

    def test_owner_admission_requires_note(self):
        self.engine.record_line(
            self.count.count_id,
            item_key="P1",
            description="MS 382",
            counted_quantity="9",
            reference_quantity="10",
        )
        self.engine.finalize(self.count.count_id, actor_id="staff-1")
        self.engine.propose_adjustment(self.count.count_id, actor_id="manager-1", reason="Recount complete")
        with self.assertRaises(ValueError):
            self.engine.admit_adjustment(self.count.count_id, owner_actor_id="owner-1", owner_note="")


if __name__ == "__main__":
    unittest.main()
