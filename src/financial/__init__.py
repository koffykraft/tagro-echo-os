"""Governed financial-health calculations for ECHO.

This package is intentionally projection-only: it derives owner-facing financial
status from supplied evidence and never mutates canonical business truth.
"""

from .cost_confidence import confidence_breakdown
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
    "confidence_breakdown",
]
