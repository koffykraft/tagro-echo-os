from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from typing import Any, Mapping

from .config import RuntimeConfig
from .database import connect


class OperationalRuntimeError(ValueError):
    pass


def _stable_id(prefix: str, enterprise_id: str, key: str) -> str:
    return f"{prefix}-{sha256(f'{enterprise_id}|{key}'.encode()).hexdigest()[:24]}"


def _capability(membership: Mapping[str, Any], required: str) -> None:
    caps = {str(x).upper() for x in membership.get("capabilities") or []}
    if required.upper() not in caps:
        raise PermissionError(f"{required.upper()} capability required")


def _identity(conn, enterprise_id: str, principal_id: str, branch_code: str):
    user = conn.execute(
        "select user_id from users where enterprise_id=%s and principal_id=%s and active=true",
        (enterprise_id, principal_id),
    ).fetchone()
    if not user:
        raise OperationalRuntimeError("authenticated principal has no active ECHO user")
    branch = conn.execute(
        "select branch_id from branches where enterprise_id=%s and code=%s and active=true",
        (enterprise_id, branch_code.upper()),
    ).fetchone()
    if not branch:
        raise OperationalRuntimeError("active branch not found for enterprise")
    return str(user[0]), str(branch[0])


def create_service_intake(config: RuntimeConfig, *, principal_id: str, membership: Mapping[str, Any], payload: Mapping[str, Any]) -> dict[str, Any]:
    _capability(membership, "SERVICE")
    enterprise_id = str(membership.get("enterprise_id") or "")
    branch_code = str(payload.get("branch_code") or "").strip().upper()
    customer_id = str(payload.get("customer_id") or "").strip()
    model = str(payload.get("model") or "").strip()
    serial = str(payload.get("serial_no") or "").strip()
    complaint = str(payload.get("complaint") or "").strip()
    product_id = str(payload.get("product_id") or "").strip() or None
    key = str(payload.get("idempotency_key") or "").strip()
    if not all((enterprise_id, branch_code, customer_id, model, complaint, key)):
        raise OperationalRuntimeError("branch, customer, model, complaint and idempotency_key are required")
    job_id = _stable_id("echo-job", enterprise_id, key)
    event_id = _stable_id("echo-service-event", enterprise_id, key)
    machine_id = _stable_id("echo-machine", enterprise_id, f"{customer_id}|{serial or model}")
    now = datetime.now(timezone.utc)
    with connect(config) as conn:
        with conn.transaction():
            user_id, branch_id = _identity(conn, enterprise_id, principal_id, branch_code)
            existing = conn.execute("select status,opened_at from service_jobs where enterprise_id=%s and job_id=%s", (enterprise_id, job_id)).fetchone()
            if existing:
                return {"job_id": job_id, "status": existing[0], "opened_at": existing[1].isoformat(), "idempotent_replay": True}
            if not conn.execute("select 1 from customers where enterprise_id=%s and customer_id=%s", (enterprise_id, customer_id)).fetchone():
                raise OperationalRuntimeError("customer does not belong to enterprise")
            if product_id and not conn.execute("select 1 from products where enterprise_id=%s and product_id=%s and active=true", (enterprise_id, product_id)).fetchone():
                raise OperationalRuntimeError("product does not belong to enterprise")
            machine = None
            if serial:
                machine = conn.execute("select machine_id from machines where enterprise_id=%s and customer_id=%s and serial_no=%s", (enterprise_id, customer_id, serial)).fetchone()
            if machine:
                machine_id = str(machine[0])
            else:
                conn.execute(
                    "insert into machines(machine_id,enterprise_id,customer_id,product_id,model,serial_no,purchase_date,source) values(%s,%s,%s,%s,%s,%s,null,'staff_confirmed_runtime') on conflict(machine_id) do nothing",
                    (machine_id, enterprise_id, customer_id, product_id, model, serial),
                )
            conn.execute(
                "insert into service_jobs(job_id,enterprise_id,branch_id,customer_id,machine_id,opened_at,complaint,status,observations,estimate_id) values(%s,%s,%s,%s,%s,%s,%s,'received','',null)",
                (job_id, enterprise_id, branch_id, customer_id, machine_id, now, complaint),
            )
            conn.execute(
                "insert into service_events(event_id,enterprise_id,job_id,occurred_at,event_type,note,actor_id) values(%s,%s,%s,%s,'received',%s,%s)",
                (event_id, enterprise_id, job_id, now, complaint, user_id),
            )
    return {"job_id": job_id, "machine_id": machine_id, "status": "received", "opened_at": now.isoformat(), "idempotent_replay": False}


def create_purchase_order(config: RuntimeConfig, *, principal_id: str, membership: Mapping[str, Any], payload: Mapping[str, Any]) -> dict[str, Any]:
    _capability(membership, "PURCHASE_ORDER")
    enterprise_id = str(membership.get("enterprise_id") or "")
    branch_code = str(payload.get("branch_code") or "").strip().upper()
    supplier_id = str(payload.get("supplier_id") or "").strip()
    lines = payload.get("lines")
    key = str(payload.get("idempotency_key") or "").strip()
    if not branch_code or not supplier_id or not key or not isinstance(lines, list) or not lines:
        raise OperationalRuntimeError("branch, supplier, idempotency_key and lines are required")
    po_id = _stable_id("echo-po", enterprise_id, key)
    now = datetime.now(timezone.utc)
    with connect(config) as conn:
        with conn.transaction():
            user_id, branch_id = _identity(conn, enterprise_id, principal_id, branch_code)
            existing = conn.execute("select status,created_at from purchase_orders where enterprise_id=%s and po_id=%s", (enterprise_id, po_id)).fetchone()
            if existing:
                return {"po_id": po_id, "status": existing[0], "created_at": existing[1].isoformat(), "idempotent_replay": True}
            if not conn.execute("select 1 from suppliers where enterprise_id=%s and supplier_id=%s", (enterprise_id, supplier_id)).fetchone():
                raise OperationalRuntimeError("supplier does not belong to enterprise")
            normalized = []
            for i, raw in enumerate(lines, 1):
                product_id = str(raw.get("product_id") or "").strip() if isinstance(raw, Mapping) else ""
                qty = Decimal(str(raw.get("quantity") or 0)) if isinstance(raw, Mapping) else Decimal("0")
                unit_price = raw.get("unit_price") if isinstance(raw, Mapping) else None
                note = str(raw.get("note") or "") if isinstance(raw, Mapping) else ""
                if not product_id or qty <= 0:
                    raise OperationalRuntimeError(f"invalid PO line {i}")
                if not conn.execute("select 1 from products where enterprise_id=%s and product_id=%s and active=true", (enterprise_id, product_id)).fetchone():
                    raise OperationalRuntimeError(f"product {product_id} does not belong to enterprise")
                normalized.append((product_id, qty, Decimal(str(unit_price)) if unit_price not in (None, "") else None, note))
            conn.execute("insert into purchase_orders(po_id,enterprise_id,branch_id,supplier_id,created_at,status,created_by) values(%s,%s,%s,%s,%s,'draft',%s)", (po_id, enterprise_id, branch_id, supplier_id, now, user_id))
            for line_no, (product_id, qty, unit_price, note) in enumerate(normalized, 1):
                conn.execute("insert into purchase_order_lines(po_id,line_no,product_id,quantity,unit_price,note) values(%s,%s,%s,%s,%s,%s)", (po_id, line_no, product_id, qty, unit_price, note))
    return {"po_id": po_id, "status": "draft", "created_at": now.isoformat(), "idempotent_replay": False}


def record_stock_count(config: RuntimeConfig, *, principal_id: str, membership: Mapping[str, Any], payload: Mapping[str, Any]) -> dict[str, Any]:
    _capability(membership, "STOCK_COUNT")
    enterprise_id = str(membership.get("enterprise_id") or "")
    branch_code = str(payload.get("branch_code") or "").strip().upper()
    product_id = str(payload.get("product_id") or "").strip()
    raw_count = payload.get("counted_qty")
    try:
        counted_qty = Decimal(str(raw_count))
    except Exception as exc:
        raise OperationalRuntimeError("counted_qty must be numeric") from exc
    session_key = str(payload.get("count_session_key") or "").strip()
    key = str(payload.get("idempotency_key") or "").strip()
    evidence_ids = list(payload.get("evidence_ids") or [])
    raw_item_ref = str(payload.get("raw_item_ref") or product_id).strip()
    location_note = str(payload.get("location_note") or "").strip()
    if not branch_code or not product_id or not session_key or not key or counted_qty < 0:
        raise OperationalRuntimeError("branch, product, non-negative count, count_session_key and idempotency_key are required")

    count_id = _stable_id("echo-count", enterprise_id, session_key)
    observation_id = _stable_id("echo-stock-observation", enterprise_id, key)
    now = datetime.now(timezone.utc)
    with connect(config) as conn:
        with conn.transaction():
            user_id, branch_id = _identity(conn, enterprise_id, principal_id, branch_code)
            if not conn.execute("select 1 from products where enterprise_id=%s and product_id=%s and active=true", (enterprise_id, product_id)).fetchone():
                raise OperationalRuntimeError("product does not belong to enterprise")

            existing_observation = conn.execute(
                "select branch_id,product_id,counted_qty,count_id,canonical_system_qty,variance_to_canonical from stock_count_observations where enterprise_id=%s and observation_id=%s",
                (enterprise_id, observation_id),
            ).fetchone()
            if existing_observation:
                if (
                    str(existing_observation[0]) != branch_id
                    or str(existing_observation[1]) != product_id
                    or Decimal(str(existing_observation[2])) != counted_qty
                    or str(existing_observation[3]) != count_id
                ):
                    raise OperationalRuntimeError("idempotency_key was reused with changed stock count payload")
                stored_system_qty = Decimal(str(existing_observation[4])) if existing_observation[4] is not None else None
                stored_variance = Decimal(str(existing_observation[5])) if existing_observation[5] is not None else None
                provisional = conn.execute(
                    "select quantity from provisional_stock_position where enterprise_id=%s and branch_id=%s and product_id=%s",
                    (enterprise_id, branch_id, product_id),
                ).fetchone()
                return {
                    "count_id": count_id,
                    "observation_id": observation_id,
                    "product_id": product_id,
                    "system_qty": str(stored_system_qty) if stored_system_qty is not None else None,
                    "system_qty_known": stored_system_qty is not None,
                    "counted_qty": str(counted_qty),
                    "variance": str(stored_variance) if stored_variance is not None else None,
                    "provisional_qty": str(provisional[0]) if provisional else str(counted_qty),
                    "provisional_truth_state": "provisional_count",
                    "stock_mutated": False,
                    "status": "open",
                    "idempotent_replay": True,
                }

            count = conn.execute("select branch_id,status from stock_counts where enterprise_id=%s and count_id=%s", (enterprise_id, count_id)).fetchone()
            if count and (str(count[0]) != branch_id or str(count[1]) != "open"):
                raise OperationalRuntimeError("stock count session is not open for this branch")
            if not count:
                conn.execute("insert into stock_counts(count_id,enterprise_id,branch_id,created_by,created_at,status) values(%s,%s,%s,%s,%s,'open')", (count_id, enterprise_id, branch_id, user_id, now))

            stock = conn.execute("select quantity from stock_position where enterprise_id=%s and branch_id=%s and product_id=%s", (enterprise_id, branch_id, product_id)).fetchone()
            system_qty = Decimal(str(stock[0])) if stock else None
            variance = counted_qty - system_qty if system_qty is not None else None

            provenance = json.dumps(
                {"evidence_ids": evidence_ids, "location_note": location_note, "source": "staff_realtime_count"},
                separators=(",", ":"),
                sort_keys=True,
            )
            conn.execute(
                "insert into stock_count_observations(observation_id,enterprise_id,branch_id,count_id,product_id,raw_item_ref,counted_qty,canonical_system_qty,variance_to_canonical,observed_at,observed_by,source_type,source_ref,evidence_id,identity_state,identity_confidence,observation_confidence,provisional_eligible,note,provenance_json) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'staff_realtime_count',%s,null,'resolved',1,1,true,%s,%s)",
                (observation_id, enterprise_id, branch_id, count_id, product_id, raw_item_ref, counted_qty, system_qty, variance, now, user_id, key, location_note, provenance),
            )

            # Legacy summary is retained only when canonical movement quantity actually exists.
            # Absence from stock_position is UNKNOWN and must never be encoded as numeric zero.
            if system_qty is not None:
                conn.execute(
                    "insert into stock_count_lines(count_id,product_id,system_qty,counted_qty,variance,evidence_ids) values(%s,%s,%s,%s,%s,%s) on conflict(count_id,product_id) do update set system_qty=excluded.system_qty,counted_qty=excluded.counted_qty,variance=excluded.variance,evidence_ids=excluded.evidence_ids",
                    (count_id, product_id, system_qty, counted_qty, variance, json.dumps(evidence_ids, separators=(",", ":"))),
                )

    return {
        "count_id": count_id,
        "observation_id": observation_id,
        "product_id": product_id,
        "system_qty": str(system_qty) if system_qty is not None else None,
        "system_qty_known": system_qty is not None,
        "counted_qty": str(counted_qty),
        "variance": str(variance) if variance is not None else None,
        "provisional_qty": str(counted_qty),
        "provisional_truth_state": "provisional_count",
        "stock_mutated": False,
        "status": "open",
        "idempotent_replay": False,
    }
