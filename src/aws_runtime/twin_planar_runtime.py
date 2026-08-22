from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any, Mapping

from .config import RuntimeConfig
from .database import connect
from .twin_ingest_runtime import TwinIngestError, sync_source_records


class TwinPlanarError(ValueError):
    pass


def _stable_json(value: Any) -> str:
    return json.dumps(value if value is not None else {}, sort_keys=True, separators=(",", ":"), default=str)


def _as_date(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError as exc:
        raise TwinPlanarError(f"invalid date: {text}") from exc


def _as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def sync_planar_records(
    config: RuntimeConfig,
    *,
    enterprise_id: str,
    source_system: str,
    source_locator: str,
    source_class: str,
    source_as_of: str | None,
    sync_run_id: str,
    records: list[Mapping[str, Any]],
    provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist a Planar export into raw intake + explicit PostgreSQL planes.

    Expected record_type values mirror the existing TAGRO AWS OS planar.sqlite
    tables: entity, event, event_entity, evidence, relationship. Unknown record
    types remain in the raw twin_source_records layer but are not projected.
    """
    raw_result = sync_source_records(
        config,
        enterprise_id=enterprise_id,
        source_system=source_system,
        source_locator=source_locator,
        source_class=source_class,
        source_as_of=source_as_of,
        records=records,
        sync_run_id=sync_run_id,
        provenance=provenance,
    )

    projected = {"entity": 0, "event": 0, "event_entity": 0, "evidence": 0, "relationship": 0, "other": 0}
    now = datetime.now(timezone.utc)

    with connect(config) as conn:
        with conn.transaction():
            for raw in records:
                record_type = str(raw.get("record_type") or "").strip().lower()
                payload = raw.get("payload") if isinstance(raw.get("payload"), Mapping) else raw

                if record_type == "entity":
                    entity_id = str(payload.get("entity_id") or raw.get("source_record_id") or "").strip()
                    if not entity_id:
                        raise TwinPlanarError("entity requires entity_id")
                    conn.execute(
                        """
                        insert into twin_planar_entities(
                          enterprise_id,entity_id,entity_type,canonical_name,branch_code,
                          attributes_json,confidence,source_sync_run_id,source_updated_at,ingested_at
                        ) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        on conflict(enterprise_id,entity_id) do update set
                          entity_type=excluded.entity_type,
                          canonical_name=excluded.canonical_name,
                          branch_code=excluded.branch_code,
                          attributes_json=excluded.attributes_json,
                          confidence=excluded.confidence,
                          source_sync_run_id=excluded.source_sync_run_id,
                          source_updated_at=excluded.source_updated_at,
                          ingested_at=excluded.ingested_at
                        """,
                        (
                            enterprise_id, entity_id,
                            str(payload.get("entity_type") or "unknown"),
                            str(payload.get("canonical_name") or ""),
                            str(payload.get("branch") or payload.get("branch_code") or "").upper(),
                            _stable_json(payload.get("attributes_json") or payload.get("attributes") or {}),
                            _as_float(payload.get("confidence")), sync_run_id,
                            raw.get("source_updated_at") or None, now,
                        ),
                    )
                    projected["entity"] += 1
                    continue

                if record_type == "event":
                    event_id = str(payload.get("event_id") or raw.get("source_record_id") or "").strip()
                    if not event_id:
                        raise TwinPlanarError("event requires event_id")
                    conn.execute(
                        """
                        insert into twin_planar_events(
                          enterprise_id,event_id,event_type,event_date,branch_code,amount,summary,
                          attributes_json,confidence,source_sync_run_id,source_effective_at,
                          source_updated_at,ingested_at
                        ) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        on conflict(enterprise_id,event_id) do update set
                          event_type=excluded.event_type,event_date=excluded.event_date,
                          branch_code=excluded.branch_code,amount=excluded.amount,summary=excluded.summary,
                          attributes_json=excluded.attributes_json,confidence=excluded.confidence,
                          source_sync_run_id=excluded.source_sync_run_id,
                          source_effective_at=excluded.source_effective_at,
                          source_updated_at=excluded.source_updated_at,ingested_at=excluded.ingested_at
                        """,
                        (
                            enterprise_id, event_id,
                            str(payload.get("event_type") or "historical_event"),
                            _as_date(payload.get("event_date")),
                            str(payload.get("branch") or payload.get("branch_code") or "").upper(),
                            _as_float(payload.get("amount")),
                            str(payload.get("summary") or ""),
                            _stable_json(payload.get("attributes_json") or payload.get("attributes") or payload),
                            _as_float(payload.get("confidence")), sync_run_id,
                            raw.get("source_effective_at") or None,
                            raw.get("source_updated_at") or None, now,
                        ),
                    )
                    projected["event"] += 1
                    continue

                if record_type == "event_entity":
                    event_id = str(payload.get("event_id") or "").strip()
                    entity_id = str(payload.get("entity_id") or "").strip()
                    role = str(payload.get("role") or "related").strip()
                    if not event_id or not entity_id:
                        raise TwinPlanarError("event_entity requires event_id and entity_id")
                    conn.execute(
                        """
                        insert into twin_planar_event_entities(
                          enterprise_id,event_id,entity_id,role,source_sync_run_id,ingested_at
                        ) values(%s,%s,%s,%s,%s,%s)
                        on conflict(enterprise_id,event_id,entity_id,role) do update set
                          source_sync_run_id=excluded.source_sync_run_id,ingested_at=excluded.ingested_at
                        """,
                        (enterprise_id,event_id,entity_id,role,sync_run_id,now),
                    )
                    projected["event_entity"] += 1
                    continue

                if record_type == "evidence":
                    evidence_id = str(payload.get("evidence_id") or raw.get("source_record_id") or "").strip()
                    event_id = str(payload.get("event_id") or "").strip()
                    if not evidence_id or not event_id:
                        raise TwinPlanarError("evidence requires evidence_id and event_id")
                    conn.execute(
                        """
                        insert into twin_planar_evidence(
                          enterprise_id,evidence_id,event_id,source_domain,source_database,
                          source_record_id,source_path,evidence_json,source_sha256,
                          source_sync_run_id,ingested_at
                        ) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        on conflict(enterprise_id,evidence_id) do update set
                          event_id=excluded.event_id,source_domain=excluded.source_domain,
                          source_database=excluded.source_database,source_record_id=excluded.source_record_id,
                          source_path=excluded.source_path,evidence_json=excluded.evidence_json,
                          source_sha256=excluded.source_sha256,source_sync_run_id=excluded.source_sync_run_id,
                          ingested_at=excluded.ingested_at
                        """,
                        (
                            enterprise_id,evidence_id,event_id,
                            str(payload.get("source_domain") or "unknown"),
                            str(payload.get("source_database") or ""),
                            str(payload.get("source_record_id") or ""),
                            str(payload.get("source_path") or ""),
                            _stable_json(payload.get("evidence_json") or payload.get("evidence") or payload),
                            str(payload.get("source_sha256") or ""),sync_run_id,now,
                        ),
                    )
                    projected["evidence"] += 1
                    continue

                if record_type == "relationship":
                    relationship_id = str(payload.get("relationship_id") or raw.get("source_record_id") or "").strip()
                    if not relationship_id:
                        raise TwinPlanarError("relationship requires relationship_id")
                    conn.execute(
                        """
                        insert into twin_planar_relationships(
                          enterprise_id,relationship_id,from_entity_id,to_entity_id,relationship_type,
                          start_date,end_date,evidence_id,confidence,source_sync_run_id,ingested_at
                        ) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        on conflict(enterprise_id,relationship_id) do update set
                          from_entity_id=excluded.from_entity_id,to_entity_id=excluded.to_entity_id,
                          relationship_type=excluded.relationship_type,start_date=excluded.start_date,
                          end_date=excluded.end_date,evidence_id=excluded.evidence_id,
                          confidence=excluded.confidence,source_sync_run_id=excluded.source_sync_run_id,
                          ingested_at=excluded.ingested_at
                        """,
                        (
                            enterprise_id,relationship_id,
                            str(payload.get("from_entity_id") or ""),str(payload.get("to_entity_id") or ""),
                            str(payload.get("relationship_type") or "related"),
                            _as_date(payload.get("start_date")),_as_date(payload.get("end_date")),
                            str(payload.get("evidence_id") or ""),_as_float(payload.get("confidence")),
                            sync_run_id,now,
                        ),
                    )
                    projected["relationship"] += 1
                    continue

                projected["other"] += 1

            conn.execute(
                """
                insert into twin_planar_projection_state(
                  enterprise_id,projection_code,last_sync_run_id,last_source_as_of,updated_at,status,details_json
                ) values(%s,'TAGRO_HISTORY_PLANAR',%s,%s,%s,'ready',%s)
                on conflict(enterprise_id,projection_code) do update set
                  last_sync_run_id=excluded.last_sync_run_id,
                  last_source_as_of=excluded.last_source_as_of,
                  updated_at=excluded.updated_at,status='ready',details_json=excluded.details_json
                """,
                (enterprise_id,sync_run_id,source_as_of or None,now,_stable_json(projected)),
            )

    return {**raw_result, "projected": projected, "planar_projection": "ready"}


def planar_status(config: RuntimeConfig, *, enterprise_id: str) -> dict[str, Any]:
    with connect(config) as conn:
        counts = {}
        for name, table in (
            ("entities","twin_planar_entities"),
            ("events","twin_planar_events"),
            ("event_entities","twin_planar_event_entities"),
            ("evidence","twin_planar_evidence"),
            ("relationships","twin_planar_relationships"),
        ):
            row = conn.execute(f"select count(*) from {table} where enterprise_id=%s",(enterprise_id,)).fetchone()
            counts[name] = int(row[0] if row else 0)
        state = conn.execute(
            """
            select last_sync_run_id,last_source_as_of,updated_at,status,details_json
            from twin_planar_projection_state
            where enterprise_id=%s and projection_code='TAGRO_HISTORY_PLANAR'
            """,
            (enterprise_id,),
        ).fetchone()
    return {
        "schema":"tagro.echo.planar-status.v1",
        "counts":counts,
        "last_sync_run_id": state[0] if state else None,
        "last_source_as_of": state[1].isoformat() if state and state[1] else None,
        "updated_at": state[2].isoformat() if state and state[2] else None,
        "status": state[3] if state else "not_loaded",
        "details": json.loads(state[4]) if state and state[4] else {},
    }


def history_readback(
    config: RuntimeConfig,
    *,
    enterprise_id: str,
    branch: str | None = None,
    event_type: str | None = None,
    start: str | None = None,
    end: str | None = None,
    query: str | None = None,
    limit: int | str = 50,
    cursor: int | str = 0,
) -> dict[str, Any]:
    try:
        limit_i = max(1,min(int(limit),200))
        offset_i = max(0,int(cursor))
    except (TypeError,ValueError) as exc:
        raise TwinPlanarError("limit/cursor must be integers") from exc

    where = ["enterprise_id=%s"]
    params: list[Any] = [enterprise_id]
    if branch:
        where.append("branch_code=%s")
        params.append(str(branch).upper())
    if event_type:
        where.append("event_type=%s")
        params.append(str(event_type))
    if start:
        where.append("event_date >= %s")
        params.append(_as_date(start))
    if end:
        where.append("event_date <= %s")
        params.append(_as_date(end))
    if query:
        where.append("summary ilike %s")
        params.append("%"+str(query).strip()+"%")

    clause = " and ".join(where)
    with connect(config) as conn:
        total = conn.execute(f"select count(*) from twin_planar_event_read where {clause}",tuple(params)).fetchone()[0]
        rows = conn.execute(
            f"""
            select event_id,event_type,event_date,branch_code,amount,summary,confidence,
                   evidence_count,entity_count,source_sync_run_id,source_effective_at,ingested_at
            from twin_planar_event_read
            where {clause}
            order by event_date desc nulls last,event_id
            limit %s offset %s
            """,
            tuple(params+[limit_i,offset_i]),
        ).fetchall()

    items = [
        {
            "event_id":r[0],"event_type":r[1],"event_date":r[2].isoformat() if r[2] else None,
            "branch":r[3],"amount":float(r[4]) if r[4] is not None else None,"summary":r[5],
            "confidence":float(r[6]) if r[6] is not None else None,"evidence_count":int(r[7]),
            "entity_count":int(r[8]),"source_sync_run_id":r[9],
            "source_effective_at":r[10].isoformat() if r[10] else None,
            "ingested_at":r[11].isoformat() if r[11] else None,
        }
        for r in rows
    ]
    next_cursor = offset_i + len(items) if offset_i + len(items) < int(total) else None
    return {
        "schema":"tagro.echo.history-readback.v1",
        "database_primary":True,
        "filters":{"branch":branch,"event_type":event_type,"start":start,"end":end,"q":query},
        "total":int(total),"limit":limit_i,"cursor":offset_i,"next_cursor":next_cursor,"items":items,
    }
