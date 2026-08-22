from __future__ import annotations

import json
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from src.financial.health import ExpenseEvidence, ExpenseRole


_ALLOWED_CONFIDENCE = {"exact", "strong", "weak", "unknown"}
_ROLE_MAP = {role.value: role for role in ExpenseRole}


def _in_period(value: date, start: date | None, end: date | None) -> bool:
    return (start is None or value >= start) and (end is None or value <= end)


def _governed_classification(category: Any, role: Any, confidence: Any) -> tuple[str | None, ExpenseRole, str]:
    """Admit only complete explicit classifications; partial evidence stays unknown."""
    category_text = str(category or "").strip() or None
    role_value = _ROLE_MAP.get(str(role or "").strip().lower(), ExpenseRole.UNKNOWN)
    confidence_value = str(confidence or "unknown").strip().lower()
    complete = (
        category_text is not None
        and role_value != ExpenseRole.UNKNOWN
        and confidence_value in _ALLOWED_CONFIDENCE
        and confidence_value != "unknown"
    )
    if not complete:
        return None, ExpenseRole.UNKNOWN, "unknown"
    return category_text, role_value, confidence_value


def cash_entry_expense_evidence(
    conn,
    enterprise_id: str,
    *,
    start: date | None = None,
    end: date | None = None,
    branch: str | None = None,
) -> tuple[ExpenseEvidence, ...]:
    """Read Closing Cash entry-level expense evidence without inferring P&L meaning.

    Only explicit expense entry types are considered. Deposit/allocation/transfer rows
    are excluded because movement of cash does not itself prove an expense. Existing
    category/role/confidence fields are admitted only when complete; otherwise the
    evidence remains visible as unknown.
    """
    params: list[Any] = [enterprise_id]
    where = ["e.enterprise_id=%s", "e.entry_type in ('expense_cash','expense_noncash')"]
    if start:
        where.append("e.business_date >= %s")
        params.append(start)
    if end:
        where.append("e.business_date <= %s")
        params.append(end)
    if branch:
        where.append("b.code=%s")
        params.append(branch.upper())

    rows = conn.execute(
        f"""
        select e.entry_id,e.business_date,e.amount,b.code,e.classification_category,
               e.classification_role,e.classification_confidence,e.evidence_ref,e.reference,e.note
        from cash_entry_evidence e
        join branches b on b.branch_id=e.branch_id
        where {' and '.join(where)}
        order by e.business_date,e.occurred_at,e.entry_id
        """,
        tuple(params),
    ).fetchall()

    evidence: list[ExpenseEvidence] = []
    for entry_id, business_date, amount, branch_code, category, role, confidence, evidence_ref, reference, note in rows:
        category_value, role_value, confidence_value = _governed_classification(category, role, confidence)
        evidence.append(
            ExpenseEvidence(
                expense_id=f"cash-entry:{entry_id}",
                expense_date=business_date,
                amount=Decimal(str(amount)),
                branch=str(branch_code),
                category=category_value,
                source_ref=str(evidence_ref or reference or f"cash-entry:{entry_id}"),
                classification_confidence=confidence_value,
                role=role_value,
            )
        )
    return tuple(evidence)


def imported_accounting_expense_evidence(
    conn,
    enterprise_id: str,
    *,
    start: date | None = None,
    end: date | None = None,
    branch: str | None = None,
) -> tuple[ExpenseEvidence, ...]:
    """Read supporting accounting expense observations without promoting them to truth.

    The importer stores these as supporting observations. This reader does not infer
    from narration, debit/credit direction, ledger name, or voucher type. The source
    payload must carry amount and business_date. P&L classification is admitted only
    when category, role and non-unknown confidence are all explicitly present.
    """
    rows = conn.execute(
        """
        select o.observation_id,o.source_subject_ref,o.observed_value_json,o.provenance_ref,
               o.acceptance_state,s.source_system,s.source_locator
        from import_observations o
        join import_sources s on s.source_id=o.source_id
        where o.enterprise_id=%s
          and o.subject_kind='financial_expense_observation'
          and o.dimension_code='financial.expense_evidence'
          and o.acceptance_state in ('raw_supporting','reviewed_provisional','accepted_supporting')
        order by s.captured_at,o.source_subject_ref,o.observation_id
        """,
        (enterprise_id,),
    ).fetchall()

    evidence: list[ExpenseEvidence] = []
    for observation_id, source_subject_ref, raw_json, provenance_ref, acceptance_state, source_system, source_locator in rows:
        try:
            value = json.loads(raw_json)
            business_date = date.fromisoformat(str(value.get("business_date") or ""))
            amount = Decimal(str(value.get("amount")))
        except (ValueError, TypeError, InvalidOperation, json.JSONDecodeError):
            continue
        if amount <= 0 or not _in_period(business_date, start, end):
            continue
        branch_code = str(value.get("branch") or "").strip().upper() or None
        if branch and branch_code != branch.upper():
            continue
        category_value, role_value, confidence_value = _governed_classification(
            value.get("category"), value.get("role"), value.get("classification_confidence")
        )
        evidence.append(
            ExpenseEvidence(
                expense_id=f"accounting-observation:{observation_id}",
                expense_date=business_date,
                amount=amount,
                branch=branch_code,
                category=category_value,
                source_ref=str(
                    value.get("source_ref")
                    or provenance_ref
                    or f"{source_system}:{source_locator}:{source_subject_ref}"
                ),
                classification_confidence=confidence_value,
                role=role_value,
            )
        )
    return tuple(evidence)


def expense_evidence_diagnostics(rows: Iterable[ExpenseEvidence]) -> dict[str, Any]:
    evidence = tuple(rows)
    classified = [e for e in evidence if e.category and e.role != ExpenseRole.UNKNOWN and e.classification_confidence != "unknown"]
    unknown = [e for e in evidence if e not in classified]
    return {
        "count": len(evidence),
        "classified_count": len(classified),
        "unknown_count": len(unknown),
        "amount": sum((abs(e.amount) for e in evidence), Decimal("0")),
        "classified_amount": sum((abs(e.amount) for e in classified), Decimal("0")),
        "unknown_amount": sum((abs(e.amount) for e in unknown), Decimal("0")),
        "confidence_counts": {
            confidence: sum(1 for e in evidence if e.classification_confidence == confidence)
            for confidence in ("exact", "strong", "weak", "unknown")
        },
    }
