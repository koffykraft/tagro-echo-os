from __future__ import annotations

import base64
import json
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Any, Mapping

from .cash_runtime import _ENTRY_TYPES, _CHANNELS, _EXPENSE_ROLES, _CONFIDENCE, _active_user, _branch, _session_summary
from .config import RuntimeConfig
from .database import connect


class CashDocumentRuntimeError(ValueError):
    pass


_MAX_IMAGE_BYTES = 3 * 1024 * 1024


def _stable_id(prefix: str, enterprise_id: str, key: str) -> str:
    return f"{prefix}-{sha256(f'{enterprise_id}|{key}'.encode()).hexdigest()[:24]}"


def _money(value: Any, name: str, *, allow_zero: bool = False) -> Decimal:
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise CashDocumentRuntimeError(f"{name} must be numeric") from exc
    if amount < 0 or (amount == 0 and not allow_zero):
        raise CashDocumentRuntimeError(f"{name} must be {'non-negative' if allow_zero else 'positive'}")
    return amount


def _decode_image(data_url: Any) -> tuple[bytes | None, str | None, str | None]:
    raw = str(data_url or "").strip()
    if not raw:
        return None, None, None
    prefix = "data:image/png;base64,"
    if not raw.startswith(prefix):
        raise CashDocumentRuntimeError("rendered_image_data_url must be PNG data URL")
    try:
        image = base64.b64decode(raw[len(prefix):], validate=True)
    except Exception as exc:
        raise CashDocumentRuntimeError("rendered image is not valid base64 PNG") from exc
    if not image or len(image) > _MAX_IMAGE_BYTES:
        raise CashDocumentRuntimeError("rendered image exceeds admitted size")
    if not image.startswith(b"\x89PNG\r\n\x1a\n"):
        raise CashDocumentRuntimeError("rendered image is not PNG")
    return image, sha256(image).hexdigest(), "image/png"


def _normalize_entries(raw_entries: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_entries, list):
        raise CashDocumentRuntimeError("entries must be a list")
    if len(raw_entries) > 500:
        raise CashDocumentRuntimeError("too many Closing Cash entries")
    rows: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_entries, start=1):
        if not isinstance(raw, Mapping):
            raise CashDocumentRuntimeError(f"entry {index} must be an object")
        entry_type = str(raw.get("entry_type") or "").strip()
        channel = str(raw.get("channel") or "other").strip().lower()
        if entry_type not in _ENTRY_TYPES:
            raise CashDocumentRuntimeError(f"entry {index} type is not admitted")
        if channel not in _CHANNELS:
            raise CashDocumentRuntimeError(f"entry {index} channel is not admitted")
        role = str(raw.get("classification_role") or "unknown").strip().lower()
        confidence = str(raw.get("classification_confidence") or "unknown").strip().lower()
        category = str(raw.get("classification_category") or "").strip()
        if role not in _EXPENSE_ROLES or confidence not in _CONFIDENCE:
            raise CashDocumentRuntimeError(f"entry {index} has invalid classification")
        if role != "unknown" and (not category or confidence == "unknown"):
            raise CashDocumentRuntimeError(f"entry {index} classification is incomplete")
        if role == "unknown" and (category or confidence != "unknown"):
            raise CashDocumentRuntimeError(f"entry {index} partial classification is not admitted")
        if not entry_type.startswith("expense_") and role != "unknown":
            raise CashDocumentRuntimeError(f"entry {index} non-expense cannot carry expense classification")
        rows.append({
            "entry_type": entry_type,
            "channel": channel,
            "amount": _money(raw.get("amount"), f"entry {index} amount"),
            "reference": str(raw.get("reference") or "").strip(),
            "evidence_ref": str(raw.get("evidence_ref") or "").strip(),
            "note": str(raw.get("note") or "").strip(),
            "classification_category": category or None,
            "classification_role": role,
            "classification_confidence": confidence,
        })
    return rows


def save_cash_document(
    config: RuntimeConfig,
    *,
    principal_id: str,
    membership: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    capabilities = {str(x).upper() for x in membership.get("capabilities") or []}
    if "CASH" not in capabilities:
        raise PermissionError("CASH capability required")

    enterprise_id = str(membership.get("enterprise_id") or "")
    if not enterprise_id or str(payload.get("enterprise_id") or enterprise_id) != enterprise_id:
        raise CashDocumentRuntimeError("enterprise selection does not match authenticated membership")
    branch_code = str(payload.get("branch_code") or "").strip().upper()
    business_date_raw = str(payload.get("business_date") or "").strip()
    key = str(payload.get("idempotency_key") or "").strip()
    document_schema = str(payload.get("document_schema") or "tagro.echo.closing-cash-document.v1").strip()
    entered_for_label = str(payload.get("entered_for_label") or "").strip()
    switch_reason = str(payload.get("context_switch_reason") or "").strip()
    document = payload.get("document")
    if not branch_code or not business_date_raw or not key or not entered_for_label:
        raise CashDocumentRuntimeError("branch_code, business_date, entered_for_label and idempotency_key are required")
    if not isinstance(document, Mapping):
        raise CashDocumentRuntimeError("document must be an object")
    if len(json.dumps(document, default=str)) > 750_000:
        raise CashDocumentRuntimeError("Closing Cash document is too large")
    try:
        business_date = date.fromisoformat(business_date_raw)
    except ValueError as exc:
        raise CashDocumentRuntimeError("business_date must be ISO date") from exc

    opening = _money(payload.get("opening_cash", 0), "opening_cash", allow_zero=True)
    declared = _money(payload.get("declared_closing", 0), "declared_closing", allow_zero=True)
    entries = _normalize_entries(payload.get("entries") or [])
    image_bytes, image_sha, image_mime = _decode_image(payload.get("rendered_image_data_url"))

    stable_request = {
        "enterprise_id": enterprise_id,
        "branch_code": branch_code,
        "business_date": business_date_raw,
        "opening_cash": str(opening),
        "declared_closing": str(declared),
        "entered_for_label": entered_for_label,
        "context_switch_reason": switch_reason,
        "document_schema": document_schema,
        "document": document,
        "entries": [{**row, "amount": str(row["amount"])} for row in entries],
        "rendered_image_sha256": image_sha,
    }
    request_hash = sha256(json.dumps(stable_request, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
    session_id = _stable_id("echo-cash-day", enterprise_id, key)
    document_id = _stable_id("echo-cash-document", enterprise_id, key)
    event_id = _stable_id("echo-cash-event", enterprise_id, key)
    now = datetime.now(timezone.utc)

    with connect(config) as conn:
        with conn.transaction():
            user_id = _active_user(conn, enterprise_id, principal_id)
            branch_id = _branch(conn, enterprise_id, branch_code)

            existing = conn.execute(
                "select document_id,session_id,request_hash,rendered_image_sha256,saved_at from cash_saved_documents where enterprise_id=%s and source_idempotency_key=%s",
                (enterprise_id, key),
            ).fetchone()
            if existing:
                if str(existing[2]) != request_hash:
                    raise CashDocumentRuntimeError("idempotency key was reused with changed Closing Cash document")
                return {
                    "document_id": str(existing[0]),
                    "session": _session_summary(conn, enterprise_id, str(existing[1])),
                    "rendered_image_sha256": existing[3],
                    "saved_at": existing[4].isoformat(),
                    "shared_persistence": "confirmed",
                    "idempotent_replay": True,
                }

            active = conn.execute(
                """
                select session_id from cash_day_sessions
                where enterprise_id=%s and branch_id=%s and business_date=%s
                  and status in ('draft','submitted','approved')
                """,
                (enterprise_id, branch_id, business_date),
            ).fetchone()
            if active:
                raise CashDocumentRuntimeError("an active Closing Cash day already exists for this branch/date")

            note = f"entered_for={entered_for_label}"
            if switch_reason:
                note += f"; context_switch_reason={switch_reason}"
            conn.execute(
                """
                insert into cash_day_sessions(
                  session_id,enterprise_id,branch_id,business_date,opening_cash,declared_closing,status,
                  created_at,created_by,submitted_at,submitted_by,approved_at,approved_by,supersedes_session_id,note
                ) values(%s,%s,%s,%s,%s,%s,'submitted',%s,%s,%s,%s,null,null,null,%s)
                """,
                (session_id, enterprise_id, branch_id, business_date, opening, declared, now, user_id, now, user_id, note),
            )

            for index, row in enumerate(entries, start=1):
                entry_key = f"{key}:entry:{index}"
                entry_id = _stable_id("echo-cash-entry", enterprise_id, entry_key)
                conn.execute(
                    """
                    insert into cash_entry_evidence(
                      entry_id,session_id,enterprise_id,branch_id,business_date,entry_type,channel,amount,
                      reference,evidence_ref,note,occurred_at,actor_id,idempotency_key,
                      classification_category,classification_role,classification_confidence
                    ) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        entry_id, session_id, enterprise_id, branch_id, business_date,
                        row["entry_type"], row["channel"], row["amount"], row["reference"], row["evidence_ref"], row["note"],
                        now, user_id, entry_key, row["classification_category"], row["classification_role"], row["classification_confidence"],
                    ),
                )

            conn.execute(
                """
                insert into cash_saved_documents(
                  document_id,enterprise_id,session_id,branch_id,business_date,saved_at,saved_by,
                  entered_for_label,context_switch_reason,document_schema,document_json,
                  rendered_image_png,rendered_image_sha256,rendered_image_mime,request_hash,source_idempotency_key
                ) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s)
                """,
                (
                    document_id, enterprise_id, session_id, branch_id, business_date, now, user_id,
                    entered_for_label, switch_reason, document_schema,
                    json.dumps(document, sort_keys=True, separators=(",", ":"), default=str),
                    image_bytes, image_sha, image_mime, request_hash, key,
                ),
            )

            event_payload = {
                "schema": "tagro.echo.closing-cash-document-admission.v1",
                "document_id": document_id,
                "session_id": session_id,
                "branch_code": branch_code,
                "business_date": business_date_raw,
                "entered_for_label": entered_for_label,
                "context_switch_reason": switch_reason,
                "entry_count": len(entries),
                "rendered_image_sha256": image_sha,
                "request_hash": request_hash,
            }
            conn.execute(
                """
                insert into echo_events(
                  event_id,enterprise_id,event_type,subject_type,subject_id,occurred_at,recorded_at,
                  actor_principal_id,location_ref,authority_basis,evidence_ref,provenance_ref,confidence,
                  materiality_class,sensitivity_class,payload_json,admission_state
                ) values(%s,%s,'closing_cash.document_saved','closing_cash_document',%s,%s,%s,%s,%s,%s,%s,%s,'1.0','A','internal',%s,'admitted')
                """,
                (
                    event_id, enterprise_id, document_id, now, now, principal_id, branch_id,
                    f"membership:{membership.get('membership_id','')};capability:CASH",
                    f"cash_saved_documents:{document_id}", f"closing_cash:{business_date_raw}:{branch_code}",
                    json.dumps(event_payload, sort_keys=True, separators=(",", ":")),
                ),
            )

            summary = _session_summary(conn, enterprise_id, session_id)

    return {
        "document_id": document_id,
        "session": summary,
        "rendered_image_sha256": image_sha,
        "saved_at": now.isoformat(),
        "shared_persistence": "confirmed",
        "idempotent_replay": False,
    }
