from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Mapping

from .health import ExpenseEvidence, ExpenseRole


_ALLOWED_CONFIDENCE = {"exact", "strong", "weak", "unknown"}


@dataclass(frozen=True)
class AccountingExpenseObservation:
    """Read-only accounting-side expense observation.

    This is evidence, not canonical truth. A debit/voucher/narration does not by
    itself prove a P&L consequence. Callers may supply only explicit, governed
    classification fields already present in the source/reconciliation layer.
    """

    observation_id: str
    business_date: date
    amount: Decimal
    branch: str | None = None
    category: str | None = None
    role: str | None = None
    classification_confidence: str = "unknown"
    source_ref: str | None = None
    evidence_state: str = "supporting"


_ROLE_MAP = {role.value: role for role in ExpenseRole}


def accounting_expense_evidence(
    observation: AccountingExpenseObservation,
    explicit_overrides: Mapping[str, tuple[str, ExpenseRole, str]] | None = None,
) -> ExpenseEvidence | None:
    """Convert accounting observation to governed expense evidence.

    Rules:
    - non-positive values are not expense evidence;
    - explicit override is keyed by exact observation ID only;
    - otherwise category/role/confidence must all be supplied by the observation;
    - weak/unknown evidence remains visible but is not upgraded here;
    - malformed/partial classification is deliberately downgraded to unknown.
    """

    amount = Decimal(observation.amount)
    if amount <= 0:
        return None

    override = (explicit_overrides or {}).get(observation.observation_id)
    if override:
        category, role, confidence = override
        confidence = str(confidence or "unknown").lower()
        if confidence not in _ALLOWED_CONFIDENCE:
            confidence = "unknown"
        if confidence == "unknown" or not str(category or "").strip() or role == ExpenseRole.UNKNOWN:
            category = None
            role = ExpenseRole.UNKNOWN
            confidence = "unknown"
        return ExpenseEvidence(
            expense_id=f"accounting:{observation.observation_id}",
            expense_date=observation.business_date,
            amount=amount,
            branch=observation.branch,
            category=category,
            source_ref=observation.source_ref or f"accounting:{observation.observation_id}",
            classification_confidence=confidence,
            role=role,
        )

    confidence = str(observation.classification_confidence or "unknown").lower()
    role = _ROLE_MAP.get(str(observation.role or "").lower(), ExpenseRole.UNKNOWN)
    category = str(observation.category or "").strip() or None
    complete = category is not None and role != ExpenseRole.UNKNOWN and confidence in _ALLOWED_CONFIDENCE and confidence != "unknown"
    if not complete:
        category = None
        role = ExpenseRole.UNKNOWN
        confidence = "unknown"

    return ExpenseEvidence(
        expense_id=f"accounting:{observation.observation_id}",
        expense_date=observation.business_date,
        amount=amount,
        branch=observation.branch,
        category=category,
        source_ref=observation.source_ref or f"accounting:{observation.observation_id}",
        classification_confidence=confidence,
        role=role,
    )


def collect_accounting_expense_evidence(
    observations: tuple[AccountingExpenseObservation, ...],
    explicit_overrides: Mapping[str, tuple[str, ExpenseRole, str]] | None = None,
) -> tuple[ExpenseEvidence, ...]:
    rows: list[ExpenseEvidence] = []
    for observation in observations:
        row = accounting_expense_evidence(observation, explicit_overrides)
        if row is not None:
            rows.append(row)
    return tuple(rows)
