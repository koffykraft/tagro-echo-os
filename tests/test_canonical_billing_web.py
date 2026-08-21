from pathlib import Path


def test_canonical_billing_preserves_runtime_authority_and_busy_separation():
    html = Path("web/forms/billing.html").read_text(encoding="utf-8")
    assert "Issue through ECHO" in html
    assert "/billing/issue" in html
    assert "tagro.echo.billing-request.v1" in html
    assert "tagro.echo.bill-issued.v1" in html
    assert "BUSY series: not assigned until confirmed runtime handoff" in html
    assert "no invoice or BUSY booking has been claimed" in html
    assert "payment_evidence_state" in html


def test_canonical_billing_is_phone_first_and_does_not_claim_unknown_stock():
    html = Path("web/forms/billing.html").read_text(encoding="utf-8")
    css = Path("web/forms/echo-forms.css").read_text(encoding="utf-8")
    assert "@media(max-width:760px)" in html
    assert "font-size:16px" in html
    assert "Unknown stock is never silently treated as available" in html
    assert "active enterprise product IDs" in html
    assert "owner_stock_override" not in html
    assert ".billing-shell .bill-table{display:block!important" in css
    assert "min-width:0!important" in css
    assert ".billing-shell .bill-table tr{display:grid!important" in css
    assert "content:'Item'" in css
    assert "content:'Amount'" in css


def test_canonical_billing_keeps_local_draft_and_idempotency_boundary():
    html = Path("web/forms/billing.html").read_text(encoding="utf-8")
    assert "billing-draft-canonical" in html
    assert "idempotency_key" in html
    assert "enqueueAndFlush" in html
    assert "LOCAL DRAFT" in html
