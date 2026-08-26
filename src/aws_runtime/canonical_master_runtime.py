from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Any, Mapping
from uuid import UUID, uuid5

from .config import RuntimeConfig
from .database import connect

MASTER_NAMESPACE = UUID("a3318f90-a19b-4b72-8b8a-e46c5d20c1c8")


class CanonicalMasterError(ValueError):
    pass


def _stable_id(kind: str, enterprise_id: str, value: str) -> str:
    return str(uuid5(MASTER_NAMESPACE, f"{enterprise_id}|{kind}|{value}"))


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _code(value: Any) -> str:
    return _clean(value).upper()


def _decimal(value: Any, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise CanonicalMasterError(f"invalid {field}") from exc
    return result


def _date(value: Any, field: str) -> date:
    text = _clean(value)
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise CanonicalMasterError(f"invalid {field}") from exc


def _payload_hash(records: list[Mapping[str, Any]]) -> str:
    return sha256(json.dumps(records, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def sync_canonical_master(
    config: RuntimeConfig,
    *,
    enterprise_id: str,
    source_system: str,
    source_locator: str,
    source_class: str,
    source_as_of: str | None,
    records: list[Mapping[str, Any]],
    sync_run_id: str,
    provenance: Mapping[str, Any],
) -> dict[str, Any]:
    if not records:
        raise CanonicalMasterError("records required")

    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(records, start=1):
        if not isinstance(raw, Mapping):
            raise CanonicalMasterError(f"record {index} must be an object")
        manufacturer = _code(raw.get("manufacturer"))
        sku = _clean(raw.get("sku"))
        name = _clean(raw.get("name"))
        model = _clean(raw.get("model")) or name
        category = _clean(raw.get("category")) or "UNCLASSIFIED"
        hsn_code = _clean(raw.get("hsn_code"))
        gst_rate = _decimal(raw.get("gst_rate", 0), "gst_rate")
        unit = _clean(raw.get("unit")) or "nos"
        if not manufacturer or not sku or not name:
            raise CanonicalMasterError(f"record {index} requires manufacturer, sku and name")
        if gst_rate < 0 or gst_rate > Decimal("100"):
            raise CanonicalMasterError(f"record {index} GST rate out of range")

        aliases = raw.get("aliases") or []
        prices = raw.get("prices") or []
        if not isinstance(aliases, list) or not isinstance(prices, list):
            raise CanonicalMasterError(f"record {index} aliases/prices must be arrays")

        clean_aliases: list[dict[str, str]] = []
        seen_aliases: set[tuple[str, str, str]] = set()
        for alias in aliases:
            if not isinstance(alias, Mapping):
                raise CanonicalMasterError(f"record {index} alias must be an object")
            alias_type = _clean(alias.get("type")).lower()
            alias_value = _clean(alias.get("value"))
            branch_code = _code(alias.get("branch_code"))
            if not alias_type or not alias_value:
                continue
            key = (alias_type, alias_value, branch_code)
            if key not in seen_aliases:
                seen_aliases.add(key)
                clean_aliases.append({"type": alias_type, "value": alias_value, "branch_code": branch_code})

        clean_prices: list[dict[str, Any]] = []
        seen_prices: set[tuple[str, str, str]] = set()
        for price in prices:
            if not isinstance(price, Mapping):
                raise CanonicalMasterError(f"record {index} price must be an object")
            price_type = _clean(price.get("type")).lower()
            amount = _decimal(price.get("amount"), "price amount")
            effective_from = _date(price.get("effective_from"), "effective_from")
            branch_code = _code(price.get("branch_code"))
            if not price_type or amount < 0:
                raise CanonicalMasterError(f"record {index} invalid price")
            key = (price_type, effective_from.isoformat(), branch_code)
            if key in seen_prices:
                raise CanonicalMasterError(f"record {index} duplicate price identity")
            seen_prices.add(key)
            clean_prices.append({
                "type": price_type,
                "amount": amount,
                "effective_from": effective_from,
                "branch_code": branch_code,
            })

        normalized.append({
            "manufacturer": manufacturer,
            "sku": sku,
            "model": model,
            "name": name,
            "category": category,
            "hsn_code": hsn_code,
            "gst_rate": gst_rate,
            "unit": unit,
            "serial_tracked": bool(raw.get("serial_tracked", False)),
            "aliases": clean_aliases,
            "prices": clean_prices,
        })

    payload_hash = _payload_hash(records)
    started = datetime.now(timezone.utc)
    product_inserted = product_updated = product_unchanged = 0
    aliases_upserted = prices_upserted = 0

    with connect(config) as conn:
        with conn.transaction():
            existing_run = conn.execute(
                "select payload_hash,status,record_count from twin_source_sync_runs where sync_run_id=%s and enterprise_id=%s",
                (sync_run_id, enterprise_id),
            ).fetchone()
            if existing_run:
                if str(existing_run[0]) != payload_hash:
                    raise CanonicalMasterError("sync_run_id replayed with different canonical master payload")
                if str(existing_run[1]) == "complete":
                    return {
                        "sync_run_id": sync_run_id,
                        "record_count": int(existing_run[2]),
                        "inserted": 0,
                        "updated": 0,
                        "unchanged": int(existing_run[2]),
                        "aliases_upserted": 0,
                        "prices_upserted": 0,
                        "idempotent_replay": True,
                    }
            else:
                conn.execute(
                    """
                    insert into twin_source_sync_runs(
                      sync_run_id,enterprise_id,source_system,source_locator,source_class,
                      source_as_of,started_at,record_count,payload_hash,status,provenance_json
                    ) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,'running',%s)
                    """,
                    (
                        sync_run_id, enterprise_id, source_system, source_locator, source_class,
                        source_as_of, started, len(normalized), payload_hash,
                        json.dumps(dict(provenance), sort_keys=True, separators=(",", ":"), default=str),
                    ),
                )

            for record in normalized:
                manufacturer_id = _stable_id("manufacturer", enterprise_id, record["manufacturer"])
                conn.execute(
                    """
                    insert into catalog_manufacturers(manufacturer_id,enterprise_id,code,name,active,source_ref)
                    values(%s,%s,%s,%s,true,%s)
                    on conflict(enterprise_id,code) do update set name=excluded.name,active=true,source_ref=excluded.source_ref
                    """,
                    (manufacturer_id, enterprise_id, record["manufacturer"], record["manufacturer"], source_locator),
                )

                product_id = _stable_id("product", enterprise_id, f"{record['manufacturer']}|{record['sku']}")
                existing = conn.execute(
                    "select product_id,model,name,category,gst_rate,unit,serial_tracked,active from products where enterprise_id=%s and sku=%s",
                    (enterprise_id, record["sku"]),
                ).fetchone()
                desired = (
                    record["model"], record["name"], record["category"], record["gst_rate"],
                    record["unit"], record["serial_tracked"], True,
                )
                if not existing:
                    conn.execute(
                        """
                        insert into products(product_id,enterprise_id,sku,model,name,category,gst_rate,unit,serial_tracked,active)
                        values(%s,%s,%s,%s,%s,%s,%s,%s,%s,true)
                        """,
                        (
                            product_id, enterprise_id, record["sku"], record["model"], record["name"],
                            record["category"], record["gst_rate"], record["unit"], record["serial_tracked"],
                        ),
                    )
                    product_inserted += 1
                else:
                    product_id = str(existing[0])
                    current_gst = None if existing[4] is None else Decimal(str(existing[4]))
                    current = (existing[1], existing[2], existing[3], current_gst, existing[5], existing[6], existing[7])
                    if current == desired:
                        product_unchanged += 1
                    else:
                        conn.execute(
                            """
                            update products set model=%s,name=%s,category=%s,gst_rate=%s,unit=%s,serial_tracked=%s,active=true
                            where enterprise_id=%s and product_id=%s
                            """,
                            (*desired[:-1], enterprise_id, product_id),
                        )
                        product_updated += 1

                commercial_provenance = json.dumps(
                    {"source_system": source_system, "source_locator": source_locator, "source_as_of": source_as_of},
                    sort_keys=True, separators=(",", ":"), default=str,
                )
                conn.execute(
                    """
                    insert into product_commercial_attributes(
                      product_id,enterprise_id,manufacturer_id,manufacturer_part_no,hsn_code,source_ref,provenance_json
                    ) values(%s,%s,%s,%s,%s,%s,%s)
                    on conflict(product_id) do update set
                      manufacturer_id=excluded.manufacturer_id,
                      manufacturer_part_no=excluded.manufacturer_part_no,
                      hsn_code=excluded.hsn_code,
                      source_ref=excluded.source_ref,
                      provenance_json=excluded.provenance_json
                    """,
                    (product_id, enterprise_id, manufacturer_id, record["sku"], record["hsn_code"], source_locator, commercial_provenance),
                )

                # The official manufacturer part number is a valid product alias.
                # The manufacturer name itself is NOT a product alias because one
                # manufacturer naturally owns many products.
                official_aliases = [
                    {"type": "manufacturer_part_no", "value": record["sku"], "branch_code": ""},
                ]
                for alias in official_aliases + record["aliases"]:
                    existing_alias = conn.execute(
                        """
                        select product_id from product_aliases
                        where enterprise_id=%s and alias_type=%s and alias_value=%s and branch_code=%s
                        """,
                        (enterprise_id, alias["type"], alias["value"], alias["branch_code"]),
                    ).fetchone()
                    if existing_alias and str(existing_alias[0]) != product_id:
                        raise CanonicalMasterError(
                            f"alias collision: {alias['type']}={alias['value']} branch={alias['branch_code'] or 'GLOBAL'} already belongs to another product"
                        )
                    alias_identity = f"{alias['type']}|{alias['value']}|{alias['branch_code']}"
                    alias_id = _stable_id("alias", enterprise_id, alias_identity)
                    conn.execute(
                        """
                        insert into product_aliases(alias_id,enterprise_id,product_id,alias_type,alias_value,branch_code,source_ref,active)
                        values(%s,%s,%s,%s,%s,%s,%s,true)
                        on conflict(enterprise_id,alias_type,alias_value,branch_code)
                        do update set source_ref=excluded.source_ref,active=true
                        """,
                        (alias_id, enterprise_id, product_id, alias["type"], alias["value"], alias["branch_code"], source_locator),
                    )
                    aliases_upserted += 1

                for price in record["prices"]:
                    branch_id = None
                    if price["branch_code"]:
                        branch = conn.execute(
                            "select branch_id from branches where enterprise_id=%s and code=%s",
                            (enterprise_id, price["branch_code"]),
                        ).fetchone()
                        if not branch:
                            raise CanonicalMasterError(f"unknown branch code {price['branch_code']} in price")
                        branch_id = str(branch[0])
                    price_identity = f"{product_id}|{price['type']}|{price['effective_from'].isoformat()}|{branch_id or ''}"
                    price_id = _stable_id("price", enterprise_id, price_identity)
                    conn.execute(
                        """
                        insert into prices(price_id,enterprise_id,product_id,price_type,amount,effective_from,effective_to,branch_id)
                        values(%s,%s,%s,%s,%s,%s,null,%s)
                        on conflict(price_id) do update set amount=excluded.amount
                        """,
                        (price_id, enterprise_id, product_id, price["type"], price["amount"], price["effective_from"], branch_id),
                    )
                    prices_upserted += 1

            completed = datetime.now(timezone.utc)
            conn.execute(
                """
                update twin_source_sync_runs set completed_at=%s,inserted_count=%s,updated_count=%s,
                  unchanged_count=%s,status='complete' where sync_run_id=%s and enterprise_id=%s
                """,
                (completed, product_inserted, product_updated, product_unchanged, sync_run_id, enterprise_id),
            )

    return {
        "sync_run_id": sync_run_id,
        "record_count": len(normalized),
        "inserted": product_inserted,
        "updated": product_updated,
        "unchanged": product_unchanged,
        "aliases_upserted": aliases_upserted,
        "prices_upserted": prices_upserted,
        "idempotent_replay": False,
    }
