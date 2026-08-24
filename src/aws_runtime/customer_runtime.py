from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping

from .config import RuntimeConfig
from .database import connect


class CustomerRuntimeError(ValueError):
    pass


def _stable_id(enterprise_id: str, key: str) -> str:
    return f"echo-customer-{sha256(f'{enterprise_id}|{key}'.encode()).hexdigest()[:24]}"


def _clean(value: Any) -> str:
    return str(value or "").strip()


def create_customer(
    config: RuntimeConfig,
    *,
    principal_id: str,
    membership: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    caps = {str(x).upper() for x in membership.get("capabilities") or []}
    if not caps.intersection({"SELL", "SERVICE"}):
        raise PermissionError("SELL or SERVICE capability required")

    enterprise_id = _clean(membership.get("enterprise_id"))
    name = _clean(payload.get("name"))
    phone = _clean(payload.get("phone"))
    email = _clean(payload.get("email"))
    gstin = _clean(payload.get("gstin")).upper()
    district = _clean(payload.get("district"))
    key = _clean(payload.get("idempotency_key"))

    if not enterprise_id or not name or not phone or not key:
        raise CustomerRuntimeError("name, phone and idempotency_key are required")
    if len(name) > 160 or len(phone) > 40 or len(email) > 254 or len(gstin) > 32 or len(district) > 120:
        raise CustomerRuntimeError("customer field exceeds admitted length")

    customer_id = _stable_id(enterprise_id, key)

    with connect(config) as conn:
        with conn.transaction():
            user = conn.execute(
                "select user_id from users where enterprise_id=%s and principal_id=%s and active=true",
                (enterprise_id, principal_id),
            ).fetchone()
            if not user:
                raise CustomerRuntimeError("authenticated principal has no active ECHO user")

            replay = conn.execute(
                "select name,phone,email,gstin,district from customers where enterprise_id=%s and customer_id=%s",
                (enterprise_id, customer_id),
            ).fetchone()
            if replay:
                return {
                    "customer_id": customer_id,
                    "name": replay[0],
                    "phone": replay[1],
                    "email": replay[2],
                    "gstin": replay[3],
                    "district": replay[4],
                    "matched_existing": False,
                    "idempotent_replay": True,
                }

            existing = conn.execute(
                "select customer_id,name,phone,email,gstin,district from customers where enterprise_id=%s and phone=%s order by customer_id limit 1",
                (enterprise_id, phone),
            ).fetchone()
            if existing:
                return {
                    "customer_id": str(existing[0]),
                    "name": existing[1],
                    "phone": existing[2],
                    "email": existing[3],
                    "gstin": existing[4],
                    "district": existing[5],
                    "matched_existing": True,
                    "idempotent_replay": False,
                }

            conn.execute(
                "insert into customers(customer_id,enterprise_id,name,phone,email,gstin,district) values(%s,%s,%s,%s,%s,%s,%s)",
                (customer_id, enterprise_id, name, phone, email, gstin, district),
            )

    return {
        "customer_id": customer_id,
        "name": name,
        "phone": phone,
        "email": email,
        "gstin": gstin,
        "district": district,
        "matched_existing": False,
        "idempotent_replay": False,
    }
