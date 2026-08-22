from __future__ import annotations

import unittest
from decimal import Decimal

from src.financial.closing_cash_learning import (
    ClosingCashEvidenceRow,
    ClosingCashKind,
    LearningRule,
    build_review_queue,
    consolidate,
    evidence_key,
    suggest,
)


class ClosingCashLearningTests(unittest.TestCase):
    def row(self, **kw):
        base = dict(
            branch="KVR",
            business_date="2026-04-10",
            kind=ClosingCashKind.EXPENSE,
            amount=Decimal("100"),
            particulars="Tea expense",
            source_ref="cc:kvr:2026-04-10",
            source_row=12,
        )
        base.update(kw)
        return ClosingCashEvidenceRow(**base)

    def test_accountfetcher_style_key_is_stable(self):
        row = self.row(kind=ClosingCashKind.SALES, particulars="44", amount=Decimal("1000"))
        self.assertEqual(evidence_key(row), "KVR|2026-04-10|S|1000|44")

    def test_consolidation_only_collapses_full_evidence_key_duplicates(self):
        a = self.row()
        duplicate = self.row(source_row=13)
        distinct = self.row(amount=Decimal("101"), source_row=14)
        result = consolidate((a, duplicate, distinct))
        self.assertEqual(len(result), 2)

    def test_learned_owner_rule_precedes_generic_keyword(self):
        row = self.row(particulars="special staff tea")
        rule = LearningRule(
            fragment="special staff tea",
            semantic_class="STAFF_WELFARE",
            confidence=0.98,
            source_ref="owner-rule:17",
            branch="KVR",
            kind=ClosingCashKind.EXPENSE,
        )
        result = suggest(row, (rule,))
        self.assertEqual(result.semantic_class, "STAFF_WELFARE")
        self.assertEqual(result.rule_source, "owner-rule:17")
        self.assertFalse(result.requires_review)

    def test_historical_branch_rule_is_suggestion_not_financial_truth(self):
        row = self.row(branch="PKM", particulars="KU Cash")
        result = suggest(row)
        self.assertEqual(result.semantic_class, "CASH_BOX_MOVEMENT")
        self.assertGreaterEqual(result.confidence, 0.90)

    def test_low_confidence_rows_enter_review_queue(self):
        row = self.row(particulars="misc thing")
        queue = build_review_queue((row,))
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0][1].semantic_class, "UNCLASSIFIED_EXPENSE")

    def test_sales_default_needs_review(self):
        row = self.row(kind=ClosingCashKind.SALES, particulars="123")
        result = suggest(row)
        self.assertEqual(result.semantic_class, "DIRECT_SALES")
        self.assertTrue(result.requires_review)


if __name__ == "__main__":
    unittest.main()
