from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping


def _utc(value: datetime) -> datetime:
    """Normalize a timestamp without inventing a source timezone.

    Naive timestamps are treated as UTC only because the current ECHO runtime
    stores/returns its evidence timestamps on the UTC boundary. Callers that
    hold local timestamps must make them timezone-aware before using this helper.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def source_freshness(
    evidence_sources_as_of: Mapping[str, datetime | None],
    *,
    now: datetime | None = None,
) -> dict[str, object]:
    """Describe financial evidence age source-by-source without judging it.

    A single newest timestamp can hide a stale sales, cash, bank, purchase-cost,
    or warehouse stream.  ON CALL therefore needs the ages of the individual
    evidence planes.  This helper deliberately does *not* label evidence
    fresh/stale or choose a business threshold; it reports deterministic ages
    and missing-source state for the owner/UI to inspect.
    """
    current = _utc(now or datetime.now(timezone.utc))
    sources: dict[str, dict[str, object]] = {}
    known: list[tuple[str, datetime]] = []

    for name in sorted(str(key) for key in evidence_sources_as_of):
        raw = evidence_sources_as_of.get(name)
        if raw is None:
            sources[name] = {
                "as_of": None,
                "age_seconds": None,
                "missing": True,
            }
            continue
        as_of = _utc(raw)
        age_seconds = max(0, int((current - as_of).total_seconds()))
        sources[name] = {
            "as_of": as_of,
            "age_seconds": age_seconds,
            "missing": False,
        }
        known.append((name, as_of))

    newest = max(known, key=lambda item: item[1]) if known else None
    oldest = min(known, key=lambda item: item[1]) if known else None
    missing_sources = tuple(name for name, row in sources.items() if row["missing"])

    return {
        "observed_at": current,
        "sources": sources,
        "known_source_count": len(known),
        "missing_source_count": len(missing_sources),
        "missing_sources": missing_sources,
        "newest_source": newest[0] if newest else None,
        "newest_as_of": newest[1] if newest else None,
        "oldest_source": oldest[0] if oldest else None,
        "oldest_as_of": oldest[1] if oldest else None,
        "spread_seconds": (
            int((newest[1] - oldest[1]).total_seconds()) if newest and oldest else None
        ),
    }
