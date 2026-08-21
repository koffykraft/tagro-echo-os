from datetime import date
from decimal import Decimal

from src.financial.health import PurchasePriceEvidence, SaleLineEvidence
from src.financial.on_call import OwnerOnCall


def test_owner_on_call_reports_revenue_weighted_cost_confidence_without_upgrading_evidence():
    sales = (
        SaleLineEvidence(
            sale_id="S-EXACT",
            sale_date=date(2026, 8, 20),
            branch="KVR",
            item_key="P1",
            quantity=Decimal("1"),
            sale_before_tax=Decimal("1000"),
            explicit_cost_before_tax=Decimal("600"),
            source_ref="sale:S-EXACT",
        ),
        SaleLineEvidence(
            sale_id="S-WEAK",
            sale_date=date(2026, 8, 20),
            branch="KVR",
            item_key="P2",
            quantity=Decimal("1"),
            sale_before_tax=Decimal("500"),
            source_ref="sale:S-WEAK",
        ),
        SaleLineEvidence(
            sale_id="S-UNKNOWN",
            sale_date=date(2026, 8, 20),
            branch="KVR",
            item_key="P3",
            quantity=Decimal("1"),
            sale_before_tax=Decimal("500"),
            source_ref="sale:S-UNKNOWN",
        ),
    )
    purchases = (
        PurchasePriceEvidence(
            item_key="P2",
            purchase_date=date(2026, 8, 1),
            cost_before_tax=Decimal("300"),
            branch="KVR",
            source_ref="purchase:P2:1",
        ),
    )

    snapshot = OwnerOnCall().snapshot(sales, purchases)
    confidence = snapshot["cost_confidence"]

    assert confidence["sales_before_tax"] == Decimal("2000.00")
    assert confidence["exact_or_strong_sales_before_tax"] == Decimal("1000.00")
    assert confidence["weak_or_unknown_sales_before_tax"] == Decimal("1000.00")
    assert confidence["exact_or_strong_revenue_coverage_pct"] == Decimal("50.00")
    assert confidence["weak_or_unknown_revenue_exposure_pct"] == Decimal("50.00")
    assert confidence["by_confidence"]["exact"]["sales_before_tax"] == Decimal("1000.00")
    assert confidence["by_confidence"]["weak"]["sales_before_tax"] == Decimal("500.00")
    assert confidence["by_confidence"]["unknown"]["sales_before_tax"] == Decimal("500.00")
    assert snapshot["projection_complete"] is False
