from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Mapping

from src.bank.normalization import BankTransaction

from .closing_cash_learning import ClosingCashEvidenceRow, LearningRule, suggest
from .prism import AdaptivePrism, PrismCandidate, PrismDepth, PrismObservation, PrismResult


# Semantic classes that describe event meaning only. They do not, by themselves,
# establish the final financial consequence used by FinancialHealthEngine.
_EVENT_FAMILY = {
    "DIRECT_SALES": "SALE_OR_RECEIPT",
    "SERVICE_INCOME": "SERVICE_RECEIPT",
    "CASH_BOX_MOVEMENT": "INTERNAL_CASH_MOVEMENT",
    "BANK_OR_TRANSFER": "BANK_OR_INTERNAL_MOVEMENT",
    "OWNER_DRAWING_OR_OWNER_USE": "OWNER_MOVEMENT",
    "LOCAL_PURCHASE": "PURCHASE_OR_SUPPLIER_PAYMENT",
    "CHITTY": "CHITTY_MOVEMENT",
}

# These are business-meaning labels only. Financial consequence remains gated.
_BUSINESS_MEANING = {
    "FOOD_EXPENSE",
    "OFFICE_EXPENSE",
    "SERVICE_CENTER_EXPENSE",
    "VEHICLE_EXPENSE",
    "TRAVEL_EXPENSE",
    "COURIER_FREIGHT",
    "SALARY",
    "RENT",
    "STAFF_WELFARE",
}


def closing_cash_observation(row: ClosingCashEvidenceRow) -> PrismObservation:
    direction = "in" if row.kind.value == "sales" else "out"
    return PrismObservation(
        observation_id=f"closing-cash:{row.branch}:{row.business_date}:{row.source_row or 'na'}",
        source_kind="closing_cash",
        source_ref=row.source_ref or f"closing-cash:{row.branch}:{row.business_date}",
        amount=Decimal(row.amount),
        direction=direction,
        branch=row.branch.strip().upper() or None,
        narration=row.particulars or row.narration,
        business_date=row.business_date,
    )


def closing_cash_candidates(
    row: ClosingCashEvidenceRow,
    learned_rules: Iterable[LearningRule] = (),
) -> tuple[PrismCandidate, ...]:
    learning = suggest(row, learned_rules)
    candidates: list[PrismCandidate] = []
    family = _EVENT_FAMILY.get(learning.semantic_class)
    if family:
        candidates.append(
            PrismCandidate(
                family,
                learning.confidence,
                PrismDepth.EVENT_FAMILY,
                learning.reason,
                learning.rule_source,
            )
        )
    if learning.semantic_class in _BUSINESS_MEANING:
        candidates.append(
            PrismCandidate(
                learning.semantic_class,
                learning.confidence,
                PrismDepth.BUSINESS_MEANING,
                learning.reason,
                learning.rule_source,
            )
        )
    if not candidates:
        candidates.append(
            PrismCandidate(
                learning.semantic_class,
                learning.confidence,
                PrismDepth.EVENT_FAMILY,
                learning.reason,
                learning.rule_source,
            )
        )
    return tuple(candidates)


def disperse_closing_cash(
    row: ClosingCashEvidenceRow,
    learned_rules: Iterable[LearningRule] = (),
    prism: AdaptivePrism | None = None,
) -> PrismResult:
    engine = prism or AdaptivePrism()
    return engine.resolve(closing_cash_observation(row), closing_cash_candidates(row, learned_rules))


def bank_observation(transaction: BankTransaction, branch: str | None = None) -> PrismObservation:
    transaction.validate()
    return PrismObservation(
        observation_id=f"bank:{transaction.transaction_id}",
        source_kind="bank_statement",
        source_ref=f"bank:{transaction.statement_id}:{transaction.source_row}",
        amount=Decimal(transaction.amount),
        direction=transaction.direction,
        branch=branch,
        account=transaction.account_id,
        narration=transaction.narration,
        business_date=transaction.transaction_date.isoformat(),
    )


def bank_candidates(
    transaction: BankTransaction,
    governed_meanings: Mapping[str, tuple[str, float, PrismDepth, str]] | None = None,
) -> tuple[PrismCandidate, ...]:
    """Return governed bank meaning candidates keyed by exact transaction id.

    The adapter deliberately does not classify bank narration itself. Historical
    narration-learning outputs can be loaded by a higher-level importer after
    their confidence/provenance is checked, then supplied here as governed
    candidates. A debit is not automatically expense and a credit is not
    automatically income.
    """
    rule = (governed_meanings or {}).get(transaction.transaction_id)
    if rule is None:
        broad = "BANK_OUTFLOW" if transaction.direction == "debit" else "BANK_INFLOW"
        return (
            PrismCandidate(
                broad,
                1.0,
                PrismDepth.MOVEMENT,
                "literal bank direction only; semantic purpose unresolved",
                f"bank:{transaction.statement_id}:{transaction.source_row}",
            ),
        )
    meaning, confidence, depth, reason = rule
    return (
        PrismCandidate(
            meaning,
            confidence,
            depth,
            reason,
            f"bank:{transaction.statement_id}:{transaction.source_row}",
        ),
    )


def disperse_bank(
    transaction: BankTransaction,
    branch: str | None = None,
    governed_meanings: Mapping[str, tuple[str, float, PrismDepth, str]] | None = None,
    prism: AdaptivePrism | None = None,
) -> PrismResult:
    engine = prism or AdaptivePrism()
    return engine.resolve(bank_observation(transaction, branch), bank_candidates(transaction, governed_meanings))


def consequence_candidate(
    meaning: str,
    confidence: float,
    reason: str,
    source_ref: str,
) -> PrismCandidate:
    """Explicit bridge for corroborated P&L consequence evidence.

    Callers must supply a consequence derived from governed reconciliation,
    owner-approved rules, or deterministic multi-source evidence. The adaptive
    prism applies its stronger consequence threshold before exposing it as a
    supported financial ray.
    """
    return PrismCandidate(
        meaning,
        confidence,
        PrismDepth.FINANCIAL_CONSEQUENCE,
        reason,
        source_ref,
    )
