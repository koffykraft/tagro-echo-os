from __future__ import annotations

import json
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from src.aws_runtime.financial_expense_runtime import (
    cash_entry_expense_evidence,
    expense_evidence_diagnostics,
    imported_accounting_expense_evidence,
)
from src.financial.health import ExpenseRole


class FakeConn:
    def __init__(self, rows):
        self.rows = rows
        self.sql = ""
        self.params = ()

    def execute(self, sql, params):
        self.sql = sql
        self.params = params
        return self

    def fetchall(self):
        return self.rows


class RuntimeExpenseEvidenceTests(unittest.TestCase):
    def test_cash_entry_reader_only_requests_explicit_expense_types(self):
        conn = FakeConn([
            (
                "e1", date(2026, 8, 21), Decimal("250.00"), "KVR", "courier",
                "branch_operating_expense", "exact", "receipt:1", "", ""
            ),
            (
                "e2", date(2026, 8, 21), Decimal("100.00"), "KVR", None,
                "unknown", "unknown", "", "", "unclear"
            ),
        ])
        rows = cash_entry_expense_evidence(conn, "ent", branch="KVR")
        self.assertIn("entry_type in ('expense_cash','expense_noncash')", conn.sql)
        self.assertNotIn("deposit_cash", conn.sql)
        self.assertEqual(ExpenseRole.BRANCH, rows[0].role)
        self.assertEqual("exact", rows[0].classification_confidence)
        self.assertEqual(ExpenseRole.UNKNOWN, rows[1].role)
        self.assertIsNone(rows[1].category)

    def test_partial_cash_classification_is_downgraded_to_unknown(self):
        conn = FakeConn([
            (
                "e1", date(2026, 8, 21), Decimal("250.00"), "KVR", "courier",
                "branch_operating_expense", "unknown", "receipt:1", "", ""
            )
        ])
        row = cash_entry_expense_evidence(conn, "ent")[0]
        self.assertEqual(ExpenseRole.UNKNOWN, row.role)
        self.assertEqual("unknown", row.classification_confidence)
        self.assertIsNone(row.category)

    def test_imported_accounting_observation_stays_supporting_and_explicit(self):
        value = {
            "business_date": "2026-08-20",
            "amount": "1250.00",
            "branch": "KVR",
            "category": "bank_charges",
            "role": "finance_cost",
            "classification_confidence": "strong",
            "source_ref": "busy:voucher:ABC",
            "narration": "BANK PAYMENT",
        }
        conn = FakeConn([
            ("obs1", "voucher:ABC", json.dumps(value), "prov", "raw_supporting", "busy", "file")
        ])
        row = imported_accounting_expense_evidence(conn, "ent", start=date(2026, 8, 1), end=date(2026, 8, 31))[0]
        self.assertIn("acceptance_state in ('raw_supporting','reviewed_provisional','accepted_supporting')", conn.sql)
        self.assertEqual(ExpenseRole.FINANCE, row.role)
        self.assertEqual("strong", row.classification_confidence)
        self.assertEqual("bank_charges", row.category)
        self.assertEqual("busy:voucher:ABC", row.source_ref)

    def test_narration_without_explicit_classification_cannot_become_pnl(self):
        value = {
            "business_date": "2026-08-20",
            "amount": "1250.00",
            "branch": "KVR",
            "narration": "PETROL EXPENSE",
        }
        conn = FakeConn([
            ("obs1", "voucher:ABC", json.dumps(value), "prov", "raw_supporting", "busy", "file")
        ])
        row = imported_accounting_expense_evidence(conn, "ent")[0]
        self.assertEqual(ExpenseRole.UNKNOWN, row.role)
        self.assertEqual("unknown", row.classification_confidence)
        self.assertIsNone(row.category)

    def test_diagnostics_keep_unknown_amount_visible(self):
        conn = FakeConn([
            ("e1", date(2026, 8, 21), Decimal("250.00"), "KVR", "courier", "branch_operating_expense", "exact", "receipt:1", "", ""),
            ("e2", date(2026, 8, 21), Decimal("100.00"), "KVR", None, "unknown", "unknown", "", "", ""),
        ])
        diag = expense_evidence_diagnostics(cash_entry_expense_evidence(conn, "ent"))
        self.assertEqual(2, diag["count"])
        self.assertEqual(1, diag["classified_count"])
        self.assertEqual(1, diag["unknown_count"])
        self.assertEqual(Decimal("100.00"), diag["unknown_amount"])
        self.assertEqual(1, diag["confidence_counts"]["exact"])
        self.assertEqual(1, diag["confidence_counts"]["unknown"])

    def test_import_reconciliation_only_admits_supporting_financial_expense_dimension(self):
        text = Path("src/aws_runtime/import_reconciliation.py").read_text(encoding="utf-8")
        self.assertIn('"financial_expense_observation"', text)
        self.assertIn('"financial.expense_evidence"', text)
        self.assertIn("never derives one from narration", text)
        for forbidden in ("insert into sale_headers", "insert into purchase_headers", "insert into cash_closings", "insert into bank_transactions"):
            self.assertNotIn(forbidden, text.lower())


if __name__ == "__main__":
    unittest.main()
