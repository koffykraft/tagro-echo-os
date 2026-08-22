from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .engine import BillingError, BusyBookingHandoff


@dataclass(frozen=True)
class BusyHandoffReceipt:
    """Evidence about a BUSY booking handoff; never a booking command.

    The ECHO bill remains operational truth. A handoff is not considered booked
    until deterministic BUSY-side evidence confirms the same payload hash and a
    non-empty external voucher reference. Rejection is retained explicitly.
    """

    handoff_id: str
    bill_id: str
    payload_hash: str
    state: str
    recorded_at: str
    busy_voucher_ref: str | None = None
    evidence_ref: str | None = None
    reason: str = ""


class BusyBillingReconciler:
    STATES = {
        "queued_not_booked",
        "submitted_not_confirmed",
        "booked_confirmed",
        "rejected",
    }

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def queued(self, handoff: BusyBookingHandoff) -> BusyHandoffReceipt:
        if handoff.status != "queued_not_booked":
            raise BillingError("handoff must begin as queued_not_booked")
        return BusyHandoffReceipt(
            handoff_id=handoff.handoff_id,
            bill_id=handoff.bill_id,
            payload_hash=handoff.payload_hash,
            state="queued_not_booked",
            recorded_at=self._now(),
        )

    def submitted(
        self,
        handoff: BusyBookingHandoff,
        *,
        submitted_payload_hash: str,
        evidence_ref: str,
    ) -> BusyHandoffReceipt:
        if submitted_payload_hash != handoff.payload_hash:
            raise BillingError("BUSY submission payload hash does not match prepared handoff")
        if not evidence_ref.strip():
            raise BillingError("BUSY submission requires transport evidence_ref")
        return BusyHandoffReceipt(
            handoff_id=handoff.handoff_id,
            bill_id=handoff.bill_id,
            payload_hash=handoff.payload_hash,
            state="submitted_not_confirmed",
            recorded_at=self._now(),
            evidence_ref=evidence_ref.strip(),
        )

    def confirm_booked(
        self,
        handoff: BusyBookingHandoff,
        *,
        confirmed_payload_hash: str,
        busy_voucher_ref: str,
        evidence_ref: str,
    ) -> BusyHandoffReceipt:
        if confirmed_payload_hash != handoff.payload_hash:
            raise BillingError("BUSY confirmation payload hash does not match prepared handoff")
        if not busy_voucher_ref.strip():
            raise BillingError("BUSY booking confirmation requires external voucher reference")
        if not evidence_ref.strip():
            raise BillingError("BUSY booking confirmation requires evidence_ref")
        return BusyHandoffReceipt(
            handoff_id=handoff.handoff_id,
            bill_id=handoff.bill_id,
            payload_hash=handoff.payload_hash,
            state="booked_confirmed",
            recorded_at=self._now(),
            busy_voucher_ref=busy_voucher_ref.strip(),
            evidence_ref=evidence_ref.strip(),
        )

    def reject(
        self,
        handoff: BusyBookingHandoff,
        *,
        reason: str,
        evidence_ref: str,
    ) -> BusyHandoffReceipt:
        if not reason.strip():
            raise BillingError("BUSY rejection requires an explicit reason")
        if not evidence_ref.strip():
            raise BillingError("BUSY rejection requires evidence_ref")
        return BusyHandoffReceipt(
            handoff_id=handoff.handoff_id,
            bill_id=handoff.bill_id,
            payload_hash=handoff.payload_hash,
            state="rejected",
            recorded_at=self._now(),
            evidence_ref=evidence_ref.strip(),
            reason=reason.strip(),
        )
