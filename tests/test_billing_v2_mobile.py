from pathlib import Path


def test_phone_first_billing_v2_preserves_runtime_and_proving_boundaries():
    text = Path("web/billing-v2.html").read_text(encoding="utf-8")
    assert "tagro.echo.billing-request.v1" in text
    assert "path:'/billing/issue'" in text
    assert "tagro.echo.bill-issued.v1" in text
    assert "BUSY proving series" in text
    assert "No BUSY voucher is claimed here" in text
    assert "no bill or BUSY booking" in text.lower()


def test_phone_first_billing_v2_avoids_horizontal_line_grid_on_mobile():
    text = Path("web/billing-v2.html").read_text(encoding="utf-8")
    assert ".line-card" in text
    assert "@media(max-width:720px)" in text
    assert ".layout{display:block}" in text
    assert "font-size:16px" in text
    assert "inputmode=\"decimal\"" in text
    assert "Review bill" in text


def test_phone_first_billing_v2_keeps_authoritative_checks_server_side():
    text = Path("web/billing-v2.html").read_text(encoding="utf-8")
    assert "Product identity and GST must resolve to governed enterprise product data before issue" in text
    assert "Product/GST/stock/authority checks remain server-side" in text
    assert "owner_stock_override" not in text
