from __future__ import annotations

import json
import unittest
from datetime import date, datetime, timezone
from decimal import Decimal

from src.financial.health import CostConfidence, CostEstimate, SaleProfitProjection
from src.financial.presentation import OWNER_ON_CALL_SCHEMA, owner_on_call_payload


class FinancialPresentationTests(unittest.TestCase):
    def test_payload_is_json_safe_and_preserves_decimal_precision(self):
        projection = SaleProfitProjection(
            sale_id="S1",
            branch="KVR",
            sale_date=date(2026, 8, 21),
            item_key="ITEM1",
            quantity=Decimal("2"),
            sales_before_tax=Decimal("1234.50"),
            estimated_cogs=Decimal("900.25"),
            estimated_gross_profit=Decimal("334.25"),
            gross_margin_pct=Decimal("27.08"),
            cost=CostEstimate(
                unit_cost=Decimal("450.125"),
                confidence=CostConfidence.STRONG,
                reference_count=4,
                reference_dates=(date(2026, 8, 20),),
                source_refs=("P1",),
                policy="test",
            ),
        )
        payload = owner_on_call_payload({
            "sales_before_tax": Decimal("1234.50"),
            "evidence_as_of": datetime(2026, 8, 21, 5, 0, tzinfo=timezone.utc),
            "drilldown": {"sale_projections": (projection,)},
        })
        self.assertEqual(payload["schema"], OWNER_ON_CALL_SCHEMA)
        self.assertEqual(payload["projection_status"], "not_accounting_final")
        self.assertEqual(payload["data"]["sales_before_tax"], "1234.50")
        self.assertEqual(payload["data"]["drilldown"]["sale_projections"][0]["cost"]["confidence"], "strong")
        json.dumps(payload)


if __name__ == "__main__":
    unittest.main()
