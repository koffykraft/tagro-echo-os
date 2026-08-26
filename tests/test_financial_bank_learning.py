from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal

from src.bank.normalization import BankTransaction
from src.financial.bank_learning import BankNarrationRule, learned_bank_candidates, match_bank_rule, narration_signature
from src.financial.prism import PrismDepth


class BankLearningTests(unittest.TestCase):
    def tx(self, **kw):
        base = dict(
            transaction_id="tx-1",
            statement_id="stmt-1",
            source_file="sbi.xlsx",
            source_row=12,
            account_id="SBI-KVR",
            transaction_date=date(2026, 8, 20),
            value_date=None,
            direction="debit",
            amount=Decimal("15000"),
            narration="NEFT ABCSUPPLIER 123456789012",
            reference="",
            balance=None,
        )
        base.update(kw)
        return BankTransaction(**base)

    def rule(self, **kw):
        base = dict(
            narration_signature=narration_signature("NEFT ABCSUPPLIER 998877665544"),
            direction="D",
            meaning="SUPPLIER PAYMENT",
            confidence=0.97,
            examples=12,
            safe_action="auto-fill",
            source_ref="bank-rule:42",
            depth=PrismDepth.BUSINESS_MEANING,
            years_seen=("2023-24", "2024-25", "2025-26"),
        )
        base.update(kw)
        return BankNarrationRule(**base)

    def test_historical_signature_masks_changing_reference_numbers(self):
        self.assertEqual(
            narration_signature("NEFT ABCSUPPLIER 123456789012"),
            narration_signature("NEFT ABCSUPPLIER 998877665544"),
        )

    def test_safe_rule_can_teach_business_meaning(self):
        match = match_bank_rule(self.tx(), (self.rule(),))
        self.assertFalse(match.review_required)
        self.assertEqual(match.candidate.meaning, "SUPPLIER PAYMENT")
        self.assertEqual(match.candidate.depth, PrismDepth.BUSINESS_MEANING)

    def test_suggestion_rule_is_forced_below_auto_descent_threshold(self):
        candidates = learned_bank_candidates(
            self.tx(),
            (self.rule(confidence=0.94, safe_action="suggest for review"),),
        )
        self.assertEqual(len(candidates), 1)
        self.assertLess(candidates[0].confidence, 0.80)

    def test_direction_must_match(self):
        match = match_bank_rule(self.tx(direction="credit"), (self.rule(),))
        self.assertIsNone(match.candidate)
        self.assertTrue(match.review_required)

    def test_narration_rule_cannot_be_financial_consequence(self):
        with self.assertRaises(ValueError):
            self.rule(depth=PrismDepth.FINANCIAL_CONSEQUENCE).validate()


if __name__ == "__main__":
    unittest.main()
