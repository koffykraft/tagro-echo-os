from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Iterable, Mapping
from uuid import uuid4


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _d(value: Decimal | int | str) -> Decimal:
    return Decimal(str(value))


class CountStatus(str, Enum):
    OPEN = "open"
    FINALIZED = "finalized"
    ADJUSTMENT_PROPOSED = "adjustment_proposed"
    ADJUSTMENT_ADMITTED = "adjustment_admitted"
    CLOSED_WITHOUT_ADJUSTMENT = "closed_without_adjustment"


@dataclass(frozen=True)
class CountLine:
    item_key: str
    description: str
    counted_quantity: Decimal
    reference_quantity: Decimal | None
    evidence_refs: tuple[str, ...] = ()
    note: str = ""

    @property
    def variance(self) -> Decimal | None:
        if self.reference_quantity is None:
            return None
        return self.counted_quantity - self.reference_quantity

    def validate(self) -> None:
        if not self.item_key.strip():
            raise ValueError("item_key is required")
        if self.counted_quantity < 0:
            raise ValueError("counted_quantity cannot be negative")
        if self.reference_quantity is not None and self.reference_quantity < 0:
            raise ValueError("reference_quantity cannot be negative")


@dataclass(frozen=True)
class StockAdjustmentProposal:
    proposal_id: str
    count_id: str
    proposed_by: str
    proposed_at: datetime
    lines: tuple[CountLine, ...]
    reason: str
    admitted_by_owner: str | None = None
    admitted_at: datetime | None = None
    owner_note: str = ""

    @property
    def admitted(self) -> bool:
        return self.admitted_by_owner is not None


@dataclass(frozen=True)
class CountSession:
    count_id: str
    branch_id: str
    location: str
    created_by: str
    created_at: datetime
    status: CountStatus = CountStatus.OPEN
    lines: tuple[CountLine, ...] = ()
    finalized_by: str | None = None
    finalized_at: datetime | None = None
    proposal: StockAdjustmentProposal | None = None

    @property
    def variances(self) -> tuple[CountLine, ...]:
        return tuple(line for line in self.lines if line.variance not in {None, Decimal("0")})

    @property
    def unknown_reference_lines(self) -> tuple[CountLine, ...]:
        return tuple(line for line in self.lines if line.reference_quantity is None)


class StockCountEngine:
    """Governed physical stock counting.

    Physical count is evidence. Reference stock is comparison data only.
    Finalizing a count never mutates canonical stock. Any adjustment is a
    separate proposal and requires explicit owner admission before a downstream
    stock ledger may act on it.
    """

    def __init__(self) -> None:
        self.counts: dict[str, CountSession] = {}
        self.events: list[dict[str, object]] = []

    def start(self, *, branch_id: str, location: str, actor_id: str) -> CountSession:
        if not branch_id.strip() or not actor_id.strip():
            raise ValueError("branch_id and actor_id are required")
        count = CountSession(
            count_id=_id("count"),
            branch_id=branch_id.strip(),
            location=location.strip(),
            created_by=actor_id.strip(),
            created_at=_now(),
        )
        self.counts[count.count_id] = count
        self._event(count.count_id, "count_started", actor_id)
        return count

    def record_line(
        self,
        count_id: str,
        *,
        item_key: str,
        description: str,
        counted_quantity: Decimal | int | str,
        reference_quantity: Decimal | int | str | None,
        evidence_refs: Iterable[str] = (),
        note: str = "",
    ) -> CountSession:
        count = self._require_open(count_id)
        line = CountLine(
            item_key=item_key.strip(),
            description=description.strip(),
            counted_quantity=_d(counted_quantity),
            reference_quantity=(None if reference_quantity is None else _d(reference_quantity)),
            evidence_refs=tuple(ref for ref in evidence_refs if str(ref).strip()),
            note=note.strip(),
        )
        line.validate()
        rows = tuple(existing for existing in count.lines if existing.item_key != line.item_key) + (line,)
        updated = replace(count, lines=rows)
        self.counts[count_id] = updated
        self._event(
            count_id,
            "count_line_recorded",
            count.created_by,
            item_key=line.item_key,
            counted_quantity=str(line.counted_quantity),
            reference_known=line.reference_quantity is not None,
        )
        return updated

    def finalize(self, count_id: str, *, actor_id: str) -> CountSession:
        count = self._require_open(count_id)
        if not count.lines:
            raise ValueError("cannot finalize an empty count")
        updated = replace(
            count,
            status=CountStatus.FINALIZED,
            finalized_by=actor_id.strip(),
            finalized_at=_now(),
        )
        self.counts[count_id] = updated
        self._event(
            count_id,
            "count_finalized_without_stock_mutation",
            actor_id,
            variance_lines=len(updated.variances),
            unknown_reference_lines=len(updated.unknown_reference_lines),
        )
        return updated

    def propose_adjustment(self, count_id: str, *, actor_id: str, reason: str) -> CountSession:
        count = self.counts[count_id]
        if count.status != CountStatus.FINALIZED:
            raise ValueError("only a finalized count can propose adjustment")
        if not reason.strip():
            raise ValueError("adjustment proposal requires a reason")
        if count.unknown_reference_lines:
            raise ValueError("cannot propose adjustment while reference quantity is unknown")
        variances = count.variances
        if not variances:
            raise ValueError("count has no variance to adjust")
        proposal = StockAdjustmentProposal(
            proposal_id=_id("stock-adjustment"),
            count_id=count_id,
            proposed_by=actor_id.strip(),
            proposed_at=_now(),
            lines=variances,
            reason=reason.strip(),
        )
        updated = replace(count, status=CountStatus.ADJUSTMENT_PROPOSED, proposal=proposal)
        self.counts[count_id] = updated
        self._event(count_id, "stock_adjustment_proposed_not_applied", actor_id, proposal_id=proposal.proposal_id)
        return updated

    def admit_adjustment(
        self,
        count_id: str,
        *,
        owner_actor_id: str,
        owner_note: str,
    ) -> CountSession:
        count = self.counts[count_id]
        if count.status != CountStatus.ADJUSTMENT_PROPOSED or count.proposal is None:
            raise ValueError("there is no adjustment proposal awaiting owner admission")
        if not owner_actor_id.strip():
            raise PermissionError("owner authority is required")
        if not owner_note.strip():
            raise ValueError("owner admission note is required")
        admitted = replace(
            count.proposal,
            admitted_by_owner=owner_actor_id.strip(),
            admitted_at=_now(),
            owner_note=owner_note.strip(),
        )
        updated = replace(count, status=CountStatus.ADJUSTMENT_ADMITTED, proposal=admitted)
        self.counts[count_id] = updated
        self._event(
            count_id,
            "stock_adjustment_admitted_for_downstream_application",
            owner_actor_id,
            proposal_id=admitted.proposal_id,
        )
        return updated

    def close_without_adjustment(self, count_id: str, *, actor_id: str, reason: str) -> CountSession:
        count = self.counts[count_id]
        if count.status not in {CountStatus.FINALIZED, CountStatus.ADJUSTMENT_PROPOSED}:
            raise ValueError("count cannot be closed from current status")
        if not reason.strip():
            raise ValueError("closure reason is required")
        updated = replace(count, status=CountStatus.CLOSED_WITHOUT_ADJUSTMENT, proposal=None)
        self.counts[count_id] = updated
        self._event(count_id, "count_closed_without_stock_adjustment", actor_id, reason=reason.strip())
        return updated

    def admitted_adjustment_payload(self, count_id: str) -> Mapping[str, object]:
        count = self.counts[count_id]
        if count.status != CountStatus.ADJUSTMENT_ADMITTED or not count.proposal or not count.proposal.admitted:
            raise PermissionError("stock adjustment has not been admitted by owner")
        return {
            "proposal_id": count.proposal.proposal_id,
            "count_id": count.count_id,
            "branch_id": count.branch_id,
            "location": count.location,
            "owner_actor_id": count.proposal.admitted_by_owner,
            "owner_note": count.proposal.owner_note,
            "lines": tuple(
                {
                    "item_key": line.item_key,
                    "counted_quantity": line.counted_quantity,
                    "reference_quantity": line.reference_quantity,
                    "variance": line.variance,
                    "evidence_refs": line.evidence_refs,
                }
                for line in count.proposal.lines
            ),
        }

    def _require_open(self, count_id: str) -> CountSession:
        count = self.counts[count_id]
        if count.status != CountStatus.OPEN:
            raise ValueError("count is not open")
        return count

    def _event(self, count_id: str, event_type: str, actor_id: str, **payload: object) -> None:
        self.events.append(
            {
                "event_id": _id("stock-count-event"),
                "count_id": count_id,
                "event_type": event_type,
                "actor_id": actor_id,
                "occurred_at": _now(),
                "payload": payload,
            }
        )
