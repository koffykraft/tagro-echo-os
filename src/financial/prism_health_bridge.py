from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Mapping

from .health import ExpenseEvidence, ExpenseRole
from .prism import PrismBand, PrismDepth, PrismResult


@dataclass(frozen=True)
class ConsequencePolicy:
    role: ExpenseRole
    category: str | None = None
    minimum_confidence: float = 0.92


DEFAULT_CONSEQUENCE_POLICIES: Mapping[str, ConsequencePolicy] = {
    "DIRECT_SELLING_COST": ConsequencePolicy(ExpenseRole.DIRECT),
    "BRANCH_OPERATING_EXPENSE": ConsequencePolicy(ExpenseRole.BRANCH),
    "CENTRAL_OVERHEAD": ConsequencePolicy(ExpenseRole.CENTRAL),
    "FINANCE_COST": ConsequencePolicy(ExpenseRole.FINANCE),
    "NON_OPERATING": ConsequencePolicy(ExpenseRole.NON_OPERATING),
    "CAPITAL_MOVEMENT": ConsequencePolicy(ExpenseRole.CAPITAL),
    "NO_PNL_INTERNAL_TRANSFER": ConsequencePolicy(ExpenseRole.INTERNAL_TRANSFER),
}


def supported_consequence(result: PrismResult):
    """Return the strongest consequence ray only when the prism reached that depth."""
    if result.resolved_depth < PrismDepth.FINANCIAL_CONSEQUENCE:
        return None
    rays = [ray for ray in result.rays if ray.band == PrismBand.YIELD and ray.depth == PrismDepth.FINANCIAL_CONSEQUENCE]
    if not rays:
        return None
    return sorted(rays, key=lambda r: (-r.confidence, r.value))[0]


def prism_expense_evidence(
    *,
    result: PrismResult,
    expense_id: str,
    expense_date: date,
    amount: Decimal,
    branch: str | None,
    source_ref: str,
    policies: Mapping[str, ConsequencePolicy] = DEFAULT_CONSEQUENCE_POLICIES,
) -> ExpenseEvidence | None:
    """Bridge a supported Prism consequence into Financial Health.

    Semantic/event-family rays are intentionally insufficient. A consequence
    must survive the Prism's adaptive resolution and also meet the governed
    consequence policy threshold. Internal transfers/capital movements may be
    represented for audit but remain excluded from operating P&L by their role.
    """
    ray = supported_consequence(result)
    if ray is None:
        return None
    policy = policies.get(ray.value)
    if policy is None or ray.confidence < policy.minimum_confidence:
        return None
    return ExpenseEvidence(
        expense_id=expense_id,
        expense_date=expense_date,
        amount=Decimal(amount),
        branch=branch,
        category=policy.category or ray.value,
        source_ref=source_ref,
        classification_confidence=f"prism:{ray.confidence:.2f}",
        role=policy.role,
    )
