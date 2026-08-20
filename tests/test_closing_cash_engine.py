import unittest
from datetime import date

from src.cash.engine import ClosingCashEngine, CashEngineError
from src.repository.ports import MemoryRepository


class ClosingCashEngineTests(unittest.TestCase):
    def setUp(self):
        self.repo = MemoryRepository()
        self.engine = ClosingCashEngine(self.repo)
        self.day = self.engine.open_day("ent-kvr", date(2026,8,20), 1000, "owner-1")

    def add(self, typ, amount, actor, idem, channel="cash"):
        entry = self.engine.new_entry(self.day.closing_id, typ, amount, actor, idem, channel=channel)
        return self.engine.add_entry(entry)

    def test_cash_arithmetic_excludes_noncash(self):
        self.add("cash_sale", 500, "staff-1", "a")
        self.add("upi_receipt", 700, "staff-1", "b", channel="upi")
        self.add("expense_cash", 100, "staff-1", "c")
        self.add("allocation_cash", 200, "owner-1", "d")
        summary = self.engine.summary(self.day.closing_id)
        self.assertEqual(str(summary.expected_physical_cash), "1200.00")
        self.assertEqual(str(summary.noncash_in), "700.00")

    def test_allocation_is_not_expense_classification(self):
        self.add("allocation_cash", 150, "owner-1", "alloc")
        entries = self.engine.entries(self.day.closing_id)
        self.assertEqual(entries[0].entry_type, "allocation_cash")
        self.assertNotEqual(entries[0].entry_type, "expense_cash")

    def test_service_cash_and_noncash_are_distinct(self):
        self.add("service_cash_receipt", 300, "staff-1", "svc-cash")
        self.add("service_noncash_receipt", 400, "staff-1", "svc-upi", channel="upi")
        summary = self.engine.summary(self.day.closing_id)
        self.assertEqual(str(summary.cash_in), "300.00")
        self.assertEqual(str(summary.noncash_in), "400.00")

    def test_declared_variance_and_lifecycle(self):
        self.add("cash_sale", 500, "staff-1", "s1")
        self.engine.declare_closing(self.day.closing_id, 1490, "owner-1")
        summary = self.engine.summary(self.day.closing_id)
        self.assertEqual(str(summary.variance), "-10.00")
        submitted = self.engine.submit(self.day.closing_id, "owner-1")
        self.assertEqual(submitted.status, "submitted")
        approved = self.engine.approve(self.day.closing_id, "exec-1")
        self.assertEqual(approved.status, "approved")
        with self.assertRaises(CashEngineError):
            self.add("cash_sale", 10, "staff-1", "late")

    def test_supersession_preserves_old_closing(self):
        self.engine.declare_closing(self.day.closing_id, 1000, "owner-1")
        self.engine.submit(self.day.closing_id, "owner-1")
        new = self.engine.supersede(self.day.closing_id, "exec-1", note="Correction after review")
        old = self.engine.get_closing(self.day.closing_id)
        self.assertEqual(old.status, "superseded")
        self.assertEqual(new.supersedes_closing_id, old.closing_id)

    def test_idempotent_offline_replay(self):
        entry = self.engine.new_entry(self.day.closing_id, "cash_sale", 250, "staff-1", "offline-1")
        first = self.engine.add_entry(entry)
        second = self.engine.add_entry(entry)
        self.assertEqual(first.entry_id, second.entry_id)
        self.assertEqual(len(self.engine.entries(self.day.closing_id)), 1)

    def test_changed_payload_with_same_idempotency_is_rejected(self):
        first = self.engine.new_entry(self.day.closing_id, "cash_sale", 250, "staff-1", "offline-2")
        self.engine.add_entry(first)
        changed = self.engine.new_entry(self.day.closing_id, "cash_sale", 260, "staff-1", "offline-2")
        with self.assertRaises(CashEngineError):
            self.engine.add_entry(changed)

    def test_multi_user_entries_keep_actor_identity(self):
        self.add("cash_sale", 200, "staff-1", "m1")
        self.add("cash_receipt", 300, "franchisee-owner", "m2")
        self.add("deposit_cash", 100, "tagro-exec", "m3")
        actors = {x.actor_id for x in self.engine.entries(self.day.closing_id)}
        self.assertEqual(actors, {"staff-1", "franchisee-owner", "tagro-exec"})


if __name__ == "__main__":
    unittest.main()
