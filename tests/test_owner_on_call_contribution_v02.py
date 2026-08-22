from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal

from src.financial.health import ExpenseEvidence, ExpenseRole, SaleLineEvidence
from src.financial.on_call import OwnerOnCall


class OwnerOnCallContributionV02Tests(unittest.TestCase):
    def test_branch_snapshot_exposes_contribution_layers(self):
        sale = SaleLineEvidence(
            "S1", date(2026, 8, 20), "KVR", "ITEM", Decimal("1"), Decimal("500"),
            explicit_cost_before_tax=Decimal("300"),
        )
        expenses = (
            ExpenseEvidence("D", date(2026, 8, 20), Decimal("20"), "KVR", "delivery", "D", "exact", ExpenseRole.DIRECT),
            ExpenseEvidence("B", date(2026, 8, 20), Decimal("30"), "KVR", "rent", "B", "exact", ExpenseRole.BRANCH),
            ExpenseEvidence("CAP", date(2026, 8, 20), Decimal("1000"), "KVR", "asset", "CAP", "exact", ExpenseRole.CAPITAL),
        )
        snapshot = OwnerOnCall().snapshot((sale,), (), expenses, branch="KVR")
        self.assertEqual(snapshot["estimated_contribution_known"], Decimal("180.00"))
        self.assertEqual(snapshot["estimated_branch_contribution_known"], Decimal("150.00"))
        branch = snapshot["branches"]["KVR"]
        self.assertEqual(branch["classified_direct_selling_costs"], Decimal("20"))
        self.assertEqual(branch["classified_branch_operating_expenses"], Decimal("30"))
        self.assertEqual(branch["classified_pnl_expenses"], Decimal("50"))
        self.assertEqual(branch["estimated_contribution_known"], Decimal("180.00"))
        self.assertEqual(branch["estimated_branch_contribution_known"], Decimal("150.00"))
        self.assertNotEqual(branch["classified_pnl_expenses"], Decimal("1050"))


if __name__ == "__main__":
    unittest.main()
