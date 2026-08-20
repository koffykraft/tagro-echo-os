from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import json
from typing import Any, Mapping
from uuid import uuid4

from src.repository.ports import RepositoryPort


def money(value: Any) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class CashEngineError(ValueError):
    pass


CASH_AFFECTING_IN = {"cash_sale", "cash_receipt", "service_cash_receipt", "other_cash_in"}
CASH_AFFECTING_OUT = {"expense_cash", "deposit_cash", "transfer_cash_out", "allocation_cash"}
NONCASH_IN = {"upi_receipt", "card_receipt", "bank_receipt", "service_noncash_receipt"}
NONCASH_OUT = {"expense_noncash", "bank_transfer_out"}
VALID_ENTRY_TYPES = CASH_AFFECTING_IN | CASH_AFFECTING_OUT | NONCASH_IN | NONCASH_OUT


@dataclass(frozen=True)
class CashEntry:
    entry_id: str
    closing_id: str
    enterprise_id: str
    business_date: date
    entry_type: str
    amount: Decimal
    actor_id: str
    occurred_at: datetime
    idempotency_key: str
    channel: str = "cash"
    reference_type: str | None = None
    reference_id: str | None = None
    evidence_ref: str | None = None
    note: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DailyClosing:
    closing_id: str
    enterprise_id: str
    business_date: date
    opening_cash: Decimal
    declared_closing_cash: Decimal | None = None
    status: str = "draft"
    created_by: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    submitted_by: str | None = None
    submitted_at: datetime | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    supersedes_closing_id: str | None = None
    note: str = ""


@dataclass(frozen=True)
class ClosingSummary:
    closing_id: str
    enterprise_id: str
    business_date: date
    status: str
    opening_cash: Decimal
    cash_in: Decimal
    cash_out: Decimal
    noncash_in: Decimal
    noncash_out: Decimal
    expected_physical_cash: Decimal
    declared_closing_cash: Decimal | None
    variance: Decimal | None
    entries_count: int


class ClosingCashEngine:
    CLOSINGS = "closing_cash.closings"
    ENTRIES = "closing_cash.entries"
    IDEMPOTENCY = "closing_cash.idempotency"
    AUDIT = "closing_cash.audit"

    def __init__(self, repository: RepositoryPort):
        self.repository = repository

    def open_day(self, enterprise_id: str, business_date: date, opening_cash: Any, actor_id: str, note: str = "") -> DailyClosing:
        if not enterprise_id.strip() or not actor_id.strip():
            raise CashEngineError("enterprise_id and actor_id are required")
        opening = money(opening_cash)
        if opening < 0:
            raise CashEngineError("opening cash cannot be negative")
        for row in self.repository.list(self.CLOSINGS):
            if row.get("enterprise_id") == enterprise_id and row.get("business_date") == business_date.isoformat() and row.get("status") in {"draft", "submitted", "approved"}:
                raise CashEngineError("active closing already exists for enterprise and business date")
        closing = DailyClosing(
            closing_id=f"close-{uuid4().hex[:12]}", enterprise_id=enterprise_id,
            business_date=business_date, opening_cash=opening, created_by=actor_id, note=note,
        )
        self._put_closing(closing)
        self._audit(closing.closing_id, actor_id, "opened", {"opening_cash": str(opening)})
        return closing

    def add_entry(self, entry: CashEntry) -> CashEntry:
        if entry.entry_type not in VALID_ENTRY_TYPES:
            raise CashEngineError(f"unsupported cash entry type: {entry.entry_type}")
        if entry.amount <= 0:
            raise CashEngineError("entry amount must be positive")
        if not entry.actor_id.strip() or not entry.idempotency_key.strip():
            raise CashEngineError("actor_id and idempotency_key are required")
        closing = self.get_closing(entry.closing_id)
        if not closing:
            raise CashEngineError("closing does not exist")
        if closing.enterprise_id != entry.enterprise_id or closing.business_date != entry.business_date:
            raise CashEngineError("entry enterprise/date does not match closing")
        if closing.status != "draft":
            raise CashEngineError("entries may only be added while closing is draft")
        payload = self._entry_payload(entry)
        payload_hash = sha256(json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()
        existing = self.repository.get(self.IDEMPOTENCY, entry.idempotency_key)
        if existing:
            if existing.get("payload_hash") != payload_hash:
                raise CashEngineError("idempotency key replayed with changed cash entry")
            existing_entry = self.repository.get(self.ENTRIES, existing["entry_id"])
            return self._entry_from(existing_entry)
        self.repository.put(self.ENTRIES, entry.entry_id, payload)
        self.repository.put(self.IDEMPOTENCY, entry.idempotency_key, {"entry_id": entry.entry_id, "payload_hash": payload_hash})
        self._audit(entry.closing_id, entry.actor_id, "entry_added", {"entry_id": entry.entry_id, "entry_type": entry.entry_type, "amount": str(entry.amount)})
        return entry

    def new_entry(self, closing_id: str, entry_type: str, amount: Any, actor_id: str, idempotency_key: str, *, channel: str = "cash", reference_type: str | None = None, reference_id: str | None = None, evidence_ref: str | None = None, note: str = "", metadata: Mapping[str, Any] | None = None) -> CashEntry:
        closing = self.get_closing(closing_id)
        if not closing:
            raise CashEngineError("closing does not exist")
        return CashEntry(
            entry_id=f"cash-{uuid4().hex[:12]}", closing_id=closing_id,
            enterprise_id=closing.enterprise_id, business_date=closing.business_date,
            entry_type=entry_type, amount=money(amount), actor_id=actor_id,
            occurred_at=datetime.now(timezone.utc), idempotency_key=idempotency_key,
            channel=channel, reference_type=reference_type, reference_id=reference_id,
            evidence_ref=evidence_ref, note=note, metadata=metadata or {},
        )

    def declare_closing(self, closing_id: str, declared_cash: Any, actor_id: str) -> DailyClosing:
        closing = self._require_draft(closing_id)
        declared = money(declared_cash)
        if declared < 0:
            raise CashEngineError("declared cash cannot be negative")
        updated = DailyClosing(**{**asdict(closing), "declared_closing_cash": declared})
        self._put_closing(updated)
        self._audit(closing_id, actor_id, "declared", {"declared_closing_cash": str(declared)})
        return updated

    def submit(self, closing_id: str, actor_id: str) -> DailyClosing:
        closing = self._require_draft(closing_id)
        if closing.declared_closing_cash is None:
            raise CashEngineError("declared closing cash is required before submission")
        now = datetime.now(timezone.utc)
        updated = DailyClosing(**{**asdict(closing), "status": "submitted", "submitted_by": actor_id, "submitted_at": now})
        self._put_closing(updated)
        self._audit(closing_id, actor_id, "submitted", {"variance": str(self.summary(closing_id).variance)})
        return updated

    def approve(self, closing_id: str, actor_id: str) -> DailyClosing:
        closing = self.get_closing(closing_id)
        if not closing or closing.status != "submitted":
            raise CashEngineError("only submitted closing may be approved")
        now = datetime.now(timezone.utc)
        updated = DailyClosing(**{**asdict(closing), "status": "approved", "approved_by": actor_id, "approved_at": now})
        self._put_closing(updated)
        self._audit(closing_id, actor_id, "approved", {})
        return updated

    def supersede(self, closing_id: str, actor_id: str, opening_cash: Any | None = None, note: str = "") -> DailyClosing:
        old = self.get_closing(closing_id)
        if not old or old.status not in {"submitted", "approved"}:
            raise CashEngineError("only submitted or approved closing may be superseded")
        old_updated = DailyClosing(**{**asdict(old), "status": "superseded"})
        self._put_closing(old_updated)
        new = DailyClosing(
            closing_id=f"close-{uuid4().hex[:12]}", enterprise_id=old.enterprise_id,
            business_date=old.business_date,
            opening_cash=money(opening_cash if opening_cash is not None else old.opening_cash),
            created_by=actor_id, supersedes_closing_id=old.closing_id, note=note,
        )
        self._put_closing(new)
        self._audit(old.closing_id, actor_id, "superseded", {"replacement_closing_id": new.closing_id})
        return new

    def summary(self, closing_id: str) -> ClosingSummary:
        closing = self.get_closing(closing_id)
        if not closing:
            raise CashEngineError("closing does not exist")
        entries = self.entries(closing_id)
        cash_in = sum((e.amount for e in entries if e.entry_type in CASH_AFFECTING_IN), Decimal("0"))
        cash_out = sum((e.amount for e in entries if e.entry_type in CASH_AFFECTING_OUT), Decimal("0"))
        noncash_in = sum((e.amount for e in entries if e.entry_type in NONCASH_IN), Decimal("0"))
        noncash_out = sum((e.amount for e in entries if e.entry_type in NONCASH_OUT), Decimal("0"))
        expected = money(closing.opening_cash + cash_in - cash_out)
        declared = closing.declared_closing_cash
        variance = money(declared - expected) if declared is not None else None
        return ClosingSummary(
            closing.closing_id, closing.enterprise_id, closing.business_date, closing.status,
            money(closing.opening_cash), money(cash_in), money(cash_out), money(noncash_in), money(noncash_out),
            expected, declared, variance, len(entries),
        )

    def entries(self, closing_id: str) -> list[CashEntry]:
        return [self._entry_from(r) for r in self.repository.list(self.ENTRIES) if r.get("closing_id") == closing_id]

    def get_closing(self, closing_id: str) -> DailyClosing | None:
        row = self.repository.get(self.CLOSINGS, closing_id)
        return self._closing_from(row) if row else None

    def audit(self, closing_id: str) -> list[Mapping[str, Any]]:
        return [r for r in self.repository.list(self.AUDIT) if r.get("closing_id") == closing_id]

    def _require_draft(self, closing_id: str) -> DailyClosing:
        closing = self.get_closing(closing_id)
        if not closing or closing.status != "draft":
            raise CashEngineError("closing must be draft")
        return closing

    def _put_closing(self, closing: DailyClosing) -> None:
        row = asdict(closing)
        row["business_date"] = closing.business_date.isoformat()
        for key in ("created_at", "submitted_at", "approved_at"):
            value = row.get(key)
            row[key] = value.isoformat() if value else None
        for key in ("opening_cash", "declared_closing_cash"):
            if row.get(key) is not None:
                row[key] = str(row[key])
        self.repository.put(self.CLOSINGS, closing.closing_id, row)

    def _audit(self, closing_id: str, actor_id: str, event: str, details: Mapping[str, Any]) -> None:
        audit_id = f"cash-audit-{uuid4().hex[:12]}"
        self.repository.put(self.AUDIT, audit_id, {
            "audit_id": audit_id, "closing_id": closing_id, "actor_id": actor_id,
            "event": event, "at": datetime.now(timezone.utc).isoformat(), "details": dict(details),
        })

    @staticmethod
    def _entry_payload(entry: CashEntry) -> dict[str, Any]:
        row = asdict(entry)
        row["business_date"] = entry.business_date.isoformat()
        row["occurred_at"] = entry.occurred_at.isoformat()
        row["amount"] = str(entry.amount)
        return row

    @staticmethod
    def _entry_from(row: Mapping[str, Any]) -> CashEntry:
        data = dict(row)
        data["business_date"] = date.fromisoformat(data["business_date"])
        data["occurred_at"] = datetime.fromisoformat(data["occurred_at"])
        data["amount"] = money(data["amount"])
        return CashEntry(**data)

    @staticmethod
    def _closing_from(row: Mapping[str, Any]) -> DailyClosing:
        data = dict(row)
        data["business_date"] = date.fromisoformat(data["business_date"])
        for key in ("created_at", "submitted_at", "approved_at"):
            data[key] = datetime.fromisoformat(data[key]) if data.get(key) else None
        data["opening_cash"] = money(data["opening_cash"])
        if data.get("declared_closing_cash") is not None:
            data["declared_closing_cash"] = money(data["declared_closing_cash"])
        return DailyClosing(**data)
