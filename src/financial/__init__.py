"""Governed financial-health calculations for ECHO.

This package is intentionally projection-only: it derives owner-facing financial
status from supplied evidence and never mutates canonical business truth.
"""

from .health import (
    CostConfidence,
    ExpenseEvidence,
    PurchasePriceEvidence,
    SaleLineEvidence,
    FinancialHealthEngine,
)

__all__ = [
    "CostConfidence",
    "ExpenseEvidence",
    "PurchasePriceEvidence",
    "SaleLineEvidence",
    "FinancialHealthEngine",
]
