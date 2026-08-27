from __future__ import annotations

import unittest

from src.aws_runtime.purchase_entry_runtime import (
    PurchaseEntryRuntimeError,
    _branch_allowed,
    _tax_mode,
)


class PurchaseEntryRuntimeTests(unittest.TestCase):
    def test_intra_state_purchase_uses_supplier_and_branch_state(self) -> None:
        self.assertEqual(_tax_mode("32ABCDE1234F1Z5", "32"), "intra")

    def test_inter_state_purchase_uses_supplier_and_branch_state(self) -> None:
        self.assertEqual(_tax_mode("33ABCDE1234F1Z5", "32"), "inter")

    def test_tax_mode_rejects_missing_or_invalid_evidence(self) -> None:
        with self.assertRaises(PurchaseEntryRuntimeError):
            _tax_mode("", "32")
        with self.assertRaises(PurchaseEntryRuntimeError):
            _tax_mode("33ABCDE1234F1Z5", "")

    def test_branch_access_is_least_privilege(self) -> None:
        self.assertTrue(_branch_allowed("owner", None, "branch-b"))
        self.assertTrue(_branch_allowed("branch_manager", "branch-a", "branch-a"))
        self.assertFalse(_branch_allowed("branch_manager", "branch-a", "branch-b"))
        self.assertFalse(_branch_allowed("branch_staff", None, "branch-a"))


if __name__ == "__main__":
    unittest.main()
