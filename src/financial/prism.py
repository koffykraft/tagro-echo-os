from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum, IntEnum
from typing import Iterable


class PrismDepth(IntEnum):
    OBSERVATION = 0
    MOVEMENT = 1
    RELATIONSHIP = 2
    EVENT_FAMILY = 3
    BUSINESS_MEANING = 4
    FINANCIAL_CONSEQUENCE = 5
    OPERATIONAL_ALLOCATION = 6


class PrismBand(str, Enum):
    VALUE = "value"
    IDENTITY = "identity"
    BUSINESS = "business_meaning"
    LOCATION = "location"
    YIELD = "financial_consequence"
    ORIGIN = "origin_evidence"
    RELIABILITY = "reliability_relationship"


@dataclass(frozen=True)
class PrismCandidate:
    meaning: str
    confidence: float
    depth: PrismDepth
    reason: str
    source_ref: str | None = None

    def validate(self) -> None:
        if not self.meaning.strip():
            raise ValueError("meaning is required")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")


@dataclass(frozen=True)
class PrismObservation:
    observation_id: str
    source_kind: str
    source_ref: str
    amount: Decimal
    direction: str
    branch: str | None = None
    account: str | None = None
    counterparty: str | None = None
    narration: str = ""
    business_date: str | None = None

    def validate(self) -> None:
        if not self.observation_id.strip():
            raise ValueError("observation_id is required")
        if not self.source_ref.strip():
            raise ValueError("source_ref is required")
        if Decimal(self.amount) < 0:
            raise ValueError("amount cannot be negative")
        if self.direction not in {"in", "out", "debit", "credit", "neutral"}:
            raise ValueError("unsupported direction")


@dataclass(frozen=True)
class PrismRay:
    band: PrismBand
    value: str
    confidence: float
    depth: PrismDepth
    reason: str
    source_refs: tuple[str, ...]


@dataclass(frozen=True)
class PrismResult:
    observation_id: str
    resolved_depth: PrismDepth
    rays: tuple[PrismRay, ...]
    candidates: tuple[PrismCandidate, ...]
    tight_split: bool
    requires_more_evidence: bool
    stop_reason: str

    @property
    def top_candidate(self) -> PrismCandidate | None:
        return self.candidates[0] if self.candidates else None


class AdaptivePrism:
    """Read-only adaptive evidence splitter.

    The prism does not force an observation into the most specific available
    category. It walks from broad to precise interpretation and stops at the
    deepest level justified by evidence. If the best candidates are too close,
    it steps back to the last safe depth and preserves the competing meanings.

    This layer produces suggestions/projections only. It does not establish
    canonical business or financial truth.
    """

    def __init__(
        self,
        descend_threshold: float = 0.80,
        tight_margin: float = 0.12,
        auto_consequence_threshold: float = 0.92,
    ) -> None:
        if not 0 <= descend_threshold <= 1:
            raise ValueError("descend_threshold must be between 0 and 1")
        if not 0 <= tight_margin <= 1:
            raise ValueError("tight_margin must be between 0 and 1")
        if not 0 <= auto_consequence_threshold <= 1:
            raise ValueError("auto_consequence_threshold must be between 0 and 1")
        self.descend_threshold = descend_threshold
        self.tight_margin = tight_margin
        self.auto_consequence_threshold = auto_consequence_threshold

    @staticmethod
    def _sort(candidates: Iterable[PrismCandidate]) -> tuple[PrismCandidate, ...]:
        result = tuple(sorted(candidates, key=lambda c: (-c.confidence, c.meaning, int(c.depth))))
        for candidate in result:
            candidate.validate()
        return result

    def resolve(
        self,
        observation: PrismObservation,
        candidates: Iterable[PrismCandidate],
    ) -> PrismResult:
        observation.validate()
        ordered = self._sort(candidates)

        base_rays = [
            PrismRay(
                PrismBand.VALUE,
                f"{observation.direction}:{Decimal(observation.amount)}",
                1.0,
                PrismDepth.MOVEMENT,
                "literal observed movement",
                (observation.source_ref,),
            ),
            PrismRay(
                PrismBand.ORIGIN,
                observation.source_kind,
                1.0,
                PrismDepth.OBSERVATION,
                "preserved source identity",
                (observation.source_ref,),
            ),
        ]
        if observation.branch:
            base_rays.append(
                PrismRay(
                    PrismBand.LOCATION,
                    observation.branch,
                    1.0,
                    PrismDepth.OPERATIONAL_ALLOCATION,
                    "explicit source branch",
                    (observation.source_ref,),
                )
            )
        if observation.counterparty:
            base_rays.append(
                PrismRay(
                    PrismBand.IDENTITY,
                    observation.counterparty,
                    1.0,
                    PrismDepth.RELATIONSHIP,
                    "explicit counterparty identity",
                    (observation.source_ref,),
                )
            )

        if not ordered:
            return PrismResult(
                observation.observation_id,
                PrismDepth.MOVEMENT,
                tuple(base_rays),
                (),
                False,
                True,
                "no semantic evidence beyond literal movement",
            )

        top = ordered[0]
        second = ordered[1] if len(ordered) > 1 else None
        tight = bool(second and abs(top.confidence - second.confidence) < self.tight_margin)

        # A tight spectrum means the prism cannot justify the narrower split.
        # Step back one level from the shallower competing candidate rather than
        # selecting whichever happens to score slightly higher.
        if tight:
            safe_depth = PrismDepth(max(PrismDepth.MOVEMENT, min(top.depth, second.depth) - 1))
            stop_reason = "competing meanings are too close; stepped back to broader interpretation"
            requires_more = True
        elif top.confidence < self.descend_threshold:
            safe_depth = PrismDepth(max(PrismDepth.MOVEMENT, top.depth - 1))
            stop_reason = "evidence below descent threshold; retained broader interpretation"
            requires_more = True
        elif top.depth >= PrismDepth.FINANCIAL_CONSEQUENCE and top.confidence < self.auto_consequence_threshold:
            safe_depth = PrismDepth.BUSINESS_MEANING
            stop_reason = "financial consequence requires stronger evidence"
            requires_more = True
        else:
            safe_depth = top.depth
            stop_reason = "evidence supports current resolution depth"
            requires_more = False

        rays = list(base_rays)
        for candidate in ordered:
            if candidate.depth > safe_depth:
                continue
            band = self._band_for_depth(candidate.depth)
            refs = tuple(x for x in (observation.source_ref, candidate.source_ref) if x)
            rays.append(
                PrismRay(
                    band,
                    candidate.meaning,
                    candidate.confidence,
                    candidate.depth,
                    candidate.reason,
                    refs,
                )
            )

        rays.append(
            PrismRay(
                PrismBand.RELIABILITY,
                "needs-more-evidence" if requires_more else "resolved-at-supported-depth",
                top.confidence,
                safe_depth,
                stop_reason,
                (observation.source_ref,),
            )
        )

        return PrismResult(
            observation.observation_id,
            safe_depth,
            tuple(rays),
            ordered,
            tight,
            requires_more,
            stop_reason,
        )

    @staticmethod
    def _band_for_depth(depth: PrismDepth) -> PrismBand:
        if depth == PrismDepth.MOVEMENT:
            return PrismBand.VALUE
        if depth == PrismDepth.RELATIONSHIP:
            return PrismBand.IDENTITY
        if depth in {PrismDepth.EVENT_FAMILY, PrismDepth.BUSINESS_MEANING}:
            return PrismBand.BUSINESS
        if depth == PrismDepth.FINANCIAL_CONSEQUENCE:
            return PrismBand.YIELD
        if depth == PrismDepth.OPERATIONAL_ALLOCATION:
            return PrismBand.LOCATION
        return PrismBand.ORIGIN


def chord_pair(
    left: PrismObservation,
    right: PrismObservation,
    *,
    amount_tolerance: Decimal = Decimal("0.00"),
) -> PrismCandidate | None:
    """Return a transfer candidate when two observations can form a chord.

    Same amount plus opposing direction is useful evidence, not proof. The
    confidence is intentionally below the financial-consequence threshold unless
    account/reference evidence is supplied by a higher-level reconciler.
    """
    left.validate()
    right.validate()
    amount_gap = abs(Decimal(left.amount) - Decimal(right.amount))
    opposite = {left.direction, right.direction} in ({"out", "in"}, {"debit", "credit"}, {"out", "credit"}, {"debit", "in"})
    if amount_gap > amount_tolerance or not opposite:
        return None
    return PrismCandidate(
        "INTERNAL_TRANSFER_CANDIDATE",
        0.76,
        PrismDepth.EVENT_FAMILY,
        "opposing equal-value observations form a possible transfer chord",
        source_ref=f"{left.source_ref}|{right.source_ref}",
    )
