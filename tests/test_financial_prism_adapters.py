from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal

from src.bank.normalization import BankTransaction
from src.financial.closing_cash_learning import ClosingCashEvidenceRow, ClosingCashKind
from src.financial.prism import PrismDepth
from src.financial.prism_adapters import (
    bank_candidates,
    closing_cash_candidates,
    consequence_candidate,
    disperse_bank,
    disperse_closing_cash,
)


class PrismAdapterTests(unittest.TestCase):
    def closing_row(self, **kw):
        base = dict(
            branch="KVR",
            business_date="2026-08-21",
            kind=ClosingCashKind.EXPENSE,
            amount=Decimal("25000"),
            particulars="SBI deposit",
            source_ref="cc:kvr:2026-08-21",
            source_row=12,
        )
        base.update(kw)
        return ClosingCashEvidenceRow(**base)

    def bank_tx(self, **kw):
        base = dict(
            transaction_id="tx-1",
            statement_id="stmt-1",
            source_file="sbi.xlsx",
            source_row=10,
            account_id="sbi-kvr",
            transaction_date=date(2026, 8, 21),
            value_date=None,
            direction="debit",
            amount=Decimal("25000"),
            narration="TRANSFER",
        )
        base.update(kw)
        return BankTransaction(**base)

    def test_closing_cash_deposit_is_not_forced_into_expense_consequence(self):
        row = self.closing_row()
        candidates = closing_cash_candidates(row)
        self.assertTrue(all(c.depth <= PrismDepth.EVENT_FAMILY for c in candidates))
        result = disperse_closing_cash(row)
        self.assertLessEqual(result.resolved_depth, PrismDepth.EVENT_FAMILY)

    def test_salary_wording_is_business_meaning_not_automatic_pnl_truth(self):
        row = self.closing_row(particulars="Salary", amount=Decimal("18000"))
        candidates = closing_cash_candidates(row)
        self.assertEqual(candidates[0].meaning, "SALARY")
        self.assertEqual(candidates[0].depth, PrismDepth.BUSINESS_MEANING)
        result = disperse_closing_cash(row)
        self.assertEqual(result.resolved_depth, PrismDepth.BUSINESS_MEANING)

    def test_unruled_bank_debit_remains_literal_outflow(self):
        tx = self.bank_tx()
        candidates = bank_candidates(tx)
        self.assertEqual(candidates[0].meaning, "BANK_OUTFLOW")
        self.assertEqual(candidates[0].depth, PrismDepth.MOVEMENT)
        result = disperse_bank(tx, branch="KVR")
        self.assertEqual(result.resolved_depth, PrismDepth.MOVEMENT)

    def test_governed_bank_rule_can_supply_business_meaning(self):
        tx = self.bank_tx(narration="RENT")
        rules = {
            "tx-1": ("RENT", 0.97, PrismDepth.BUSINESS_MEANING, "owner-approved narration rule")
        }
        result = disperse_bank(tx, branch="KVR", governed_meanings=rules)
        self.assertEqual(result.resolved_depth, PrismDepth.BUSINESS_MEANING)
        self.assertFalse(result.requires_more_evidence)

    def test_consequence_bridge_still_requires_prism_high_confidence(self):
        candidate = consequence_candidate(
            "OPERATING_EXPENSE",
            0.88,
            "single-source semantic rule",
            "rule:1",
        )
        self.assertEqual(candidate.depth, PrismDepth.FINANCIAL_CONSEQUENCE)
        self.assertEqual(candidate.confidence, 0.88)


if __name__ == "__main__":
    unittest.main()
