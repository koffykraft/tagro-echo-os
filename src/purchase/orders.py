from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Iterable, Mapping
from uuid import uuid4

MONEY = Decimal("0.01")


def _money(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


class PurchaseOrderStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    ORDERED = "ordered"
    PART_RECEIVED = "part_received"
    RECEIVED = "received"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class PurchaseOrderLine:
    line_id: str
    item_key: str
    description: str
    quantity: Decimal
    expected_unit_cost: Decimal | None = None
    source_ref: str | None = None

    def validate(self) -> None:
        if not self.item_key.strip():
            raise ValueError("item_key is required")
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        if self.expected_unit_cost is not None and self.expected_unit_cost < 0:
            raise ValueError("expected_unit_cost cannot be negative")


@dataclass(frozen=True)
class InterBranchStockEvidence:
    item_key: str
    branch_id: str
    available_quantity: Decimal
    observed_at: datetime
    source_ref: str
    freshness_seconds: int | None = None

    def validate(self) -> None:
        if not self.item_key.strip() or not self.branch_id.strip():
            raise ValueError("item_key and branch_id are required")
        if self.available_quantity < 0:
            raise ValueError("available_quantity cannot be negative")
        if not self.source_ref.strip():
            raise ValueError("source_ref is required")


@dataclass(frozen=True)
class ApprovalDecision:
    decision_id: str
    order_id: str
    approved: bool
    actor_id: str
    decided_at: datetime
    note: str = ""


@dataclass(frozen=True)
class PurchaseOrder:
    order_id: str
    branch_id: str
    supplier_id: str | None
    requested_by: str
    created_at: datetime
    status: PurchaseOrderStatus = PurchaseOrderStatus.DRAFT
    lines: tuple[PurchaseOrderLine, ...] = ()
    owner_approval_required: bool = True
    approval: ApprovalDecision | None = None
    interbranch_evidence: tuple[InterBranchStockEvidence, ...] = ()
    ordered_ref: str | None = None
    received_quantities: Mapping[str, Decimal] = field(default_factory=dict)

    @property
    def expected_total(self) -> Decimal | None:
        if not self.lines or any(line.expected_unit_cost is None for line in self.lines):
            return None
        return _money(sum((line.quantity * line.expected_unit_cost for line in self.lines), Decimal("0")))

    @property
    def unresolved_interbranch_opportunity(self) -> tuple[InterBranchStockEvidence, ...]:
        requested = {line.item_key: line.quantity for line in self.lines}
        return tuple(
            evidence
            for evidence in self.interbranch_evidence
            if evidence.available_quantity > 0 and evidence.item_key in requested
        )


class PurchaseOrderStore:
    """In-memory governed purchase-order lifecycle.

    The store deliberately separates stock evidence, owner approval and ordering.
    Inter-branch availability is advisory evidence only: it never silently changes
    a supplier order. Approval must be explicit when owner authority is required.
    """

    def __init__(self) -> None:
        self.orders: dict[str, PurchaseOrder] = {}
        self.events: list[dict[str, object]] = []

    def create(
        self,
        *,
        branch_id: str,
        requested_by: str,
        supplier_id: str | None = None,
        owner_approval_required: bool = True,
    ) -> PurchaseOrder:
        if not branch_id.strip() or not requested_by.strip():
            raise ValueError("branch_id and requested_by are required")
        order = PurchaseOrder(
            order_id=_id("po"),
            branch_id=branch_id,
            supplier_id=supplier_id,
            requested_by=requested_by,
            created_at=datetime.now(timezone.utc),
            owner_approval_required=owner_approval_required,
        )
        self.orders[order.order_id] = order
        self._event(order.order_id, "created", requested_by)
        return order

    def add_line(
        self,
        order_id: str,
        *,
        item_key: str,
        description: str,
        quantity: Decimal,
        expected_unit_cost: Decimal | None = None,
        source_ref: str | None = None,
    ) -> PurchaseOrder:
        order = self._editable(order_id)
        line = PurchaseOrderLine(
            line_id=_id("pol"),
            item_key=item_key,
            description=description.strip(),
            quantity=Decimal(quantity),
            expected_unit_cost=(None if expected_unit_cost is None else _money(expected_unit_cost)),
            source_ref=source_ref,
        )
        line.validate()
        updated = replace(order, lines=order.lines + (line,))
        self.orders[order_id] = updated
        self._event(order_id, "line_added", order.requested_by, item_key=item_key, quantity=str(quantity))
        return updated

    def attach_interbranch_evidence(
        self,
        order_id: str,
        evidence: Iterable[InterBranchStockEvidence],
        *,
        actor_id: str,
    ) -> PurchaseOrder:
        order = self._editable(order_id, allow_submitted=True)
        rows = tuple(evidence)
        for row in rows:
            row.validate()
        requested_items = {line.item_key for line in order.lines}
        relevant = tuple(row for row in rows if row.item_key in requested_items and row.branch_id != order.branch_id)
        updated = replace(order, interbranch_evidence=relevant)
        self.orders[order_id] = updated
        self._event(order_id, "interbranch_evidence_attached", actor_id, count=len(relevant))
        return updated

    def submit(self, order_id: str, *, actor_id: str) -> PurchaseOrder:
        order = self._editable(order_id)
        if not order.lines:
            raise ValueError("purchase order requires at least one line")
        updated = replace(order, status=PurchaseOrderStatus.SUBMITTED)
        self.orders[order_id] = updated
        self._event(order_id, "submitted", actor_id)
        return updated

    def decide(self, order_id: str, *, approved: bool, owner_actor_id: str, note: str = "") -> PurchaseOrder:
        order = self.orders[order_id]
        if order.status != PurchaseOrderStatus.SUBMITTED:
            raise ValueError("only submitted purchase orders can be decided")
        if not owner_actor_id.strip():
            raise ValueError("owner_actor_id is required")
        decision = ApprovalDecision(
            decision_id=_id("poa"),
            order_id=order_id,
            approved=approved,
            actor_id=owner_actor_id,
            decided_at=datetime.now(timezone.utc),
            note=note.strip(),
        )
        updated = replace(
            order,
            status=(PurchaseOrderStatus.APPROVED if approved else PurchaseOrderStatus.REJECTED),
            approval=decision,
        )
        self.orders[order_id] = updated
        self._event(order_id, "approved" if approved else "rejected", owner_actor_id, note=note.strip())
        return updated

    def mark_ordered(self, order_id: str, *, actor_id: str, ordered_ref: str) -> PurchaseOrder:
        order = self.orders[order_id]
        if order.owner_approval_required and order.status != PurchaseOrderStatus.APPROVED:
            raise PermissionError("owner approval is required before ordering")
        if not order.owner_approval_required and order.status not in {
            PurchaseOrderStatus.SUBMITTED,
            PurchaseOrderStatus.APPROVED,
        }:
            raise ValueError("purchase order must be submitted before ordering")
        if not ordered_ref.strip():
            raise ValueError("ordered_ref is required")
        updated = replace(order, status=PurchaseOrderStatus.ORDERED, ordered_ref=ordered_ref.strip())
        self.orders[order_id] = updated
        self._event(order_id, "ordered", actor_id, ordered_ref=ordered_ref.strip())
        return updated

    def receive(
        self,
        order_id: str,
        *,
        actor_id: str,
        quantities_by_line: Mapping[str, Decimal],
    ) -> PurchaseOrder:
        order = self.orders[order_id]
        if order.status not in {PurchaseOrderStatus.ORDERED, PurchaseOrderStatus.PART_RECEIVED}:
            raise ValueError("only ordered purchase orders can receive stock")
        known_lines = {line.line_id: line for line in order.lines}
        received = dict(order.received_quantities)
        for line_id, quantity in quantities_by_line.items():
            if line_id not in known_lines:
                raise ValueError(f"unknown line_id: {line_id}")
            qty = Decimal(quantity)
            if qty < 0:
                raise ValueError("received quantity cannot be negative")
            next_qty = Decimal(received.get(line_id, Decimal("0"))) + qty
            if next_qty > known_lines[line_id].quantity:
                raise ValueError("received quantity exceeds ordered quantity")
            received[line_id] = next_qty
        complete = all(Decimal(received.get(line.line_id, 0)) == line.quantity for line in order.lines)
        updated = replace(
            order,
            status=(PurchaseOrderStatus.RECEIVED if complete else PurchaseOrderStatus.PART_RECEIVED),
            received_quantities=received,
        )
        self.orders[order_id] = updated
        self._event(order_id, "received" if complete else "part_received", actor_id)
        return updated

    def cancel(self, order_id: str, *, actor_id: str, reason: str) -> PurchaseOrder:
        order = self.orders[order_id]
        if order.status in {PurchaseOrderStatus.RECEIVED, PurchaseOrderStatus.CANCELLED}:
            raise ValueError("purchase order cannot be cancelled from current status")
        if not reason.strip():
            raise ValueError("cancellation reason is required")
        updated = replace(order, status=PurchaseOrderStatus.CANCELLED)
        self.orders[order_id] = updated
        self._event(order_id, "cancelled", actor_id, reason=reason.strip())
        return updated

    def _editable(self, order_id: str, allow_submitted: bool = False) -> PurchaseOrder:
        order = self.orders[order_id]
        allowed = {PurchaseOrderStatus.DRAFT}
        if allow_submitted:
            allowed.add(PurchaseOrderStatus.SUBMITTED)
        if order.status not in allowed:
            raise ValueError("purchase order is no longer editable")
        return order

    def _event(self, order_id: str, event_type: str, actor_id: str, **payload: object) -> None:
        self.events.append(
            {
                "event_id": _id("poe"),
                "order_id": order_id,
                "event_type": event_type,
                "actor_id": actor_id,
                "occurred_at": datetime.now(timezone.utc),
                "payload": payload,
            }
        )
