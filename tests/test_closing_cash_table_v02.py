from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_closing_cash_v02_mobile_navigation_contract():
    text = (ROOT / "web" / "closing-cash-table-v02.html").read_text(encoding="utf-8")
    assert "Closing Cash · Ver02" in text
    assert "contenteditable" not in text
    assert "enterkeyhint=\"next\"" in text
    assert "inputmode=\"decimal\"" in text
    assert "function nextByJob" in text
    assert "function makeRow" in text
    assert "e.key==='Enter'" in text
    assert "data-job=\"sale\"" in text
    assert "data-job=\"expense\"" in text
    assert "data-job=\"part\"" in text
    assert "Undo row" in text
    assert "Ver02 navigation prototype" in text
