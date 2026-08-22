from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping

from .config import RuntimeConfig
from .database import connect


class TwinIngestError(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return sha256(_stable_json(value).encode("utf-8")).hexdigest()


def sync_source_records(
    config: RuntimeConfig,
    *,
    enterprise_id: str,
    source_system: str,
    source_locator: str,
    source_class: str,
    source_as_of: str | None,
    records: list[Mapping[str, Any]],
    sync_run_id: str,
    provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not enterprise_id or not source_system or not source_locator or not source_class or not sync_run_id:
        raise TwinIngestError("enterprise_id, source metadata and sync_run_id are required")
    if not records:
        raise TwinIngestError("records are required")

    started_at = _now()
    inserted = updated = unchanged = 0
    package_hash = _hash(records)

    with connect(config) as conn:
        with conn.transaction():
            enterprise = conn.execute(
                "select 1 from enterprises where enterprise_id=%s",
                (enterprise_id,),
            ).fetchone()
            if not enterprise:
                raise TwinIngestError("enterprise does not exist")

            conn.execute(
                """
                insert into twin_source_sync_runs(
                  sync_run_id,enterprise_id,source_system,source_locator,source_class,source_as_of,
                  started_at,record_count,payload_hash,status,provenance_json
                ) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,'running',%s)
                on conflict(sync_run_id) do update set
                  source_as_of=excluded.source_as_of,
                  record_count=excluded.record_count,
                  payload_hash=excluded.payload_hash,
                  provenance_json=excluded.provenance_json,
                  status='running'
                """,
                (
                    sync_run_id, enterprise_id, source_system, source_locator, source_class,
                    source_as_of or None, started_at, len(records), package_hash,
                    _stable_json(provenance or {}),
                ),
            )

            for raw in records:
                record_type = str(raw.get("record_type") or "").strip()
                source_record_id = str(raw.get("source_record_id") or "").strip()
                domain = str(raw.get("domain") or "").strip()
                if not record_type or not source_record_id or not domain:
                    raise TwinIngestError("each record requires domain, record_type and source_record_id")
                branch_code = str(raw.get("branch_code") or "").strip().upper()
                payload = raw.get("payload") if isinstance(raw.get("payload"), Mapping) else dict(raw)
                content_hash = _hash(payload)
                record_id = "twin-" + sha256(
                    f"{enterprise_id}|{source_system}|{source_locator}|{record_type}|{source_record_id}".encode("utf-8")
                ).hexdigest()[:32]
                prior = conn.execute(
                    "select content_hash from twin_source_records where record_id=%s",
                    (record_id,),
                ).fetchone()
                if prior and str(prior[0]) == content_hash:
                    unchanged += 1
                    continue
                if prior:
                    updated += 1
                else:
                    inserted += 1
                conn.execute(
                    """
                    insert into twin_source_records(
                      record_id,enterprise_id,source_system,source_locator,source_class,branch_code,
                      domain,record_type,source_record_id,source_effective_at,source_updated_at,
                      ingested_at,content_hash,payload_json,provenance_json,active
                    ) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,true)
                    on conflict(record_id) do update set
                      branch_code=excluded.branch_code,
                      domain=excluded.domain,
                      source_effective_at=excluded.source_effective_at,
                      source_updated_at=excluded.source_updated_at,
                      ingested_at=excluded.ingested_at,
                      content_hash=excluded.content_hash,
                      payload_json=excluded.payload_json,
                      provenance_json=excluded.provenance_json,
                      active=true
                    """,
                    (
                        record_id, enterprise_id, source_system, source_locator, source_class,
                        branch_code, domain, record_type, source_record_id,
                        raw.get("source_effective_at") or None,
                        raw.get("source_updated_at") or None,
                        _now(), content_hash, _stable_json(payload),
                        _stable_json(raw.get("provenance") or {}),
                    ),
                )

            completed_at = _now()
            conn.execute(
                """
                update twin_source_sync_runs set
                  completed_at=%s, inserted_count=%s, updated_count=%s, unchanged_count=%s,
                  status='complete'
                where sync_run_id=%s
                """,
                (completed_at, inserted, updated, unchanged, sync_run_id),
            )

    return {
        "sync_run_id": sync_run_id,
        "source_system": source_system,
        "source_locator": source_locator,
        "source_as_of": source_as_of,
        "record_count": len(records),
        "inserted": inserted,
        "updated": updated,
        "unchanged": unchanged,
        "payload_hash": package_hash,
        "status": "complete",
    }
