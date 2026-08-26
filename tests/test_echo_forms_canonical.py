from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_canonical_form_family_exists():
    js = (ROOT / "web/forms/echo-forms.js").read_text(encoding="utf-8")
    for key in ("closing", "invoice", "estimate", "quotation", "service", "purchase", "stock", "receipt", "payment"):
        assert f"{key}:{{" in js
    assert "documentHTML" in js
    assert "Review" in js
    assert "Confirm Save" in js
    assert "localStorage" in js


def test_forms_launcher_routes_immediate_work_to_purpose_specific_surfaces():
    html = (ROOT / "web/forms/index.html").read_text(encoding="utf-8")
    assert 'href="closing-cash.html"' in html
    assert 'href="billing.html"' in html
    assert 'href="../service.html"' in html
    assert 'href="../po.html"' in html
    assert 'href="../stock-count.html"' in html
    assert 'href="../reports.html"' in html
    for key in ("estimate", "quotation", "receipt", "payment"):
        assert f"type={key}" in html
    assert "BUSY remains a distinct proving/reconciliation series" in html
    assert "Physical count evidence kept separate" in html


def test_mobile_and_a4_are_distinct_render_planes():
    css = (ROOT / "web/forms/echo-forms.css").read_text(encoding="utf-8")
    assert "@media(max-width:900px)" in css
    assert "@media print" in css
    assert "size:A4" in css
    assert ".rail.open" in css
    assert ".document" in css


def test_closing_cash_keeps_expected_semantics():
    js = (ROOT / "web/forms/echo-forms.js").read_text(encoding="utf-8")
    assert "Yesterday Closing" in js
    assert "Today sale" in js
    assert "Balance Due" in js
    assert "CASH in hand" in js
    assert "Difference" in js
    assert "Expenses / cash movements" in js


def test_stock_count_keeps_physical_count_separate_from_expected():
    js = (ROOT / "web/forms/echo-forms.js").read_text(encoding="utf-8")
    assert "Expected" in js
    assert "Counted" in js
    assert "physical count remains separate until admitted" in js
