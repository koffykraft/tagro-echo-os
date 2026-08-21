from __future__ import annotations

import unittest
from datetime import date, datetime, timezone
from decimal import Decimal

from src.bank.normalization import BankTransaction
from src.cash.closing import create_closing
from src.financial.evidence_adapters import ExpenseClassification, collect_expense_evidence
from src.financial.health import PurchasePriceEvidence, SaleLineEvidence
from src.financial.on_call import OwnerOnCall


class OwnerOnCallTests(unittest.TestCase):
    def test_cash_and_bank_expenses_default_to_unclassified(self):
        closing = create_closing("KVR", date(2026, 8, 20), 1000, 500, 0, 100, 0, 1400, "owner")
        bank = BankTransaction(
            "B1", "ST1", "statement.csv", 2, "ACC1", date(2026, 8, 20), None,
            "debit", Decimal("250"), "TRANSFER TO XYZ"
        )
        rows = collect_expense_evidence((closing,), (bank,), {"ACC1": "KVR"})
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r.category is None for r in rows))
        self.assertTrue(all(r.classification_confidence == "unknown" for r in rows))

    def test_explicit_governed_classification_is_used(self):
        closing = create_closing("KVR", date(2026, 8, 20), 1000, 500, 0, 100, 0, 1400, "owner")
        key = f"closing-cash:{closing.closing_id}:expense"
        rows = collect_expense_evidence(
            (closing,), (), classifications={key: ExpenseClassification("rent", "exact")}
        )
        self.assertEqual(rows[0].category, "rent")
        self.assertEqual(rows[0].classification_confidence, "exact")

    def test_owner_snapshot_reports_profit_coverage_and_attention(self):
        sales = (
            SaleLineEvidence("S1", date(2026, 8, 20), "KVR", "A", Decimal("1"), Decimal("500")),
            SaleLineEvidence("S2", date(2026, 8, 20), "PKM", "B", Decimal("1"), Decimal("300")),
        )
        purchases = (
            PurchasePriceEvidence("A", date(2026, 8, 10), Decimal("300"), "KVR", source_ref="P1"),
            PurchasePriceEvidence("A", date(2026, 8, 1), Decimal("320"), "KVR", source_ref="P2"),
        )
        snapshot = OwnerOnCall().snapshot(
            sales,
            purchases,
            start=date(2026, 8, 20),
            end=date(2026, 8, 20),
            cash_position=Decimal("15000"),
            bank_position=Decimal("22000"),
            evidence_as_of=datetime.now(timezone.utc),
        )
        self.assertEqual(snapshot["sales_before_tax"], Decimal("800.00"))
        self.assertEqual(snapshot["estimated_gross_profit_known"], Decimal("190.00"))
        self.assertEqual(snapshot["cost_coverage_pct"], Decimal("50.00"))
        self.assertEqual(snapshot["cash_position"], Decimal("15000"))
        self.assertEqual(snapshot["branches"]["PKM"]["unknown_cost_lines"], 1)
        self.assertEqual(snapshot["attention"][0]["type"], "unknown_cost")
        self.assertEqual(snapshot["status"], "projection_not_accounting_final")

    def test_owner_snapshot_exposes_prism_uncertainty_instead_of_hiding_it(self):
        prism_status = {
            "unresolved_count": 3,
            "unresolved_amount": Decimal("18000"),
            "tight_split_count": 1,
            "tight_split_amount": Decimal("5000"),
            "review_queue": ({"observation_id": "bank:1"},),
        }
        snapshot = OwnerOnCall().snapshot((), (), prism_status=prism_status)
        types = {row["type"] for row in snapshot["attention"]}
        self.assertIn("prism_unresolved", types)
        self.assertIn("prism_tight_split", types)
        self.assertEqual(snapshot["prism_status"]["unresolved_amount"], Decimal("18000"))
        self.assertEqual(snapshot["drilldown"]["prism_review_queue"][0]["observation_id"], "bank:1")


if __name__ == "__main__":
    unittest.main()
