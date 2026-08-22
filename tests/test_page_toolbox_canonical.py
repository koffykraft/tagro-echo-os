from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_page_toolbox_matches_governed_definition_contract():
    html = (ROOT / 'web' / 'page-toolbox.html').read_text(encoding='utf-8')
    assert "owner_edit_only:true" in html
    assert "responsive_columns:4" in html
    assert "binding:kind==='field'?{path:'local.value',mode:'input'}:null" in html
    assert "requires_owner:false,consequential:false" in html
    for component in ('tile','button','field','list','table','chart','link','text','heading','status'):
        assert component in html
    for action in ('navigate','open_form','submit','refresh','export','filter'):
        assert action in html
    assert 'Consequential actions must require owner authority.' in html
    assert "ROOTS=['context','customer','product','stock','service','financial','document','local']" in html
    assert 'echo.page-definition.' in html


def test_canonical_page_toolbox_is_phone_first_and_does_not_execute_actions():
    html = (ROOT / 'web' / 'page-toolbox.html').read_text(encoding='utf-8').lower()
    assert '@media(max-width:900px)' in html
    assert '@media(max-width:520px)' in html
    assert 'eval(' not in html
    assert 'new function' not in html
    assert 'javascript:' not in html
