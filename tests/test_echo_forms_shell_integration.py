from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_root_shell_exposes_canonical_forms_without_replacing_existing_routes():
    html = (ROOT / "web/index.html").read_text(encoding="utf-8")
    assert 'href="forms/index.html"' in html
    # Existing immediate-work routes remain available while the canonical lane proves itself.
    for route in ("on-call.html", "billing.html", "service.html", "po.html", "stock-count.html", "reports.html"):
        assert f'href="{route}"' in html


def test_canonical_forms_static_lane_is_available_offline_without_caching_runtime_data():
    sw = (ROOT / "web/sw.js").read_text(encoding="utf-8")
    assert "tagro-echo-os-v8" in sw
    for asset in (
        "./forms/index.html",
        "./forms/form.html",
        "./forms/closing-cash.html",
        "./forms/billing.html",
        "./forms/echo-forms.css",
        "./forms/echo-forms.js",
    ):
        assert asset in sw
    assert "API/auth/financial/reference responses are never cached" in sw
    assert "if(url.origin!==self.location.origin)return;" in sw
    assert "fetch(request,{cache:'no-store'})" in sw
