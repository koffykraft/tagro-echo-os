from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "web" / "closing-cash.html").read_text(encoding="utf-8")


def test_closing_cash_uses_local_business_date_and_loads_existing_day_first():
    assert "getTimezoneOffset" in HTML
    assert "async function loadExisting()" in HTML
    assert "const existing=await loadExisting()" in HTML
    assert "Existing shared cash day loaded" in HTML
    assert "'/cash-days?'" in HTML


def test_closing_cash_requires_explicit_zero_instead_of_defaulting_blank_to_zero():
    assert "openingCash.value===''" in HTML
    assert "Enter 0 only when the opening cash is truly zero" in HTML
    assert "declared.value===''" in HTML
    assert "Zero must be entered explicitly" in HTML
    assert "Number(declared.value||0)" not in HTML


def test_closing_cash_controls_do_not_collide_with_function_names():
    assert "openDayBtn=$('openDay')" in HTML
    assert "addEntryBtn=$('addEntry')" in HTML
    assert "submitDayBtn=$('submitDay')" in HTML
    assert "openDayBtn.onclick=openSelectedDay" in HTML
    assert "addEntryBtn.onclick=recordEntry" in HTML
    assert "submitDayBtn.onclick=submitSelectedDay" in HTML
    assert "async function openDay()" not in HTML
    assert "async function addEntry()" not in HTML


def test_closing_cash_locks_active_day_and_preserves_evidence_draft():
    assert "dayLocked(true)" in HTML
    assert "CHOOSE ANOTHER DAY" in HTML
    assert "EchoRuntime.localKey('closing-cash-v2')" in HTML
    assert "amount:amount.value" in HTML
    assert "reference:reference.value" in HTML
    assert "entry_note:entryNote.value" in HTML
    assert "declared:declared.value" in HTML
