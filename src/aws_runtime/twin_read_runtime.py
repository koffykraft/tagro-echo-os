from __future__ import annotations

import json
from datetime import date
from typing import Any

from .config import RuntimeConfig
from .database import connect


class TwinReadError(ValueError):
    pass


def _date(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError as exc:
        raise TwinReadError(f"invalid date: {text}") from exc


def source_status(config: RuntimeConfig, *, enterprise_id: str) -> dict[str, Any]:
    """Return raw-source freshness plus the explicit Planar projection state."""
    with connect(config) as conn:
        counts = conn.execute(
            """
            select domain, count(*) as n, max(source_effective_at) as latest
            from twin_source_records
            where enterprise_id=%s and active=true
            group by domain
            order by domain
            """,
            (enterprise_id,),
        ).fetchall()
        latest_sync = conn.execute(
            """
            select sync_run_id,source_system,source_locator,source_as_of,completed_at,
                   record_count,inserted_count,updated_count,unchanged_count,status
            from twin_source_sync_runs
            where enterprise_id=%s
            order by completed_at desc nulls last, started_at desc
            limit 20
            """,
            (enterprise_id,),
        ).fetchall()
        branch_counts = conn.execute(
            """
            select branch_code, count(*) as n, max(source_effective_at) as latest
            from twin_source_records
            where enterprise_id=%s and active=true and branch_code<>''
            group by branch_code
            order by branch_code
            """,
            (enterprise_id,),
        ).fetchall()
        planar_counts: dict[str, int] = {}
        for name, table in (
            ("entities","twin_planar_entities"),
            ("events","twin_planar_events"),
            ("event_entities","twin_planar_event_entities"),
            ("evidence","twin_planar_evidence"),
            ("relationships","twin_planar_relationships"),
        ):
            row = conn.execute(f"select count(*) from {table} where enterprise_id=%s",(enterprise_id,)).fetchone()
            planar_counts[name] = int(row[0] if row else 0)
        state = conn.execute(
            """
            select last_sync_run_id,last_source_as_of,updated_at,status,details_json
            from twin_planar_projection_state
            where enterprise_id=%s and projection_code='TAGRO_HISTORY_PLANAR'
            """,
            (enterprise_id,),
        ).fetchone()

    return {
        "schema": "tagro.echo.operational-twin-source-status.v2",
        "database_primary": True,
        "planar_preserved": True,
        "raw_intake": {
            "domains": [
                {"domain": r[0], "records": int(r[1]), "latest_source_effective_at": r[2].isoformat() if r[2] else None}
                for r in counts
            ],
            "branches": [
                {"branch_code": r[0], "records": int(r[1]), "latest_source_effective_at": r[2].isoformat() if r[2] else None}
                for r in branch_counts
            ],
        },
        "planar": {
            "status": state[3] if state else "not_loaded",
            "counts": planar_counts,
            "last_sync_run_id": state[0] if state else None,
            "last_source_as_of": state[1].isoformat() if state and state[1] else None,
            "updated_at": state[2].isoformat() if state and state[2] else None,
            "details": json.loads(state[4]) if state and state[4] else {},
        },
        "recent_sync_runs": [
            {
                "sync_run_id": r[0], "source_system": r[1], "source_locator": r[2],
                "source_as_of": r[3].isoformat() if r[3] else None,
                "completed_at": r[4].isoformat() if r[4] else None,
                "record_count": int(r[5]), "inserted": int(r[6]), "updated": int(r[7]),
                "unchanged": int(r[8]), "status": r[9],
            }
            for r in latest_sync
        ],
    }


def history_search(
    config: RuntimeConfig,
    *,
    enterprise_id: str,
    domain: str | None = None,
    branch_code: str | None = None,
    record_type: str | None = None,
    event_type: str | None = None,
    start: str | None = None,
    end: str | None = None,
    query: str | None = None,
    limit: int = 100,
    cursor: int = 0,
    mode: str = "planar",
) -> dict[str, Any]:
    """Read historical working material from PostgreSQL.

    `planar` is the normal business/BIS lane. `raw` is retained for provenance and
    diagnostic use and must not become the ordinary frontend data model.
    """
    try:
        limit = max(1, min(int(limit), 200))
        cursor = max(0, int(cursor))
    except (TypeError, ValueError) as exc:
        raise TwinReadError("limit and cursor must be integers") from exc

    if str(mode or "planar").lower() == "raw":
        clauses = ["enterprise_id=%s", "active=true"]
        params: list[Any] = [enterprise_id]
        if domain:
            clauses.append("domain=%s")
            params.append(domain)
        if branch_code:
            clauses.append("branch_code=%s")
            params.append(branch_code.upper())
        if record_type:
            clauses.append("record_type=%s")
            params.append(record_type)
        if query:
            clauses.append("payload_json ilike %s")
            params.append(f"%{query}%")
        with connect(config) as conn:
            total = conn.execute(
                f"select count(*) from twin_source_records where {' and '.join(clauses)}",
                tuple(params),
            ).fetchone()[0]
            rows = conn.execute(
                f"""
                select record_id,source_system,source_locator,source_class,branch_code,domain,record_type,
                       source_record_id,source_effective_at,source_updated_at,ingested_at,payload_json,provenance_json
                from twin_source_records
                where {' and '.join(clauses)}
                order by source_effective_at desc nulls last, ingested_at desc
                limit %s offset %s
                """,
                tuple(params + [limit, cursor]),
            ).fetchall()
        records = [
            {
                "record_id": r[0], "source_system": r[1], "source_locator": r[2], "source_class": r[3],
                "branch_code": r[4], "domain": r[5], "record_type": r[6], "source_record_id": r[7],
                "source_effective_at": r[8].isoformat() if r[8] else None,
                "source_updated_at": r[9].isoformat() if r[9] else None,
                "ingested_at": r[10].isoformat() if r[10] else None,
                "payload": json.loads(r[11]), "provenance": json.loads(r[12]),
            }
            for r in rows
        ]
        return {
            "schema": "tagro.echo.operational-twin-history.raw.v2",
            "database_primary": True,
            "mode": "raw",
            "total": int(total), "cursor": cursor, "limit": limit,
            "next_cursor": cursor + len(records) if cursor + len(records) < int(total) else None,
            "records": records,
        }

    clauses = ["enterprise_id=%s"]
    params = [enterprise_id]
    if branch_code:
        clauses.append("branch_code=%s")
        params.append(branch_code.upper())
    requested_type = event_type or record_type
    if requested_type:
        clauses.append("event_type=%s")
        params.append(requested_type)
    if start:
        clauses.append("event_date >= %s")
        params.append(_date(start))
    if end:
        clauses.append("event_date <= %s")
        params.append(_date(end))
    if query:
        clauses.append("(summary ilike %s or attributes_json ilike %s)")
        params.extend([f"%{query}%", f"%{query}%"])

    with connect(config) as conn:
        total = conn.execute(
            f"select count(*) from twin_planar_event_read where {' and '.join(clauses)}",
            tuple(params),
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            select event_id,event_type,event_date,branch_code,amount,summary,confidence,
                   evidence_count,entity_count,source_sync_run_id,source_effective_at,ingested_at
            from twin_planar_event_read
            where {' and '.join(clauses)}
            order by event_date desc nulls last,event_id
            limit %s offset %s
            """,
            tuple(params + [limit, cursor]),
        ).fetchall()

    records = [
        {
            "event_id": r[0], "event_type": r[1], "event_date": r[2].isoformat() if r[2] else None,
            "branch_code": r[3], "amount": float(r[4]) if r[4] is not None else None,
            "summary": r[5], "confidence": float(r[6]) if r[6] is not None else None,
            "evidence_count": int(r[7]), "entity_count": int(r[8]), "source_sync_run_id": r[9],
            "source_effective_at": r[10].isoformat() if r[10] else None,
            "ingested_at": r[11].isoformat() if r[11] else None,
        }
        for r in rows
    ]
    return {
        "schema": "tagro.echo.operational-twin-history.planar.v2",
        "database_primary": True,
        "planar_preserved": True,
        "mode": "planar",
        "filters": {"branch": branch_code, "event_type": requested_type, "start": start, "end": end, "q": query},
        "total": int(total), "cursor": cursor, "limit": limit,
        "next_cursor": cursor + len(records) if cursor + len(records) < int(total) else None,
        "records": records,
    }
