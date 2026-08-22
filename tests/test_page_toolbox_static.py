from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "web" / "toolbox" / "page-builder.html"
JS = ROOT / "web" / "toolbox" / "page-builder.js"


def test_page_toolbox_files_exist():
    assert HTML.exists()
    assert JS.exists()


def test_page_toolbox_has_requested_component_palette():
    text = JS.read_text(encoding="utf-8")
    for component in ("tile", "button", "field", "list", "table", "chart", "link"):
        assert f"{component}:" in text


def test_page_toolbox_actions_are_intent_only_and_no_permission_grants():
    text = JS.read_text(encoding="utf-8")
    assert "ALLOWED_ACTIONS" in text
    assert "request_save" in text
    assert "request_send" in text
    assert "request_export" in text
    assert "forbidden_binding" in text
    assert "capability\\.grant" in text
    assert "role\\.grant" in text


def test_page_toolbox_is_local_draft_not_production_write():
    html = HTML.read_text(encoding="utf-8")
    js = JS.read_text(encoding="utf-8")
    assert "Draft · local only" in html
    assert "localStorage" in js
    assert "fetch(" not in js
    assert "XMLHttpRequest" not in js


def test_page_definition_exposes_validation_contract():
    text = JS.read_text(encoding="utf-8")
    assert "window.EchoPageToolbox" in text
    assert "definition" in text
    assert "validate" in text
    assert "unsupported_action" in text
