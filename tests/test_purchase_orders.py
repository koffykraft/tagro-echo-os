from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.purchase import InterBranchStockEvidence, PurchaseOrderStatus, PurchaseOrderStore


def test_owner_approval_required_before_ordering():
    store = PurchaseOrderStore()
    order = store.create(branch_id="KVR", requested_by="staff-1", supplier_id="vendor-1")
    order = store.add_line(
        order.order_id,
        item_key="MS382",
        description="Chainsaw",
        quantity=Decimal("2"),
        expected_unit_cost=Decimal("45000"),
    )
    order = store.submit(order.order_id, actor_id="staff-1")
    assert order.status == PurchaseOrderStatus.SUBMITTED
    with pytest.raises(PermissionError):
        store.mark_ordered(order.order_id, actor_id="staff-1", ordered_ref="SUP-001")
    approved = store.decide(order.order_id, approved=True, owner_actor_id="owner-1", note="Approved")
    assert approved.status == PurchaseOrderStatus.APPROVED
    ordered = store.mark_ordered(order.order_id, actor_id="staff-1", ordered_ref="SUP-001")
    assert ordered.status == PurchaseOrderStatus.ORDERED
    assert ordered.approval.actor_id == "owner-1"


def test_interbranch_stock_is_advisory_and_does_not_change_lines():
    store = PurchaseOrderStore()
    order = store.create(branch_id="KVR", requested_by="staff-1")
    order = store.add_line(order.order_id, item_key="CHAIN-20", description="20 inch chain", quantity=Decimal("10"))
    original_qty = order.lines[0].quantity
    evidence = InterBranchStockEvidence(
        item_key="CHAIN-20",
        branch_id="PKM",
        available_quantity=Decimal("4"),
        observed_at=datetime.now(timezone.utc),
        source_ref="stock-snapshot:PKM:2026-08-22",
    )
    order = store.attach_interbranch_evidence(order.order_id, [evidence], actor_id="staff-1")
    assert order.lines[0].quantity == original_qty
    assert order.unresolved_interbranch_opportunity == (evidence,)


def test_partial_and_full_receipt_preserve_ordered_ceiling():
    store = PurchaseOrderStore()
    order = store.create(branch_id="KVR", requested_by="staff-1", owner_approval_required=False)
    order = store.add_line(order.order_id, item_key="OIL-1L", description="Oil", quantity=Decimal("5"))
    line_id = order.lines[0].line_id
    store.submit(order.order_id, actor_id="staff-1")
    store.mark_ordered(order.order_id, actor_id="staff-1", ordered_ref="V-100")
    partial = store.receive(order.order_id, actor_id="staff-2", quantities_by_line={line_id: Decimal("2")})
    assert partial.status == PurchaseOrderStatus.PART_RECEIVED
    complete = store.receive(order.order_id, actor_id="staff-2", quantities_by_line={line_id: Decimal("3")})
    assert complete.status == PurchaseOrderStatus.RECEIVED
    with pytest.raises(ValueError):
        store.receive(order.order_id, actor_id="staff-2", quantities_by_line={line_id: Decimal("1")})


def test_expected_total_unknown_if_any_cost_missing():
    store = PurchaseOrderStore()
    order = store.create(branch_id="KVR", requested_by="staff-1")
    order = store.add_line(order.order_id, item_key="A", description="A", quantity=Decimal("2"), expected_unit_cost=Decimal("10"))
    assert order.expected_total == Decimal("20.00")
    order = store.add_line(order.order_id, item_key="B", description="B", quantity=Decimal("1"))
    assert order.expected_total is None
