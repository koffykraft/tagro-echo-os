from pathlib import Path


def test_owner_on_call_shows_revenue_weighted_cost_confidence():
    html = Path("web/on-call.html").read_text(encoding="utf-8")

    assert 'id="confidenceCoverage"' in html
    assert 'id="confidenceExposure"' in html
    assert "exact_or_strong_revenue_coverage_pct" in html
    assert "weak_or_unknown_sales_before_tax" in html
    assert "weak_or_unknown_revenue_exposure_pct" in html
    assert "Known-cost revenue coverage" in html
    assert "Exact + strong revenue coverage" in html
    assert "Weak + unknown revenue exposure" in html
