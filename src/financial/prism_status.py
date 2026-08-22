from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from .prism import PrismBand, PrismDepth, PrismObservation, PrismResult


@dataclass(frozen=True)
class PrismStatusRow:
    observation: PrismObservation
    result: PrismResult



def _has_financial_consequence(result: PrismResult) -> bool:
    return any(
        ray.band == PrismBand.YIELD and ray.depth == PrismDepth.FINANCIAL_CONSEQUENCE
        for ray in result.rays
    )


def build_prism_status(rows: Iterable[PrismStatusRow]) -> dict[str, object]:
    """Summarize evidence-resolution health without converting uncertainty to zero."""
    items = tuple(rows)
    total_amount = Decimal("0")
    resolved_consequence_amount = Decimal("0")
    unresolved_amount = Decimal("0")
    tight_amount = Decimal("0")
    resolved_count = unresolved_count = tight_count = 0
    review: list[dict[str, object]] = []

    for row in items:
        amount = abs(Decimal(row.observation.amount))
        total_amount += amount
        consequence = _has_financial_consequence(row.result)
        if consequence:
            resolved_count += 1
            resolved_consequence_amount += amount
        if row.result.requires_more_evidence:
            unresolved_count += 1
            unresolved_amount += amount
        if row.result.tight_split:
            tight_count += 1
            tight_amount += amount
        if row.result.requires_more_evidence or row.result.tight_split:
            review.append(
                {
                    "observation_id": row.observation.observation_id,
                    "source_kind": row.observation.source_kind,
                    "source_ref": row.observation.source_ref,
                    "amount": amount,
                    "direction": row.observation.direction,
                    "branch": row.observation.branch,
                    "resolved_depth": row.result.resolved_depth.name.lower(),
                    "tight_split": row.result.tight_split,
                    "reason": row.result.stop_reason,
                    "candidates": tuple(
                        {
                            "meaning": c.meaning,
                            "confidence": c.confidence,
                            "depth": c.depth.name.lower(),
                            "source_ref": c.source_ref,
                        }
                        for c in row.result.candidates[:4]
                    ),
                }
            )

    coverage_pct = (
        Decimal("0.00")
        if total_amount == 0
        else (resolved_consequence_amount / total_amount * Decimal("100")).quantize(Decimal("0.01"))
    )
    return {
        "observation_count": len(items),
        "movement_amount_observed": total_amount,
        "financial_consequence_resolved_count": resolved_count,
        "financial_consequence_resolved_amount": resolved_consequence_amount,
        "financial_consequence_amount_coverage_pct": coverage_pct,
        "unresolved_count": unresolved_count,
        "unresolved_amount": unresolved_amount,
        "tight_split_count": tight_count,
        "tight_split_amount": tight_amount,
        "review_queue": tuple(review),
        "status": "evidence_resolution_projection",
    }
