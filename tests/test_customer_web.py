from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_customer_information_page_uses_real_runtime_and_shared_reference_data():
    html = (WEB / "customers.html").read_text(encoding="utf-8")
    assert 'name="viewport"' in html
    assert "runtime-config.js" in html
    assert "runtime-client.js" in html
    assert "EchoRuntime.reference('customers'" in html
    assert "path:'/customers'" in html
    assert "tagro.echo.customer-created.v1" in html
    assert 'id="name"' in html
    assert 'id="phone"' in html
    assert "Enter customer name and phone" in html
    assert "Customer saved and available to Billing and Service" in html


def test_billing_and_service_can_create_then_select_acknowledged_customer():
    for page in ("billing.html", "service.html"):
        html = (WEB / page).read_text(encoding="utf-8")
        assert "SAVE & SELECT CUSTOMER" in html
        assert "path:'/customers'" in html
        assert "tagro.echo.customer-created.v1" in html
        assert "r.state==='acknowledged'" in html
        assert "r.response?.data?.customer_id" in html
        assert "selectCustomer(x)" in html


def test_customer_page_is_admitted_and_cached():
    manifest = (WEB / "deploy-manifest.txt").read_text(encoding="utf-8")
    sw = (WEB / "sw.js").read_text(encoding="utf-8")
    assert "customers.html" in manifest.splitlines()
    assert "'./customers.html'" in sw
