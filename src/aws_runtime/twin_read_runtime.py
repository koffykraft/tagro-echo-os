from __future__ import annotations

import json
from typing import Any

from .config import RuntimeConfig
from .database import connect


class TwinReadError(ValueError):
    pass


def source_status(config: RuntimeConfig, *, enterprise_id: str) -> dict[str, Any]:
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
    return {
        "schema": "tagro.echo.operational-twin-source-status.v1",
        "database_primary": True,
        "domains": [
            {"domain": r[0], "records": int(r[1]), "latest_source_effective_at": r[2].isoformat() if r[2] else None}
            for r in counts
        ],
        "branches": [
            {"branch_code": r[0], "records": int(r[1]), "latest_source_effective_at": r[2].isoformat() if r[2] else None}
            for r in branch_counts
        ],
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
    query: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    limit = max(1, min(int(limit), 500))
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
    params.append(limit)
    sql = f"""
      select record_id,source_system,source_locator,source_class,branch_code,domain,record_type,
             source_record_id,source_effective_at,source_updated_at,ingested_at,payload_json,provenance_json
      from twin_source_records
      where {' and '.join(clauses)}
      order by source_effective_at desc nulls last, ingested_at desc
      limit %s
    """
    with connect(config) as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
    return {
        "schema": "tagro.echo.operational-twin-history.v1",
        "database_primary": True,
        "records": [
            {
                "record_id": r[0], "source_system": r[1], "source_locator": r[2], "source_class": r[3],
                "branch_code": r[4], "domain": r[5], "record_type": r[6], "source_record_id": r[7],
                "source_effective_at": r[8].isoformat() if r[8] else None,
                "source_updated_at": r[9].isoformat() if r[9] else None,
                "ingested_at": r[10].isoformat() if r[10] else None,
                "payload": json.loads(r[11]), "provenance": json.loads(r[12]),
            }
            for r in rows
        ],
    }
