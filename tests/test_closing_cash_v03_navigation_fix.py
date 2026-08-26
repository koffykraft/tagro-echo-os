from pathlib import Path


def test_closing_cash_denomination_navigation_fix_contract():
    js = Path('web/closing-cash-v03-navfix.js').read_text(encoding='utf-8')
    wrapper = Path('web/closing-cash-v03-live-navfix.html').read_text(encoding='utf-8')
    assert "e.key==='Enter'" in js
    assert "preventDefault" in js
    assert "preventScroll:true" in js
    assert ".select()" in js
    assert "renderDenoms=function" in js
    assert "calcRender()" in js
    assert "markDirty()" in js
    assert "closing-cash-v03-live.html" in wrapper
    assert "closing-cash-v03-navfix.js" in js or "closing-cash-v03-navfix.js" in wrapper
