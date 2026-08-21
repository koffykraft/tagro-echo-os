from __future__ import annotations

import unittest
from decimal import Decimal

from src.financial.prism import PrismDepth, PrismObservation
from src.financial.prism_reconciliation import candidate_pairs, reconcile_pair


class PrismReconciliationTests(unittest.TestCase):
    def obs(self, **kw):
        base = dict(
            observation_id="cash-1",
            source_kind="closing_cash",
            source_ref="cc:kvr:1",
            amount=Decimal("25000"),
            direction="out",
            branch="KVR",
            account=None,
            narration="SBI deposit",
            business_date="2026-08-20",
        )
        base.update(kw)
        return PrismObservation(**base)

    def bank(self, **kw):
        base = dict(
            observation_id="bank-1",
            source_kind="bank_statement",
            source_ref="bank:sbi:1",
            amount=Decimal("25000"),
            direction="credit",
            branch=None,
            account="SBI-KVR",
            narration="cash deposit",
            business_date="2026-08-20",
        )
        base.update(kw)
        return PrismObservation(**base)

    def test_exact_pair_without_identity_remains_candidate(self):
        result = reconcile_pair(self.obs(), self.bank())
        self.assertFalse(result.deterministic_identity)
        self.assertTrue(result.requires_review)
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(result.candidates[0].depth, PrismDepth.EVENT_FAMILY)

    def test_shared_reference_can_establish_no_pnl_consequence(self):
        result = reconcile_pair(self.obs(), self.bank(), same_reference=True)
        self.assertTrue(result.deterministic_identity)
        consequence = [c for c in result.candidates if c.depth == PrismDepth.FINANCIAL_CONSEQUENCE]
        self.assertEqual(len(consequence), 1)
        self.assertEqual(consequence[0].meaning, "NO_PNL_INTERNAL_TRANSFER")
        self.assertGreaterEqual(consequence[0].confidence, 0.92)

    def test_account_identity_can_corroborate_exact_movement_triple(self):
        result = reconcile_pair(self.obs(), self.bank(), account_identified=True)
        self.assertTrue(result.deterministic_identity)
        self.assertFalse(result.requires_review)

    def test_amount_mismatch_never_forms_candidate(self):
        result = reconcile_pair(self.obs(), self.bank(amount=Decimal("24999")), same_reference=True)
        self.assertFalse(result.deterministic_identity)
        self.assertEqual(result.candidates, ())

    def test_date_outside_window_never_forms_candidate(self):
        result = reconcile_pair(self.obs(), self.bank(business_date="2026-08-25"), same_reference=True)
        self.assertEqual(result.candidates, ())

    def test_candidate_search_preserves_one_to_many_ambiguity(self):
        cash = (self.obs(),)
        banks = (
            self.bank(observation_id="bank-1"),
            self.bank(observation_id="bank-2", source_ref="bank:sbi:2", business_date="2026-08-21"),
        )
        matches = candidate_pairs(cash, banks)
        self.assertEqual(len(matches), 2)
        self.assertEqual({b.observation_id for _, b in matches}, {"bank-1", "bank-2"})


if __name__ == "__main__":
    unittest.main()
