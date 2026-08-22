from pathlib import Path


def test_owner_on_call_exposes_sale_cost_and_unknown_expense_drilldown():
    text = Path("web/on-call.html").read_text(encoding="utf-8")

    assert "Evidence drill-down" in text
    assert 'id="saleEvidence"' in text
    assert 'id="expenseEvidence"' in text
    assert "renderSaleEvidence" in text
    assert "renderExpenseEvidence" in text
    assert "drill.sale_projections" in text
    assert "drill.unknown_expense_evidence" in text


def test_owner_on_call_drilldown_preserves_cost_confidence_and_provenance():
    text = Path("web/on-call.html").read_text(encoding="utf-8")

    for token in (
        "c.confidence",
        "c.policy",
        "c.confidence_reason",
        "c.reference_scope",
        "c.reference_count",
        "c.reference_dates",
        "c.source_refs",
        "c.latest_reference_age_days",
        "c.recent_dispersion_pct",
    ):
        assert token in text

    assert "This row remains outside classified P&amp;L" in text
    assert "never upgrades it for presentation" in text


def test_owner_on_call_evidence_cards_remain_phone_first():
    text = Path("web/on-call.html").read_text(encoding="utf-8")

    assert ".drill-list{display:grid" in text
    assert ".drill-numbers{display:grid" in text
    assert "@media(max-width:640px)" in text
    assert ".drill-numbers{grid-template-columns:1fr 1fr}" in text
    assert "<table" not in text.split("Evidence drill-down", 1)[1]
