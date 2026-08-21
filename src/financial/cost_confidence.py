from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

from .health import CostConfidence, SaleProfitProjection


PCT = Decimal("0.01")
MONEY = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def _pct(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == 0:
        return Decimal("0.00")
    return (numerator / denominator * Decimal("100")).quantize(PCT, rounding=ROUND_HALF_UP)


def confidence_breakdown(projections: Iterable[SaleProfitProjection]) -> dict[str, object]:
    """Summarize how much revenue is supported by each cost-confidence tier.

    This is deliberately evidence-only. It does not upgrade weak/unknown cost
    evidence, fill missing costs, or classify business meaning. The purpose is
    to stop line-count coverage from overstating financial certainty when a few
    high-value sales have weak or missing purchase-price support.
    """

    rows = tuple(projections)
    total_revenue = _money(sum((p.sales_before_tax for p in rows), Decimal("0")))

    buckets: dict[CostConfidence, dict[str, object]] = {
        confidence: {
            "line_count": 0,
            "sales_before_tax": Decimal("0"),
            "estimated_cogs": Decimal("0"),
            "estimated_gross_profit": Decimal("0"),
            "source_refs": set(),
        }
        for confidence in CostConfidence
    }

    for projection in rows:
        bucket = buckets[projection.cost.confidence]
        bucket["line_count"] += 1
        bucket["sales_before_tax"] += projection.sales_before_tax
        if projection.estimated_cogs is not None:
            bucket["estimated_cogs"] += projection.estimated_cogs
        if projection.estimated_gross_profit is not None:
            bucket["estimated_gross_profit"] += projection.estimated_gross_profit
        bucket["source_refs"].update(projection.cost.source_refs)

    result: dict[str, object] = {}
    for confidence, bucket in buckets.items():
        sales = _money(bucket["sales_before_tax"])
        result[confidence.value] = {
            "line_count": bucket["line_count"],
            "sales_before_tax": sales,
            "sales_share_pct": _pct(sales, total_revenue),
            "estimated_cogs": _money(bucket["estimated_cogs"]),
            "estimated_gross_profit": _money(bucket["estimated_gross_profit"]),
            "source_refs": tuple(sorted(bucket["source_refs"])),
        }

    exact_or_strong_revenue = _money(
        result[CostConfidence.EXACT.value]["sales_before_tax"]
        + result[CostConfidence.STRONG.value]["sales_before_tax"]
    )
    weak_or_unknown_revenue = _money(total_revenue - exact_or_strong_revenue)

    return {
        "sales_before_tax": total_revenue,
        "exact_or_strong_sales_before_tax": exact_or_strong_revenue,
        "weak_or_unknown_sales_before_tax": weak_or_unknown_revenue,
        "exact_or_strong_revenue_coverage_pct": _pct(exact_or_strong_revenue, total_revenue),
        "weak_or_unknown_revenue_exposure_pct": _pct(weak_or_unknown_revenue, total_revenue),
        "by_confidence": result,
    }
