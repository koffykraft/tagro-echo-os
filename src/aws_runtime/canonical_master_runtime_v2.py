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

    Rules:
    - blank HSN is accepted and never erases an already-known HSN;
    - blank GST is accepted and never erases an already-known GST;
    - a genuinely supplied 0 GST remains a known 0% rate;
    - products whose GST is still unknown are stored but marked inactive for
      billing/reference until GST is populated.
    """
    if not records:
        raise CanonicalMasterError("records required")

    # A completed source batch is immutable. Return it before deriving any values
    # from today's database state, so later enrichment cannot change replay hashes.
    with connect(config) as conn:
        completed = conn.execute(
            """
            select record_count,inserted_count,updated_count,unchanged_count
            from twin_source_sync_runs
            where sync_run_id=%s and enterprise_id=%s and status='complete'
            """,
            (sync_run_id, enterprise_id),
        ).fetchone()
    if completed:
        return {
            "sync_run_id": sync_run_id,
            "record_count": int(completed[0]),
            "inserted": 0,
            "updated": 0,
            "unchanged": int(completed[0]),
            "aliases_upserted": 0,
            "prices_upserted": 0,
            "idempotent_replay": True,
            "tax_completeness_enforced": True,
        }

    prepared: list[dict[str, Any]] = []
    tax_state: dict[str, bool] = {}

    # Read any existing canonical tax/HSN values first so an incomplete later
    # source cannot erase stronger existing information.
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
                existing[sku] = {"gst_rate": row[0], "gst_known": bool(row[1]), "hsn_code": str(row[2] or "")}

    for raw in records:
        if not isinstance(raw, Mapping):
            raise CanonicalMasterError("canonical master record must be an object")
        item = deepcopy(dict(raw))
        sku = _clean(item.get("sku"))
        if not sku:
            prepared.append(item)
            continue

        prior = existing.get(sku) or {}
        gst_text = _clean(item.get("gst_rate"))
        gst_known = gst_text != ""
        if not gst_known and prior.get("gst_known"):
            item["gst_rate"] = str(prior.get("gst_rate"))
            gst_known = True
        elif not gst_known:
            # v1 needs a decimal during normalization; post-processing below
            # restores SQL NULL and marks the item not billable.
            item["gst_rate"] = "0"

        hsn = _clean(item.get("hsn_code"))
        if not hsn and prior.get("hsn_code"):
            item["hsn_code"] = prior["hsn_code"]

        tax_state[sku] = gst_known
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
            for sku, gst_known in tax_state.items():
                product = conn.execute(
                    "select product_id from products where enterprise_id=%s and sku=%s",
                    (enterprise_id, sku),
                ).fetchone()
                if not product:
                    continue
                product_id = str(product[0])
                if gst_known:
                    conn.execute(
                        "update products set active=true where enterprise_id=%s and product_id=%s",
                        (enterprise_id, product_id),
                    )
                else:
                    conn.execute(
                        "update products set gst_rate=null,active=false where enterprise_id=%s and product_id=%s",
                        (enterprise_id, product_id),
                    )
                conn.execute(
                    "update product_commercial_attributes set gst_known=%s where enterprise_id=%s and product_id=%s",
                    (gst_known, enterprise_id, product_id),
                )

    return {**result, "tax_completeness_enforced": True}
