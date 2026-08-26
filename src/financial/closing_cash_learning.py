from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Iterable, Mapping


class ClosingCashKind(str, Enum):
    SALES = "sales"
    EXPENSE = "expense"


@dataclass(frozen=True)
class ClosingCashEvidenceRow:
    branch: str
    business_date: str
    kind: ClosingCashKind
    amount: Decimal
    particulars: str
    narration: str = ""
    source_ref: str = ""
    source_row: int | None = None


@dataclass(frozen=True)
class LearningRule:
    fragment: str
    semantic_class: str
    confidence: float
    source_ref: str
    branch: str | None = None
    kind: ClosingCashKind | None = None


@dataclass(frozen=True)
class LearningSuggestion:
    semantic_class: str
    confidence: float
    reason: str
    rule_source: str | None
    requires_review: bool


@dataclass(frozen=True)
class ConsolidatedClosingCashRow:
    evidence_key: str
    branch: str
    business_date: str
    kind: ClosingCashKind
    amount: Decimal
    particulars: str
    narration: str
    source_ref: str
    source_row: int | None


def _norm(value: object) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def evidence_key(row: ClosingCashEvidenceRow) -> str:
    """Stable consolidation key modelled on the existing AccountFetcher workbook.

    The key deliberately preserves branch/date/type/amount/particulars.  It is an
    evidence identity, not a business-truth identity; duplicate-looking rows are
    only collapsed when this complete evidence key agrees.
    """
    kind = "S" if row.kind == ClosingCashKind.SALES else "E"
    return "|".join(
        [
            row.branch.strip().upper(),
            row.business_date,
            kind,
            format(Decimal(row.amount), "f"),
            str(row.particulars or "").strip(),
        ]
    )


def consolidate(rows: Iterable[ClosingCashEvidenceRow]) -> tuple[ConsolidatedClosingCashRow, ...]:
    seen: set[str] = set()
    result: list[ConsolidatedClosingCashRow] = []
    for row in rows:
        key = evidence_key(row)
        if key in seen:
            continue
        seen.add(key)
        result.append(
            ConsolidatedClosingCashRow(
                evidence_key=key,
                branch=row.branch.strip().upper(),
                business_date=row.business_date,
                kind=row.kind,
                amount=Decimal(row.amount),
                particulars=str(row.particulars or "").strip(),
                narration=str(row.narration or "").strip(),
                source_ref=row.source_ref,
                source_row=row.source_row,
            )
        )
    return tuple(result)


# These are suggestion families only. They never become financial classification
# without an owner/governance-approved rule in evidence_adapters.py.
GENERIC_PATTERNS: tuple[tuple[str, float, tuple[str, ...]], ...] = (
    ("FOOD_EXPENSE", 0.90, ("food", "tea", "coffee", "lunch", "breakfast")),
    ("OFFICE_EXPENSE", 0.86, ("office", "electric", "water", "internet", "phone", "print", "xerox")),
    ("SERVICE_CENTER_EXPENSE", 0.86, ("workshop", "welding", "repair", "service center")),
    ("VEHICLE_EXPENSE", 0.86, ("vehicle", "diesel", "petrol", "puncture", "tyre")),
    ("TRAVEL_EXPENSE", 0.82, ("travel", "bus", "train", "auto", "taxi", "fare")),
    ("COURIER_FREIGHT", 0.86, ("courier", "freight", "parcel", "transport", "lorry")),
    ("SALARY", 0.90, ("salary", "wages", "staff pay")),
    ("RENT", 0.90, ("rent",)),
)

CASH_BOX_WORDS = (
    "gst cash",
    "service cash",
    "spare cash",
    "stihl cash",
    "cash box",
    "cash changed",
    "cash change",
    "rent cash",
)
BANK_WORDS = ("bank", "gpay", "google pay", "paytm", "upi", "hdfc", "sbi", "icici", "neft", "rtgs", "deposit", "transfer")
OWNER_WORDS = ("thomas", "estate", "home", "drawing", "drawings", "owner")


def suggest(row: ClosingCashEvidenceRow, learned_rules: Iterable[LearningRule] = ()) -> LearningSuggestion:
    raw = _norm(row.particulars)
    branch = row.branch.strip().upper()

    # First teacher: owner/AI corrected historical fragments.  This mirrors the
    # LEARNING EXP / LEARNING SALES sheets but keeps source and confidence.
    candidates: list[LearningRule] = []
    for rule in learned_rules:
        frag = _norm(rule.fragment)
        if not frag or frag not in raw:
            continue
        if rule.branch and rule.branch.strip().upper() != branch:
            continue
        if rule.kind and rule.kind != row.kind:
            continue
        candidates.append(rule)
    if candidates:
        rule = max(candidates, key=lambda r: (r.confidence, len(_norm(r.fragment))))
        conf = min(0.99, max(0.0, float(rule.confidence)))
        return LearningSuggestion(rule.semantic_class, conf, f"learned fragment: {_norm(rule.fragment)}", rule.source_ref, conf < 0.90)

    # High-value branch language seen in the historical prototype.
    if branch == "MDM" and raw == "kanya chitty":
        return LearningSuggestion("CHITTY", 0.96, "historical MDM branch wording", None, False)
    if branch in {"MDM", "NDD"} and raw == "service":
        return LearningSuggestion("CASH_BOX_MOVEMENT", 0.94, f"historical {branch} service-cash wording", None, False)
    if branch == "NDD" and (raw == "rent" or "rent shop" in raw):
        return LearningSuggestion("CASH_BOX_MOVEMENT", 0.94, "historical NDD rent-cash wording", None, False)
    if branch == "PKM" and raw in {"ku cash", "stihl purchase", "ku purchase"}:
        return LearningSuggestion("CASH_BOX_MOVEMENT", 0.92, "historical PKM cash-box wording", None, False)
    if branch == "SKT" and raw.startswith("tmb c a") and "deposited" in raw:
        return LearningSuggestion("BANK_OR_TRANSFER", 0.94, "historical SKT TMB deposit wording", None, False)

    if row.kind == ClosingCashKind.SALES:
        if any(word in raw for word in CASH_BOX_WORDS):
            return LearningSuggestion("CASH_BOX_MOVEMENT", 0.82, "sales row with cash-box wording", None, True)
        if any(word in raw for word in BANK_WORDS):
            return LearningSuggestion("BANK_OR_TRANSFER", 0.78, "sales row with bank/digital wording", None, True)
        if "service" in raw or "labour" in raw or "labor" in raw:
            return LearningSuggestion("SERVICE_INCOME", 0.78, "sales row with service wording", None, True)
        return LearningSuggestion("DIRECT_SALES", 0.74, "default sales suggestion", None, True)

    if any(word in raw for word in CASH_BOX_WORDS):
        return LearningSuggestion("CASH_BOX_MOVEMENT", 0.80, "expense row with cash-box wording", None, True)
    if any(word in raw for word in BANK_WORDS):
        return LearningSuggestion("BANK_OR_TRANSFER", 0.78, "expense row with bank/digital wording", None, True)
    if any(word in raw for word in OWNER_WORDS):
        return LearningSuggestion("OWNER_DRAWING_OR_OWNER_USE", 0.78, "owner/home/estate wording", None, True)
    for semantic, confidence, words in GENERIC_PATTERNS:
        if any(word in raw for word in words):
            return LearningSuggestion(semantic, confidence, f"keyword suggestion: {semantic}", None, confidence < 0.90)
    if "purchase" in raw or "local purchase" in raw or "bought" in raw:
        return LearningSuggestion("LOCAL_PURCHASE", 0.72, "purchase wording", None, True)
    return LearningSuggestion("UNCLASSIFIED_EXPENSE", 0.42, "no governed/learning rule matched", None, True)


def build_review_queue(
    rows: Iterable[ClosingCashEvidenceRow],
    learned_rules: Iterable[LearningRule] = (),
    min_auto_confidence: float = 0.90,
) -> tuple[tuple[ClosingCashEvidenceRow, LearningSuggestion], ...]:
    queue = []
    for row in rows:
        suggestion = suggest(row, learned_rules)
        if suggestion.requires_review or suggestion.confidence < min_auto_confidence:
            queue.append((row, suggestion))
    return tuple(queue)


def learned_rule_map(rules: Iterable[LearningRule]) -> Mapping[str, LearningRule]:
    """Expose a deterministic rule inventory for audit/reporting."""
    return {f"{(r.branch or '*').upper()}|{(r.kind.value if r.kind else '*')}|{_norm(r.fragment)}": r for r in rules}
