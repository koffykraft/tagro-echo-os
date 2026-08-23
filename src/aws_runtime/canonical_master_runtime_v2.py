from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from .canonical_master_runtime import CanonicalMasterError, sync_canonical_master as _sync_v1
from .config import RuntimeConfig
from .database import connect


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _decimal(value: Any, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise CanonicalMasterError(f"invalid {field}") from exc


def _conversion_id(enterprise_id: str, product_id: str, from_unit: str, to_unit: str, usage_type: str, branch_code: str) -> str:
    raw = f"{enterprise_id}|{product_id}|{from_unit}|{to_unit}|{usage_type}|{branch_code}"
    return "echo-uom-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


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
    """Admit canonical master records while preserving unknown tax and explicit UOM evidence.

    Catalogue visibility and billability remain separate. BUSY unit stays the product's
    operational unit. Any alternate pack/reel conversion is admitted only when the
    payload supplies an explicit positive multiplier; no conversion is inferred from names.
    """
    if not records:
        raise CanonicalMasterError("records required")

    existing: dict[str, dict[str, Any]] = {}
    with connect(config) as conn:
        for raw in records:
            sku = _clean(raw.get("sku")) if isinstance(raw, Mapping) else ""
            if not sku:
                continue
            row = conn.execute(
                """
                select p.gst_rate, coalesce(pca.gst_known,false), coalesce(pca.hsn_code,'')
                from products p
                left join product_commercial_attributes pca on pca.product_id=p.product_id
                where p.enterprise_id=%s and p.sku=%s
                """,
                (enterprise_id, sku),
            ).fetchone()
            if row:
                existing[sku] = {
                    "gst_rate": row[0],
                    "gst_known": bool(row[1]),
                    "hsn_code": str(row[2] or ""),
                }

    prepared: list[dict[str, Any]] = []
    source_state: dict[str, dict[str, Any]] = {}
    conversions_by_sku: dict[str, list[dict[str, Any]]] = {}
    for raw in records:
        if not isinstance(raw, Mapping):
            raise CanonicalMasterError("canonical master record must be an object")
        item = deepcopy(dict(raw))
        sku = _clean(item.get("sku"))
        if not sku:
            prepared.append(item)
            continue

        incoming_gst = _clean(item.get("gst_rate"))
        incoming_hsn = _clean(item.get("hsn_code"))
        source_state[sku] = {
            "gst_known": incoming_gst != "",
            "hsn_known": incoming_hsn != "",
        }

        raw_conversions = item.pop("unit_conversions", []) or []
        if not isinstance(raw_conversions, list):
            raise CanonicalMasterError(f"unit_conversions must be an array for {sku}")
        clean_conversions: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str, str]] = set()
        for entry in raw_conversions:
            if not isinstance(entry, Mapping):
                raise CanonicalMasterError(f"unit conversion must be an object for {sku}")
            from_unit = _clean(entry.get("from_unit"))
            to_unit = _clean(entry.get("to_unit"))
            usage_type = _clean(entry.get("usage_type")) or "general"
            branch_code = _clean(entry.get("branch_code")).upper()
            multiplier = _decimal(entry.get("multiplier"), "unit conversion multiplier")
            if not from_unit or not to_unit or from_unit.lower() == to_unit.lower() or multiplier <= 0:
                raise CanonicalMasterError(f"invalid unit conversion for {sku}")
            key = (from_unit, to_unit, usage_type, branch_code)
            if key in seen:
                raise CanonicalMasterError(f"duplicate unit conversion for {sku}: {key}")
            seen.add(key)
            clean_conversions.append({
                "from_unit": from_unit,
                "to_unit": to_unit,
                "usage_type": usage_type,
                "branch_code": branch_code,
                "multiplier": multiplier,
                "source_ref": _clean(entry.get("source_ref")) or source_locator,
            })
        conversions_by_sku[sku] = clean_conversions

        # v1 normalization requires a decimal. Zero is a transport sentinel only.
        if incoming_gst == "":
            item["gst_rate"] = "0"
        prepared.append(item)

    result = _sync_v1(
        config,
        enterprise_id=enterprise_id,
        source_system=source_system,
        source_locator=source_locator,
        source_class=source_class,
        source_as_of=source_as_of,
        records=prepared,
        sync_run_id=sync_run_id,
        provenance=provenance,
    )

    conversions_upserted = 0
    with connect(config) as conn:
        with conn.transaction():
            for sku, state in source_state.items():
                product = conn.execute(
                    "select product_id from products where enterprise_id=%s and sku=%s",
                    (enterprise_id, sku),
                ).fetchone()
                if not product:
                    continue
                product_id = str(product[0])
                prior = existing.get(sku) or {}

                if state["gst_known"]:
                    gst_known = True
                    conn.execute(
                        "update products set active=true where enterprise_id=%s and product_id=%s",
                        (enterprise_id, product_id),
                    )
                elif prior.get("gst_known"):
                    gst_known = True
                    conn.execute(
                        "update products set gst_rate=%s,active=true where enterprise_id=%s and product_id=%s",
                        (prior.get("gst_rate"), enterprise_id, product_id),
                    )
                else:
                    gst_known = False
                    conn.execute(
                        "update products set gst_rate=null,active=true where enterprise_id=%s and product_id=%s",
                        (enterprise_id, product_id),
                    )

                if not state["hsn_known"] and prior.get("hsn_code"):
                    conn.execute(
                        "update product_commercial_attributes set hsn_code=%s where enterprise_id=%s and product_id=%s",
                        (prior["hsn_code"], enterprise_id, product_id),
                    )

                conn.execute(
                    "update product_commercial_attributes set gst_known=%s where enterprise_id=%s and product_id=%s",
                    (gst_known, enterprise_id, product_id),
                )

                for conversion in conversions_by_sku.get(sku, []):
                    branch_id = None
                    if conversion["branch_code"]:
                        branch = conn.execute(
                            "select branch_id from branches where enterprise_id=%s and code=%s",
                            (enterprise_id, conversion["branch_code"]),
                        ).fetchone()
                        if not branch:
                            raise CanonicalMasterError(f"unknown branch code {conversion['branch_code']} in unit conversion")
                        branch_id = str(branch[0])
                    conversion_id = _conversion_id(
                        enterprise_id, product_id, conversion["from_unit"], conversion["to_unit"],
                        conversion["usage_type"], conversion["branch_code"],
                    )
                    conv_provenance = json.dumps(
                        {
                            "source_system": source_system,
                            "source_locator": source_locator,
                            "source_as_of": source_as_of,
                            "sync_run_id": sync_run_id,
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                        default=str,
                    )
                    conn.execute(
                        """
                        insert into product_unit_conversions(
                          conversion_id,enterprise_id,product_id,from_unit,to_unit,multiplier,
                          usage_type,branch_id,source_ref,provenance_json,active,updated_at
                        ) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,true,now())
                        on conflict(conversion_id) do update set
                          multiplier=excluded.multiplier,source_ref=excluded.source_ref,
                          provenance_json=excluded.provenance_json,active=true,updated_at=now()
                        """,
                        (
                            conversion_id, enterprise_id, product_id, conversion["from_unit"], conversion["to_unit"],
                            conversion["multiplier"], conversion["usage_type"], branch_id,
                            conversion["source_ref"], conv_provenance,
                        ),
                    )
                    conversions_upserted += 1

    return {
        **result,
        "tax_completeness_enforced": True,
        "unit_conversions_upserted": conversions_upserted,
        "unit_conversion_inference": False,
    }
