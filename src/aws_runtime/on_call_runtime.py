from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from src.financial.health import ExpenseEvidence, ExpenseRole, PurchasePriceEvidence, SaleLineEvidence
from src.financial.on_call import OwnerOnCall
from src.financial.presentation import owner_on_call_payload

from .config import RuntimeConfig
from .database import connect


class OnCallRuntimeError(ValueError):
    pass


def _parse_date(value: str | None, name: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise OnCallRuntimeError(f"invalid {name} date") from exc


def _in_period(value: date, start: date | None, end: date | None) -> bool:
    return (start is None or value >= start) and (end is None or value <= end)


def _warehouse_projection(conn, enterprise_id: str, start: date | None, end: date | None, branch: str | None):
    """Read only the latest financial run that has its manifest observation present.

    Chunks imported without their final manifest are intentionally invisible.
    Every row remains an import_observation; no canonical sale/purchase table is
    written by this bridge.
    """
    manifest_row = conn.execute(
        """
        select s.immutable_ref,o.observed_value_json,s.source_as_of,s.captured_at
        from import_observations o
        join import_sources s on s.source_id=o.source_id
        where o.enterprise_id=%s
          and o.subject_kind='financial_snapshot'
          and o.dimension_code='financial.export_manifest'
          and s.source_system='tagro_canonical_financial_projection'
          and o.acceptance_state in ('raw_supporting','reviewed_provisional','accepted_supporting')
        order by s.captured_at desc
        limit 1
        """,
        (enterprise_id,),
    ).fetchone()
    if not manifest_row:
        return (), (), None, None, None

    immutable_ref = str(manifest_row[0] or "")
    manifest = json.loads(manifest_row[1])
    source_as_of = manifest_row[2]
    rows = conn.execute(
        """
        select o.source_subject_ref,o.observed_value_json,o.provenance_ref,s.source_locator
        from import_observations o
        join import_sources s on s.source_id=o.source_id
        where o.enterprise_id=%s
          and o.subject_kind='financial_sale_line'
          and o.dimension_code='financial.sale_cost_evidence'
          and s.source_system='tagro_canonical_financial_projection'
          and s.immutable_ref=%s
          and o.acceptance_state in ('raw_supporting','reviewed_provisional','accepted_supporting')
        order by o.source_subject_ref
        """,
        (enterprise_id, immutable_ref),
    ).fetchall()

    expected = int(manifest.get("sale_line_observations") or 0)
    if len(rows) != expected:
        # Manifest exists but the run is incomplete/corrupt in the observation
        # store. Refuse the entire warehouse projection rather than partial P&L.
        return (), (), manifest, source_as_of, {
            "status": "incomplete_financial_observation_run",
            "expected_sale_lines": expected,
            "loaded_sale_lines": len(rows),
            "immutable_ref": immutable_ref,
        }

    sales: list[SaleLineEvidence] = []
    purchases_by_ref: dict[str, PurchasePriceEvidence] = {}
    for source_subject_ref, raw_json, provenance_ref, source_locator in rows:
        value = json.loads(raw_json)
        sale_date = date.fromisoformat(str(value["sale_date"]))
        branch_code = str(value["branch"]).upper()
        if not _in_period(sale_date, start, end) or (branch and branch_code != branch):
            continue
        item_key = str(value["item_key"])
        sales.append(
            SaleLineEvidence(
                sale_id=f"warehouse:{source_subject_ref}",
                sale_date=sale_date,
                branch=branch_code,
                item_key=item_key,
                quantity=Decimal(str(value["quantity"])),
                sale_before_tax=Decimal(str(value["sale_before_tax"])),
                source_ref=str(value.get("source_ref") or provenance_ref or source_locator),
            )
        )
        for reference in value.get("purchase_references") or []:
            ref = str(reference.get("source_ref") or "")
            if not ref:
                continue
            purchases_by_ref[ref] = PurchasePriceEvidence(
                item_key=item_key,
                purchase_date=date.fromisoformat(str(reference["purchase_date"])),
                cost_before_tax=Decimal(str(reference["cost_before_tax"])),
                branch=str(reference.get("branch") or "") or None,
                source_ref=ref,
                is_stock_transfer=False,
            )

    return tuple(sales), tuple(purchases_by_ref.values()), manifest, source_as_of, None


def owner_on_call_readback(
    config: RuntimeConfig,
    *,
    enterprise_id: str,
    start: str | None = None,
    end: str | None = None,
    branch: str | None = None,
) -> dict[str, Any]:
    """Build a read-only owner projection from canonical ECHO and evidence layers.

    Canonical ECHO transactions and imported warehouse observations stay distinct.
    Imported financial rows never become canonical merely because ON CALL reads
    them. Closing Cash aggregate expenses stay unclassified and bank movements
    remain Prism-unresolved until supported consequence evidence exists.
    """
    start_date = _parse_date(start, "start")
    end_date = _parse_date(end, "end")
    if start_date and end_date and start_date > end_date:
        raise OnCallRuntimeError("start date must not be after end date")
    branch_code = str(branch or "").strip().upper() or None

    with connect(config) as conn:
        params: list[Any] = [enterprise_id]
        sale_where = ["h.enterprise_id=%s"]
        if start_date:
            sale_where.append("h.created_at::date >= %s"); params.append(start_date)
        if end_date:
            sale_where.append("h.created_at::date <= %s"); params.append(end_date)
        if branch_code:
            sale_where.append("b.code=%s"); params.append(branch_code)
        sale_rows = conn.execute(
            f"""
            select h.sale_id,h.created_at::date,b.code,l.product_id,l.quantity,
                   (l.quantity*l.unit_price-l.discount) as taxable
            from sale_headers h
            join sale_lines l on l.sale_id=h.sale_id
            join branches b on b.branch_id=h.branch_id
            where {' and '.join(sale_where)}
            order by h.created_at,h.sale_id,l.line_no
            """,
            tuple(params),
        ).fetchall()
        echo_sales = tuple(
            SaleLineEvidence(
                sale_id=str(sale_id), sale_date=sale_date, branch=str(code), item_key=str(product_id),
                quantity=Decimal(str(qty)), sale_before_tax=Decimal(str(taxable)), source_ref=f"postgres:sale:{sale_id}",
            )
            for sale_id, sale_date, code, product_id, qty, taxable in sale_rows
        )

        purchase_params: list[Any] = [enterprise_id]
        purchase_where = ["h.enterprise_id=%s"]
        if end_date:
            purchase_where.append("h.created_at::date <= %s"); purchase_params.append(end_date)
        purchase_rows = conn.execute(
            f"""
            select l.product_id,h.created_at::date,l.unit_price,b.code,h.purchase_id
            from purchase_headers h
            join purchase_lines l on l.purchase_id=h.purchase_id
            join branches b on b.branch_id=h.branch_id
            where {' and '.join(purchase_where)} and l.unit_price>0
            order by h.created_at desc,h.purchase_id,l.line_no
            """,
            tuple(purchase_params),
        ).fetchall()
        echo_purchases = tuple(
            PurchasePriceEvidence(
                item_key=str(product_id), purchase_date=purchase_date, cost_before_tax=Decimal(str(unit_price)),
                branch=str(code), source_ref=f"postgres:purchase:{purchase_id}", is_stock_transfer=False,
            )
            for product_id, purchase_date, unit_price, code, purchase_id in purchase_rows
        )

        warehouse_sales, warehouse_purchases, warehouse_manifest, warehouse_as_of, warehouse_error = _warehouse_projection(
            conn, enterprise_id, start_date, end_date, branch_code
        )
        sales = echo_sales + warehouse_sales
        purchases = echo_purchases + warehouse_purchases

        expense_params: list[Any] = [enterprise_id]
        expense_where = ["c.enterprise_id=%s", "c.cash_expenses>0"]
        if start_date:
            expense_where.append("c.business_date >= %s"); expense_params.append(start_date)
        if end_date:
            expense_where.append("c.business_date <= %s"); expense_params.append(end_date)
        if branch_code:
            expense_where.append("b.code=%s"); expense_params.append(branch_code)
        expense_rows = conn.execute(
            f"""
            select c.closing_id,c.business_date,c.cash_expenses,b.code
            from cash_closings c join branches b on b.branch_id=c.branch_id
            where {' and '.join(expense_where)}
            order by c.business_date,c.closing_id
            """,
            tuple(expense_params),
        ).fetchall()
        expenses = tuple(
            ExpenseEvidence(
                expense_id=f"closing-cash:{closing_id}:expense", expense_date=business_date,
                amount=Decimal(str(amount)), branch=str(code), category=None,
                source_ref=f"postgres:cash-closing:{closing_id}", classification_confidence="unknown",
                role=ExpenseRole.UNKNOWN,
            )
            for closing_id, business_date, amount, code in expense_rows
        )

        prism_params: list[Any] = [enterprise_id]
        prism_where = ["enterprise_id=%s"]
        if start_date:
            prism_where.append("transaction_date >= %s"); prism_params.append(start_date)
        if end_date:
            prism_where.append("transaction_date <= %s"); prism_params.append(end_date)
        bank_rows = conn.execute(
            f"select transaction_id,amount from bank_transactions where {' and '.join(prism_where)}",
            tuple(prism_params),
        ).fetchall()
        unresolved_bank_amount = sum((Decimal(str(amount)) for _, amount in bank_rows), Decimal("0"))
        prism_status = {
            "source": "postgres_bank_observations_without_admitted_consequence",
            "total_count": len(bank_rows),
            "resolved_count": 0,
            "unresolved_count": len(bank_rows),
            "tight_split_count": 0,
            "unresolved_amount": unresolved_bank_amount,
            "tight_split_amount": Decimal("0"),
            "resolution_value_coverage_pct": Decimal("0.00") if bank_rows else Decimal("100.00"),
            "review_queue": [],
        }

        cash_params: list[Any] = [enterprise_id]
        cash_branch = ""
        if branch_code:
            cash_branch = " and b.code=%s"; cash_params.append(branch_code)
        if end_date:
            cash_branch += " and c.business_date<=%s"; cash_params.append(end_date)
        cash_rows = conn.execute(
            f"""
            select distinct on(c.branch_id) c.branch_id,c.declared_closing
            from cash_closings c join branches b on b.branch_id=c.branch_id
            where c.enterprise_id=%s {cash_branch}
            order by c.branch_id,c.business_date desc,c.recorded_at desc
            """,
            tuple(cash_params),
        ).fetchall()
        cash_position = sum((Decimal(str(v)) for _, v in cash_rows), Decimal("0")) if cash_rows else None

        latest_bank = conn.execute(
            """
            select distinct on(account_id) account_id,balance,transaction_date,source_row
            from bank_transactions where enterprise_id=%s
            order by account_id,transaction_date desc,source_row desc
            """,
            (enterprise_id,),
        ).fetchall()
        bank_position = None
        if latest_bank and all(row[1] is not None for row in latest_bank):
            bank_position = sum((Decimal(str(row[1])) for row in latest_bank), Decimal("0"))

        timestamps = conn.execute(
            """
            select greatest(
              coalesce((select max(created_at) from sale_headers where enterprise_id=%s),'epoch'::timestamptz),
              coalesce((select max(recorded_at) from cash_closings where enterprise_id=%s),'epoch'::timestamptz),
              coalesce((select max(transaction_date)::timestamptz from bank_transactions where enterprise_id=%s),'epoch'::timestamptz)
            )
            """,
            (enterprise_id, enterprise_id, enterprise_id),
        ).fetchone()
        postgres_as_of = timestamps[0] if timestamps and timestamps[0].year > 1970 else None
        evidence_as_of = max((x for x in (postgres_as_of, warehouse_as_of) if x is not None), default=None)

    snapshot = OwnerOnCall().snapshot(
        sales, purchases, expenses,
        start=start_date, end=end_date, branch=branch_code,
        cash_position=cash_position, bank_position=bank_position,
        evidence_as_of=evidence_as_of, prism_status=prism_status,
    )
    snapshot["runtime_source"] = "echo_postgres_plus_governed_financial_observations"
    snapshot["echo_sale_lines"] = len(echo_sales)
    snapshot["warehouse_sale_lines"] = len(warehouse_sales)
    snapshot["warehouse_financial_projection_included"] = bool(warehouse_manifest and not warehouse_error)
    snapshot["historical_warehouse_included"] = bool(
        warehouse_manifest and str(warehouse_manifest.get("sale_start") or "9999-12-31") <= "2007-01-09"
    )
    snapshot["warehouse_projection_manifest"] = warehouse_manifest
    snapshot["warehouse_projection_error"] = warehouse_error
    snapshot["busy_booking_reconciliation_required"] = True
    if warehouse_error:
        snapshot["coverage_note"] = "A warehouse financial run was found but is incomplete; it was excluded entirely from P&L."
    elif warehouse_manifest:
        snapshot["coverage_note"] = (
            f"Warehouse sale evidence {warehouse_manifest.get('sale_start')} through {warehouse_manifest.get('sale_end')} is included as non-canonical supporting observations. "
            "ECHO-originated sales remain a separate source; BUSY booking reconciliation is required before those streams can overlap."
        )
    else:
        snapshot["coverage_note"] = "No completed warehouse financial observation run is loaded; projection uses admitted PostgreSQL evidence only."
    return owner_on_call_payload(snapshot)
