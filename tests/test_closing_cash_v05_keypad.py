from pathlib import Path


def test_v05_uses_custom_echo_numeric_keypad():
    text = Path('web/closing-cash-v05-mobile-grid.html').read_text(encoding='utf-8')
    assert 'aria-label="ECHO numeric keypad"' in text
    assert 'data-k="enter"' in text
    assert 'ENTER<br>Next' in text
    assert 'data-k="prev"' in text
    assert 'inputmode="none" readonly' in text
    assert 'function keypadInput' in text
    assert 'function advanceDenom' in text
    assert 'kpReplace=true' in text
    assert 'body.keypad-open' in text
