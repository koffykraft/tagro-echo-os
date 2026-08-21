from __future__ import annotations

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


def owner_on_call_readback(
    config: RuntimeConfig,
    *,
    enterprise_id: str,
    start: str | None = None,
    end: str | None = None,
    branch: str | None = None,
) -> dict[str, Any]:
    """Build a read-only Owner ON CALL projection from admitted PostgreSQL evidence.

    This intentionally does not claim the external historical warehouse has been
    loaded into PostgreSQL. Coverage/source metadata is returned explicitly.
    Closing Cash aggregate expense evidence is exposed as unclassified and bank
    movements remain Prism-unresolved unless a governed consequence exists.
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
        sales = tuple(
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
        purchases = tuple(
            PurchasePriceEvidence(
                item_key=str(product_id), purchase_date=purchase_date, cost_before_tax=Decimal(str(unit_price)),
                branch=str(code), source_ref=f"postgres:purchase:{purchase_id}", is_stock_transfer=False,
            )
            for product_id, purchase_date, unit_price, code, purchase_id in purchase_rows
        )

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
        evidence_as_of = timestamps[0] if timestamps and timestamps[0].year > 1970 else None

    snapshot = OwnerOnCall().snapshot(
        sales, purchases, expenses,
        start=start_date, end=end_date, branch=branch_code,
        cash_position=cash_position, bank_position=bank_position,
        evidence_as_of=evidence_as_of, prism_status=prism_status,
    )
    snapshot["runtime_source"] = "echo_postgres_admitted_evidence"
    snapshot["historical_warehouse_included"] = False
    snapshot["coverage_note"] = "PostgreSQL projection only; external sealed/current warehouse coverage is not implied by this endpoint."
    return owner_on_call_payload(snapshot)
