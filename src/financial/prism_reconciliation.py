from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

from .prism import PrismCandidate, PrismDepth, PrismObservation


@dataclass(frozen=True)
class ChordEvidence:
    """Evidence that two observations may describe one underlying movement.

    A chord is a relationship candidate, not duplicate truth.  Stronger
    corroborators must be supplied explicitly by the reconciliation caller;
    narration similarity alone is never enough to establish a P&L consequence.
    """

    left_id: str
    right_id: str
    amount_equal: bool
    direction_opposed: bool
    date_delta_days: int | None
    same_reference: bool = False
    account_identified: bool = False
    owner_confirmed: bool = False
    source_refs: tuple[str, ...] = ()

    @property
    def within_date_tolerance(self) -> bool:
        return self.date_delta_days is not None and self.date_delta_days <= 3


@dataclass(frozen=True)
class ReconciliationResult:
    chord: ChordEvidence
    candidates: tuple[PrismCandidate, ...]
    deterministic_identity: bool
    requires_review: bool
    reason: str


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _cash_bank_opposed(left: PrismObservation, right: PrismObservation) -> bool:
    pair = {left.direction.lower(), right.direction.lower()}
    # Closing Cash out + bank credit/in is the common cash-deposit pair.
    # Closing Cash in + bank debit/out is the reverse/withdrawal pair.
    return pair in ({"out", "credit"}, {"out", "in"}, {"in", "debit"})


def reconcile_pair(
    left: PrismObservation,
    right: PrismObservation,
    *,
    same_reference: bool = False,
    account_identified: bool = False,
    owner_confirmed: bool = False,
) -> ReconciliationResult:
    """Reconcile two source observations conservatively.

    Exact amount + opposing direction + close date creates only an event-family
    transfer candidate.  A no-P&L consequence is emitted only when the movement
    identity is independently corroborated by reference/account evidence or an
    owner confirmation.  This prevents every similar cash/bank movement from
    being silently netted out of expenses.
    """

    amount_equal = Decimal(left.amount) == Decimal(right.amount)
    direction_opposed = _cash_bank_opposed(left, right)
    ld, rd = _parse_date(left.business_date), _parse_date(right.business_date)
    date_delta = abs((ld - rd).days) if ld and rd else None
    chord = ChordEvidence(
        left_id=left.observation_id,
        right_id=right.observation_id,
        amount_equal=amount_equal,
        direction_opposed=direction_opposed,
        date_delta_days=date_delta,
        same_reference=same_reference,
        account_identified=account_identified,
        owner_confirmed=owner_confirmed,
        source_refs=tuple(x for x in (left.source_ref, right.source_ref) if x),
    )

    if not (amount_equal and direction_opposed and chord.within_date_tolerance):
        return ReconciliationResult(
            chord=chord,
            candidates=(),
            deterministic_identity=False,
            requires_review=True,
            reason="pair lacks exact amount/opposed direction/close-date evidence",
        )

    candidates: list[PrismCandidate] = [
        PrismCandidate(
            "INTERNAL_TRANSFER_CANDIDATE",
            0.76,
            PrismDepth.EVENT_FAMILY,
            "exact amount, opposing movement and date proximity across two sources",
            " | ".join(chord.source_refs),
        )
    ]

    # Consequential identity must have an independent corroborator.  A shared
    # reference is strongest.  Account identity is acceptable only in addition
    # to the exact movement triple above.  Owner confirmation is authoritative
    # evidence but remains traceable as such.
    deterministic = same_reference or account_identified or owner_confirmed
    if deterministic:
        confidence = 0.99 if owner_confirmed else 0.97 if same_reference else 0.94
        reason_bits = ["exact movement triple"]
        if same_reference:
            reason_bits.append("shared reference")
        if account_identified:
            reason_bits.append("destination/source account identified")
        if owner_confirmed:
            reason_bits.append("owner confirmed")
        candidates.append(
            PrismCandidate(
                "NO_PNL_INTERNAL_TRANSFER",
                confidence,
                PrismDepth.FINANCIAL_CONSEQUENCE,
                "; ".join(reason_bits),
                " | ".join(chord.source_refs),
            )
        )

    return ReconciliationResult(
        chord=chord,
        candidates=tuple(candidates),
        deterministic_identity=deterministic,
        requires_review=not deterministic,
        reason=(
            "cross-source movement identity corroborated"
            if deterministic
            else "probable transfer; independent identity evidence still required"
        ),
    )


def candidate_pairs(
    closing_cash: Iterable[PrismObservation],
    bank: Iterable[PrismObservation],
) -> tuple[tuple[PrismObservation, PrismObservation], ...]:
    """Return conservative candidate pairs without declaring a chord.

    This is deliberately a small search primitive: exact amount, opposed
    direction and +/- 3 day window.  Ambiguous one-to-many matches remain
    visible to a higher reconciliation layer and are never auto-selected here.
    """

    result: list[tuple[PrismObservation, PrismObservation]] = []
    for cash in closing_cash:
        for bank_row in bank:
            if Decimal(cash.amount) != Decimal(bank_row.amount):
                continue
            if not _cash_bank_opposed(cash, bank_row):
                continue
            cd, bd = _parse_date(cash.business_date), _parse_date(bank_row.business_date)
            if cd is None or bd is None or abs((cd - bd).days) > 3:
                continue
            result.append((cash, bank_row))
    return tuple(result)
