from __future__ import annotations

import unittest
from decimal import Decimal

from src.financial.prism import (
    AdaptivePrism,
    PrismBand,
    PrismCandidate,
    PrismDepth,
    PrismObservation,
    chord_pair,
)


class AdaptivePrismTests(unittest.TestCase):
    def observation(self, **kw):
        base = dict(
            observation_id="obs-1",
            source_kind="closing_cash",
            source_ref="cc:KVR:2026-08-21:12",
            amount=Decimal("25000"),
            direction="out",
            branch="KVR",
            narration="SBI deposit",
        )
        base.update(kw)
        return PrismObservation(**base)

    def test_no_semantic_evidence_stops_at_literal_movement(self):
        result = AdaptivePrism().resolve(self.observation(), ())
        self.assertEqual(result.resolved_depth, PrismDepth.MOVEMENT)
        self.assertTrue(result.requires_more_evidence)
        self.assertTrue(any(ray.band == PrismBand.VALUE for ray in result.rays))

    def test_clear_business_meaning_can_descend(self):
        candidates = (
            PrismCandidate("BUSINESS_PAYMENT", 0.95, PrismDepth.EVENT_FAMILY, "governed identity evidence"),
            PrismCandidate("SALARY", 0.94, PrismDepth.BUSINESS_MEANING, "owner-approved recurring rule"),
        )
        result = AdaptivePrism().resolve(self.observation(narration="Salary Anoop"), candidates)
        self.assertEqual(result.resolved_depth, PrismDepth.EVENT_FAMILY)
        # Scores are close: preserve both and step back rather than pretending
        # that the narrower salary split is certain.
        self.assertTrue(result.tight_split)
        self.assertTrue(result.requires_more_evidence)

    def test_clear_single_salary_rule_reaches_business_meaning(self):
        result = AdaptivePrism().resolve(
            self.observation(narration="Salary Anoop"),
            (PrismCandidate("SALARY", 0.96, PrismDepth.BUSINESS_MEANING, "owner-approved recurring rule"),),
        )
        self.assertEqual(result.resolved_depth, PrismDepth.BUSINESS_MEANING)
        self.assertFalse(result.requires_more_evidence)

    def test_financial_consequence_has_higher_threshold(self):
        result = AdaptivePrism().resolve(
            self.observation(),
            (PrismCandidate("OPERATING_EXPENSE", 0.88, PrismDepth.FINANCIAL_CONSEQUENCE, "semantic rule only"),),
        )
        self.assertEqual(result.resolved_depth, PrismDepth.BUSINESS_MEANING)
        self.assertTrue(result.requires_more_evidence)

    def test_strong_financial_consequence_can_resolve(self):
        result = AdaptivePrism().resolve(
            self.observation(),
            (PrismCandidate("NO_PNL_INTERNAL_TRANSFER", 0.97, PrismDepth.FINANCIAL_CONSEQUENCE, "paired account reference confirmed"),),
        )
        self.assertEqual(result.resolved_depth, PrismDepth.FINANCIAL_CONSEQUENCE)
        self.assertFalse(result.requires_more_evidence)
        self.assertTrue(any(ray.band == PrismBand.YIELD for ray in result.rays))

    def test_tight_split_steps_back_and_keeps_competing_candidates(self):
        candidates = (
            PrismCandidate("SUPPLIER_PAYMENT", 0.54, PrismDepth.BUSINESS_MEANING, "counterparty pattern"),
            PrismCandidate("INTERNAL_TRANSFER", 0.49, PrismDepth.BUSINESS_MEANING, "account movement pattern"),
        )
        result = AdaptivePrism(descend_threshold=0.50, tight_margin=0.12).resolve(self.observation(), candidates)
        self.assertTrue(result.tight_split)
        self.assertEqual(result.resolved_depth, PrismDepth.EVENT_FAMILY)
        self.assertEqual(len(result.candidates), 2)
        self.assertTrue(result.requires_more_evidence)

    def test_equal_opposing_movements_make_candidate_not_truth(self):
        left = self.observation(source_ref="cc:1", direction="out")
        right = self.observation(
            observation_id="obs-2",
            source_kind="bank",
            source_ref="bank:1",
            direction="credit",
            branch=None,
            account="SBI",
        )
        candidate = chord_pair(left, right)
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.meaning, "INTERNAL_TRANSFER_CANDIDATE")
        self.assertLess(candidate.confidence, 0.80)

    def test_amount_mismatch_does_not_form_transfer_chord(self):
        left = self.observation(direction="out")
        right = self.observation(observation_id="obs-2", source_ref="bank:2", source_kind="bank", direction="credit", amount=Decimal("24999"))
        self.assertIsNone(chord_pair(left, right))


if __name__ == "__main__":
    unittest.main()
