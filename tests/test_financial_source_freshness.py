from datetime import datetime, timedelta, timezone

from src.financial.freshness import source_freshness


def test_source_freshness_preserves_each_evidence_plane_age():
    now = datetime(2026, 8, 22, 0, 0, tzinfo=timezone.utc)
    result = source_freshness(
        {
            "sales": now - timedelta(minutes=5),
            "purchase_cost": now - timedelta(hours=3),
            "closing_cash": now - timedelta(hours=8),
            "bank": now - timedelta(days=2),
            "warehouse_projection": None,
        },
        now=now,
    )

    assert result["sources"]["sales"]["age_seconds"] == 300
    assert result["sources"]["purchase_cost"]["age_seconds"] == 10800
    assert result["sources"]["closing_cash"]["age_seconds"] == 28800
    assert result["sources"]["bank"]["age_seconds"] == 172800
    assert result["sources"]["warehouse_projection"]["missing"] is True
    assert result["newest_source"] == "sales"
    assert result["oldest_source"] == "bank"
    assert result["spread_seconds"] == 172500
    assert result["missing_sources"] == ("warehouse_projection",)


def test_source_freshness_does_not_invent_fresh_stale_business_classification():
    now = datetime(2026, 8, 22, 0, 0, tzinfo=timezone.utc)
    result = source_freshness({"sales": now - timedelta(days=90)}, now=now)

    assert result["sources"]["sales"]["age_seconds"] == 90 * 24 * 60 * 60
    assert "status" not in result["sources"]["sales"]
    assert "fresh" not in result["sources"]["sales"]
    assert "stale" not in result["sources"]["sales"]


def test_future_clock_skew_never_produces_negative_age():
    now = datetime(2026, 8, 22, 0, 0, tzinfo=timezone.utc)
    result = source_freshness({"bank": now + timedelta(seconds=30)}, now=now)
    assert result["sources"]["bank"]["age_seconds"] == 0
