from __future__ import annotations

import json
from typing import Any, Mapping

from .busy_round_trip import BusyRoundTripError, build_envelope, persist_envelope
from .config import RuntimeConfig
from .database import connect


CAPABILITIES = {
    "sale": {"SELL"}, "purchase": {"PURCHASE"}, "receipt": {"CASH"},
    "payment": {"CASH"}, "item_master": {"STOCK", "PURCHASE"},
    "account_master": {"SELL", "SERVICE", "ACCOUNTS"},
}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def save_busy_record(config: RuntimeConfig, *, principal_id: str, membership: Mapping[str, Any], payload: Mapping[str, Any]) -> dict[str, Any]:
    kind = _clean(payload.get("record_kind")).lower()
    needed = CAPABILITIES.get(kind)
    caps = {str(x).upper() for x in membership.get("capabilities") or []}
    if not needed:
        raise BusyRoundTripError("unsupported BUSY record kind")
    if not (needed & caps) and str(membership.get("role_code") or "").upper() != "OWNER":
        raise PermissionError(f"one of {sorted(needed)} capabilities is required")

    normalized = payload.get("normalized")
    if not isinstance(normalized, Mapping):
        raise BusyRoundTripError("normalized record is required")
    enterprise_id = _clean(membership.get("enterprise_id"))
    branch_id = _clean(payload.get("branch_id")) or None
    mapping_version = _clean(payload.get("mapping_version")) or "busy-web-v0.11"
    # The browser cannot self-certify a physical BUSY mapping. Only a server-side
    # mapping release can be admitted here after write/read-back verification.
    validated_versions = {x.strip() for x in _clean(__import__('os').getenv("BUSY_VALIDATED_MAPPING_VERSIONS")).split(",") if x.strip()}
    envelope = build_envelope(
        enterprise_id=enterprise_id,
        branch_id=branch_id,
        record_kind=kind,
        operation=_clean(payload.get("operation")) or "create",
        business_record_id=_clean(payload.get("business_record_id")),
        normalized=normalized,
        busy_raw=payload.get("busy_raw") if isinstance(payload.get("busy_raw"), Mapping) else {},
        busy_unknown=payload.get("busy_unknown") if isinstance(payload.get("busy_unknown"), Mapping) else {},
        mapping_version=mapping_version,
        mapping_validated=mapping_version in validated_versions,
        source_system="tagro_echo_web",
        source_file=_clean(payload.get("source_file")),
        source_record=_clean(payload.get("source_record")),
        idempotency_key=_clean(payload.get("idempotency_key")),
        created_by=principal_id,
    )
    with connect(config) as conn:
        with conn.transaction():
            user = conn.execute(
                "select user_id,branch_id from users where enterprise_id=%s and principal_id=%s and active=true",
                (enterprise_id, principal_id),
            ).fetchone()
            if not user:
                raise BusyRoundTripError("authenticated principal has no active ECHO user")
            if str(membership.get("role_code") or "").upper() != "OWNER":
                if not user[1] or not branch_id or str(user[1]) != branch_id:
                    raise PermissionError("BUSY records are restricted to the user's branch")
            persist_envelope(conn, envelope)
    return {k: envelope[k] for k in ("record_id", "record_kind", "mapping_status", "write_status", "uncertainty", "updated_at")}


def read_busy_records(config: RuntimeConfig, *, enterprise_id: str, kind: str = "", limit: int = 50, created_by: str = "") -> list[dict[str, Any]]:
    limit = min(max(int(limit), 1), 200)
    params: list[Any] = [enterprise_id]
    where = "enterprise_id=%s"
    if kind:
        where += " and record_kind=%s"
        params.append(kind)
    if created_by:
        where += " and created_by=%s"
        params.append(created_by)
    params.append(limit)
    with connect(config) as conn:
        rows = conn.execute(
            f"select record_id,record_kind,business_date,normalized_json,mapping_status,write_status,uncertainty,updated_at from busy_round_trip_records where {where} order by updated_at desc limit %s",
            tuple(params),
        ).fetchall()
    return [
        {"record_id": r[0], "record_kind": r[1], "business_date": r[2], "normalized": r[3] if isinstance(r[3], dict) else json.loads(r[3]), "mapping_status": r[4], "write_status": r[5], "uncertainty": r[6], "updated_at": r[7]}
        for r in rows
    ]
