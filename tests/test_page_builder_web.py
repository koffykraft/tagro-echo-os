from pathlib import Path


def test_page_toolbox_files_and_governance_contract():
    root = Path(__file__).resolve().parents[1]
    html = (root / "web/page-builder/index.html").read_text(encoding="utf-8")
    js = (root / "web/page-builder/page-builder.js").read_text(encoding="utf-8")
    css = (root / "web/page-builder/page-builder.css").read_text(encoding="utf-8")

    assert "Page Toolbox" in html
    assert "Save definition" in html
    assert "Data binding" in html
    assert "No production deployment" in html
    assert "financial classification" in html

    for component in ("tile", "button", "field", "list", "table", "chart", "link", "text"):
        assert component in js
    assert "localStorage" in js
    assert "binding" in js
    assert "action" in js
    assert "exportPage" in js
    assert "fetch(" not in js
    assert "XMLHttpRequest" not in js

    assert ".stage.mobile" in css
    assert ".stage.desktop" in css
    assert "@media(max-width:860px)" in css
