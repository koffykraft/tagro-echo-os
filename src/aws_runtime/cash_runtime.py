from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Any, Mapping

from .config import RuntimeConfig
from .database import connect


class CashRuntimeError(ValueError):
    pass


_ENTRY_TYPES = {
    "cash_sale",
    "cash_receipt",
    "service_cash_receipt",
    "other_cash_in",
    "upi_receipt",
    "card_receipt",
    "bank_receipt",
    "service_noncash_receipt",
    "expense_cash",
    "expense_noncash",
    "allocation_cash",
    "deposit_cash",
    "transfer_cash_out",
    "bank_transfer_out",
}

_CHANNELS = {"cash", "upi", "card", "bank", "other"}
_EXPENSE_ROLES = {
    "direct_selling_cost",
    "branch_operating_expense",
    "central_overhead",
    "finance_cost",
    "non_operating",
    "capital_movement",
    "internal_transfer",
    "unknown",
}
_CONFIDENCE = {"exact", "strong", "weak", "unknown"}


def _stable_id(prefix: str, enterprise_id: str, key: str) -> str:
    return f"{prefix}-{sha256(f'{enterprise_id}|{key}'.encode()).hexdigest()[:24]}"


def _require_cash(membership: Mapping[str, Any]) -> None:
    capabilities = {str(x).upper() for x in membership.get("capabilities") or []}
    if "CASH" not in capabilities:
        raise PermissionError("CASH capability required")


def _active_user(conn, enterprise_id: str, principal_id: str) -> str:
    row = conn.execute(
        "select user_id from users where enterprise_id=%s and principal_id=%s and active=true",
        (enterprise_id, principal_id),
    ).fetchone()
    if not row:
        raise CashRuntimeError("authenticated principal has no active ECHO user")
    return str(row[0])


def _branch(conn, enterprise_id: str, branch_code: str) -> str:
    row = conn.execute(
        "select branch_id from branches where enterprise_id=%s and code=%s and active=true",
        (enterprise_id, branch_code.upper()),
    ).fetchone()
    if not row:
        raise CashRuntimeError("active branch not found for enterprise")
    return str(row[0])


def _amount(value: Any, name: str, *, allow_zero: bool = False) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise CashRuntimeError(f"{name} must be numeric") from exc
    if amount < 0 or (amount == 0 and not allow_zero):
        raise CashRuntimeError(f"{name} must be {'non-negative' if allow_zero else 'positive'}")
    return amount


def _session_summary(conn, enterprise_id: str, session_id: str) -> dict[str, Any]:
    row = conn.execute(
        """
        select s.session_id,b.code,s.business_date,s.opening_cash,s.declared_closing,s.status,
               r.cash_in,r.cash_out,r.noncash_in,r.noncash_out,r.expected_closing,r.variance,r.entry_count,
               s.created_at,s.submitted_at,s.approved_at
        from cash_day_sessions s
        join branches b on b.branch_id=s.branch_id
        join cash_day_session_review r on r.session_id=s.session_id
        where s.enterprise_id=%s and s.session_id=%s
        """,
        (enterprise_id, session_id),
    ).fetchone()
    if not row:
        raise CashRuntimeError("cash day session not found")
    return {
        "session_id": str(row[0]),
        "branch_code": str(row[1]),
        "business_date": row[2].isoformat(),
        "opening_cash": str(row[3]),
        "declared_closing": None if row[4] is None else str(row[4]),
        "status": str(row[5]),
        "cash_in": str(row[6]),
        "cash_out": str(row[7]),
        "noncash_in": str(row[8]),
        "noncash_out": str(row[9]),
        "expected_closing": str(row[10]),
        "variance": None if row[11] is None else str(row[11]),
        "entry_count": int(row[12]),
        "created_at": row[13].isoformat(),
        "submitted_at": None if row[14] is None else row[14].isoformat(),
        "approved_at": None if row[15] is None else row[15].isoformat(),
    }


def open_cash_day(
    config: RuntimeConfig,
    *,
    principal_id: str,
    membership: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    _require_cash(membership)
    enterprise_id = str(membership.get("enterprise_id") or "")
    branch_code = str(payload.get("branch_code") or "").strip().upper()
    business_date_raw = str(payload.get("business_date") or "").strip()
    idempotency_key = str(payload.get("idempotency_key") or "").strip()
    note = str(payload.get("note") or "").strip()
    if not enterprise_id or not branch_code or not business_date_raw or not idempotency_key:
        raise CashRuntimeError("branch_code, business_date and idempotency_key are required")
    try:
        business_date = date.fromisoformat(business_date_raw)
    except ValueError as exc:
        raise CashRuntimeError("business_date must be ISO date") from exc
    opening_cash = _amount(payload.get("opening_cash", 0), "opening_cash", allow_zero=True)
    session_id = _stable_id("echo-cash-day", enterprise_id, idempotency_key)
    now = datetime.now(timezone.utc)

    with connect(config) as conn:
        with conn.transaction():
            user_id = _active_user(conn, enterprise_id, principal_id)
            branch_id = _branch(conn, enterprise_id, branch_code)
            existing = conn.execute(
                "select branch_id,business_date,opening_cash from cash_day_sessions where enterprise_id=%s and session_id=%s",
                (enterprise_id, session_id),
            ).fetchone()
            if existing:
                if str(existing[0]) != branch_id or existing[1] != business_date or Decimal(str(existing[2])) != opening_cash:
                    raise CashRuntimeError("idempotency_key was reused with changed cash-day payload")
                result = _session_summary(conn, enterprise_id, session_id)
                result["idempotent_replay"] = True
                return result
            active = conn.execute(
                """
                select session_id from cash_day_sessions
                where enterprise_id=%s and branch_id=%s and business_date=%s
                  and status in ('draft','submitted','approved')
                """,
                (enterprise_id, branch_id, business_date),
            ).fetchone()
            if active:
                raise CashRuntimeError("an active cash day already exists for this branch/date")
            conn.execute(
                """
                insert into cash_day_sessions(
                  session_id,enterprise_id,branch_id,business_date,opening_cash,declared_closing,status,
                  created_at,created_by,submitted_at,submitted_by,approved_at,approved_by,supersedes_session_id,note
                ) values(%s,%s,%s,%s,%s,null,'draft',%s,%s,null,null,null,null,null,%s)
                """,
                (session_id, enterprise_id, branch_id, business_date, opening_cash, now, user_id, note),
            )
            result = _session_summary(conn, enterprise_id, session_id)
            result["idempotent_replay"] = False
            return result


def record_cash_entry(
    config: RuntimeConfig,
    *,
    principal_id: str,
    membership: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    _require_cash(membership)
    enterprise_id = str(membership.get("enterprise_id") or "")
    session_id = str(payload.get("session_id") or "").strip()
    entry_type = str(payload.get("entry_type") or "").strip()
    channel = str(payload.get("channel") or "other").strip().lower()
    key = str(payload.get("idempotency_key") or "").strip()
    if not enterprise_id or not session_id or not key:
        raise CashRuntimeError("session_id and idempotency_key are required")
    if entry_type not in _ENTRY_TYPES:
        raise CashRuntimeError("entry_type is not admitted")
    if channel not in _CHANNELS:
        raise CashRuntimeError("channel is not admitted")
    amount = _amount(payload.get("amount"), "amount")

    category_raw = str(payload.get("classification_category") or "").strip()
    role = str(payload.get("classification_role") or "unknown").strip().lower()
    confidence = str(payload.get("classification_confidence") or "unknown").strip().lower()
    if role not in _EXPENSE_ROLES or confidence not in _CONFIDENCE:
        raise CashRuntimeError("invalid explicit financial classification")
    if role != "unknown" and (not category_raw or confidence == "unknown"):
        raise CashRuntimeError("classified expense evidence requires category and non-unknown confidence")
    if role == "unknown" and (category_raw or confidence != "unknown"):
        raise CashRuntimeError("partial financial classification is not admitted")
    if not entry_type.startswith("expense_") and role != "unknown":
        raise CashRuntimeError("financial expense classification is admitted only for expense entries")

    entry_id = _stable_id("echo-cash-entry", enterprise_id, key)
    reference = str(payload.get("reference") or "").strip()
    evidence_ref = str(payload.get("evidence_ref") or "").strip()
    note = str(payload.get("note") or "").strip()
    now = datetime.now(timezone.utc)

    with connect(config) as conn:
        with conn.transaction():
            user_id = _active_user(conn, enterprise_id, principal_id)
            session = conn.execute(
                "select branch_id,business_date,status from cash_day_sessions where enterprise_id=%s and session_id=%s",
                (enterprise_id, session_id),
            ).fetchone()
            if not session:
                raise CashRuntimeError("cash day session not found")
            if str(session[2]) != "draft":
                raise CashRuntimeError("cash entries can only be added to a draft day")
            existing = conn.execute(
                """
                select session_id,entry_type,channel,amount,classification_category,classification_role,classification_confidence
                from cash_entry_evidence where enterprise_id=%s and idempotency_key=%s
                """,
                (enterprise_id, key),
            ).fetchone()
            if existing:
                stable_existing = (
                    str(existing[0]), str(existing[1]), str(existing[2]), Decimal(str(existing[3])),
                    str(existing[4] or ""), str(existing[5]), str(existing[6]),
                )
                stable_requested = (session_id, entry_type, channel, amount, category_raw, role, confidence)
                if stable_existing != stable_requested:
                    raise CashRuntimeError("idempotency_key was reused with changed cash-entry payload")
                return {
                    "entry_id": entry_id,
                    "session": _session_summary(conn, enterprise_id, session_id),
                    "idempotent_replay": True,
                }
            conn.execute(
                """
                insert into cash_entry_evidence(
                  entry_id,session_id,enterprise_id,branch_id,business_date,entry_type,channel,amount,
                  reference,evidence_ref,note,occurred_at,actor_id,idempotency_key,
                  classification_category,classification_role,classification_confidence
                ) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    entry_id, session_id, enterprise_id, str(session[0]), session[1], entry_type, channel, amount,
                    reference, evidence_ref, note, now, user_id, key,
                    category_raw or None, role, confidence,
                ),
            )
            return {
                "entry_id": entry_id,
                "session": _session_summary(conn, enterprise_id, session_id),
                "idempotent_replay": False,
            }


def submit_cash_day(
    config: RuntimeConfig,
    *,
    principal_id: str,
    membership: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    _require_cash(membership)
    enterprise_id = str(membership.get("enterprise_id") or "")
    session_id = str(payload.get("session_id") or "").strip()
    if not enterprise_id or not session_id:
        raise CashRuntimeError("session_id is required")
    declared = _amount(payload.get("declared_closing"), "declared_closing", allow_zero=True)
    now = datetime.now(timezone.utc)

    with connect(config) as conn:
        with conn.transaction():
            user_id = _active_user(conn, enterprise_id, principal_id)
            row = conn.execute(
                "select status,declared_closing from cash_day_sessions where enterprise_id=%s and session_id=%s for update",
                (enterprise_id, session_id),
            ).fetchone()
            if not row:
                raise CashRuntimeError("cash day session not found")
            status = str(row[0])
            if status == "submitted":
                if row[1] is None or Decimal(str(row[1])) != declared:
                    raise CashRuntimeError("submitted cash day cannot be changed")
                result = _session_summary(conn, enterprise_id, session_id)
                result["idempotent_replay"] = True
                return result
            if status != "draft":
                raise CashRuntimeError("only a draft cash day can be submitted")
            conn.execute(
                """
                update cash_day_sessions
                set declared_closing=%s,status='submitted',submitted_at=%s,submitted_by=%s
                where enterprise_id=%s and session_id=%s
                """,
                (declared, now, user_id, enterprise_id, session_id),
            )
            result = _session_summary(conn, enterprise_id, session_id)
            result["idempotent_replay"] = False
            return result


def cash_day_readback(
    config: RuntimeConfig,
    *,
    enterprise_id: str,
    branch_code: str | None = None,
    business_date: str | None = None,
    limit: int = 14,
) -> dict[str, Any]:
    branch_code = str(branch_code or "").strip().upper() or None
    day = None
    if business_date:
        try:
            day = date.fromisoformat(str(business_date))
        except ValueError as exc:
            raise CashRuntimeError("business_date must be ISO date") from exc
    try:
        limit = max(1, min(int(limit), 60))
    except (TypeError, ValueError) as exc:
        raise CashRuntimeError("limit must be numeric") from exc

    params: list[Any] = [enterprise_id]
    where = ["s.enterprise_id=%s"]
    if branch_code:
        where.append("b.code=%s")
        params.append(branch_code)
    if day:
        where.append("s.business_date=%s")
        params.append(day)
    params.append(limit)

    with connect(config) as conn:
        rows = conn.execute(
            f"""
            select s.session_id
            from cash_day_sessions s join branches b on b.branch_id=s.branch_id
            where {' and '.join(where)}
            order by s.business_date desc,s.created_at desc
            limit %s
            """,
            tuple(params),
        ).fetchall()
        sessions = [_session_summary(conn, enterprise_id, str(row[0])) for row in rows]
        entries: list[dict[str, Any]] = []
        for session in sessions:
            for row in conn.execute(
                """
                select entry_id,entry_type,channel,amount,reference,evidence_ref,note,occurred_at,
                       classification_category,classification_role,classification_confidence
                from cash_entry_evidence
                where enterprise_id=%s and session_id=%s
                order by occurred_at,entry_id
                """,
                (enterprise_id, session["session_id"]),
            ).fetchall():
                entries.append({
                    "entry_id": str(row[0]),
                    "session_id": session["session_id"],
                    "entry_type": str(row[1]),
                    "channel": str(row[2]),
                    "amount": str(row[3]),
                    "reference": str(row[4] or ""),
                    "evidence_ref": str(row[5] or ""),
                    "note": str(row[6] or ""),
                    "occurred_at": row[7].isoformat(),
                    "classification_category": row[8],
                    "classification_role": str(row[9]),
                    "classification_confidence": str(row[10]),
                })
    return {"sessions": sessions, "entries": entries}
