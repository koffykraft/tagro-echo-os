from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .canonical_master_runtime import CanonicalMasterError, sync_canonical_master as _sync_v1
from .config import RuntimeConfig
from .database import connect


def _clean(value: Any) -> str:
    return str(value or "").strip()


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
    """Admit canonical master records while preserving unknown HSN/GST as unknown.

    The prepared payload is derived only from the incoming package, so idempotency
    hashing remains stable. Existing stronger HSN/GST values are captured before
    admission and restored afterwards when an incoming field is blank.
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

        # v1 normalization requires a decimal. Zero here is only a deterministic
        # transport sentinel; it is converted to SQL NULL after the v1 transaction
        # whenever GST was actually absent in the source.
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
                        "update products set gst_rate=null,active=false where enterprise_id=%s and product_id=%s",
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

    return {**result, "tax_completeness_enforced": True}
