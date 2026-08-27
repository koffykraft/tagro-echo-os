from __future__ import annotations

import json
from datetime import date, datetime, timezone
from hashlib import sha256
from typing import Any, Mapping


KINDS = {"sale", "purchase", "receipt", "payment", "item_master", "account_master"}

# These are the minimum web/canonical fields, not the complete BUSY physical
# record.  Complete imported fields remain in busy_raw/busy_unknown.
REQUIRED: dict[str, tuple[str, ...]] = {
    "sale": ("branch_code", "voucher_date", "series", "party", "lines"),
    "purchase": ("branch_code", "voucher_date", "series", "party", "lines"),
    "receipt": ("branch_code", "voucher_date", "series", "account", "amount"),
    "payment": ("branch_code", "voucher_date", "series", "account", "amount"),
    "item_master": ("name", "alias", "unit", "group", "tax_category", "hsn_code"),
    "account_master": ("name", "alias", "group"),
}


class BusyRoundTripError(ValueError):
    pass


def _jsonable(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def build_envelope(
    *,
    enterprise_id: str,
    branch_id: str | None,
    record_kind: str,
    operation: str,
    business_record_id: str,
    normalized: Mapping[str, Any],
    busy_raw: Mapping[str, Any] | None,
    busy_unknown: Mapping[str, Any] | None,
    mapping_version: str,
    mapping_validated: bool,
    source_system: str,
    source_file: str = "",
    source_record: str = "",
    idempotency_key: str,
    created_by: str = "",
) -> dict[str, Any]:
    kind = record_kind.strip().lower()
    if kind not in KINDS:
        raise BusyRoundTripError(f"unsupported BUSY record kind: {record_kind}")
    if operation not in {"import", "create", "update"}:
        raise BusyRoundTripError("operation must be import, create or update")
    if not enterprise_id or not idempotency_key or not mapping_version or not source_system:
        raise BusyRoundTripError("enterprise, idempotency, mapping version and source are required")

    clean = _jsonable(dict(normalized))
    raw = _jsonable(dict(busy_raw or {}))
    unknown = _jsonable(dict(busy_unknown or {}))
    missing = [field for field in REQUIRED[kind] if clean.get(field) in (None, "", [])]
    complete_physical_record = bool(raw) and not unknown
    mapping_status = "validated" if mapping_validated else ("partial" if clean else "unmapped")
    write_ready = mapping_validated and not missing and complete_physical_record
    uncertainty = []
    if missing:
        uncertainty.append("missing normalized fields: " + ", ".join(missing))
    if not mapping_validated:
        uncertainty.append("BUSY semantic mapping is not validated")
    if not raw:
        uncertainty.append("complete BUSY physical record is absent")
    if unknown:
        uncertainty.append("unresolved BUSY fields are preserved")

    now = datetime.now(timezone.utc)
    digest = sha256(f"{enterprise_id}|{idempotency_key}".encode()).hexdigest()[:24]
    return {
        "record_id": f"busy-rt-{digest}",
        "enterprise_id": enterprise_id,
        "branch_id": branch_id,
        "record_kind": kind,
        "operation": operation,
        "business_record_id": business_record_id,
        "normalized": clean,
        "busy_raw": raw,
        "busy_unknown": unknown,
        "mapping_version": mapping_version,
        "mapping_status": mapping_status,
        "write_status": "ready" if write_ready else "blocked",
        "uncertainty": "; ".join(uncertainty),
        "source_system": source_system,
        "source_file": source_file,
        "source_record": source_record,
        "idempotency_key": idempotency_key,
        "created_by": created_by,
        "created_at": now,
        "updated_at": now,
    }


def persist_envelope(connection: Any, envelope: Mapping[str, Any]) -> None:
    """Persist without dropping normalized, raw, or unresolved BUSY fields."""
    source_hash = sha256(
        json.dumps(envelope["busy_raw"], sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
    normalized = envelope["normalized"]
    connection.execute(
        """
        insert into busy_round_trip_records(
          record_id,enterprise_id,branch_id,record_kind,operation,business_record_id,business_date,
          busy_company_code,busy_financial_year,busy_table,busy_voucher_type,busy_voucher_series,
          busy_voucher_number,busy_voucher_code,busy_master_code,normalized_json,busy_raw_json,
          busy_unknown_json,mapping_version,mapping_status,write_status,uncertainty,source_system,
          source_file,source_record,source_hash,idempotency_key,created_by,created_at,updated_at
        ) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,
                 %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        on conflict(enterprise_id,idempotency_key) do update set
          normalized_json=excluded.normalized_json,busy_raw_json=excluded.busy_raw_json,
          busy_unknown_json=excluded.busy_unknown_json,mapping_status=excluded.mapping_status,
          write_status=excluded.write_status,uncertainty=excluded.uncertainty,
          source_hash=excluded.source_hash,updated_at=excluded.updated_at
        """,
        (
            envelope["record_id"], envelope["enterprise_id"], envelope.get("branch_id"),
            envelope["record_kind"], envelope["operation"], envelope["business_record_id"],
            normalized.get("voucher_date"), normalized.get("busy_company_code", ""),
            normalized.get("busy_financial_year", ""), normalized.get("busy_table", ""),
            normalized.get("voucher_type", ""), normalized.get("series", ""),
            normalized.get("voucher_number", ""), normalized.get("voucher_code", ""),
            normalized.get("master_code", ""), json.dumps(normalized, default=str),
            json.dumps(envelope["busy_raw"], default=str), json.dumps(envelope["busy_unknown"], default=str),
            envelope["mapping_version"], envelope["mapping_status"], envelope["write_status"],
            envelope["uncertainty"], envelope["source_system"], envelope.get("source_file", ""),
            envelope.get("source_record", ""), source_hash, envelope["idempotency_key"],
            envelope.get("created_by", ""), envelope["created_at"], envelope["updated_at"],
        ),
    )

