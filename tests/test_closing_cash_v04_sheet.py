from pathlib import Path


def test_v04_uses_excel_sheet_on_desktop_and_mobile():
    text = Path('web/closing-cash-v04-live.html').read_text(encoding='utf-8')
    assert 'width=1180' in text
    assert '.desktop{display:block!important' in text
    assert '.mobile{display:none!important' in text
    assert 'min-width:1080px!important' in text
    assert 'closing-cash-v03-navfix.js' in text
    assert "grid-template-columns:minmax(560px,1fr) 365px" in text
    assert '.entry-table col.part{width:280px!important}' in text
    assert '.entry-table th,.entry-table td{height:25px!important}' in text
    assert "path:'/cash-days/save'" in text
