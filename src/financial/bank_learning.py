from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from src.bank.normalization import BankTransaction

from .prism import PrismCandidate, PrismDepth


_CANON = {
    "RECIEPT": "RECEIPT",
    "RECIEPTS": "RECEIPT",
    "RECEIEPT": "RECEIPT",
    "RECEIPTS": "RECEIPT",
    "PAYMENTS": "PAYMENT",
    "REVERASL": "REVERSAL",
}


def clean_label(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip().upper())
    return _CANON.get(text, text)


def narration_signature(value: object) -> str:
    """Normalize changing bank references using the historical 2023-26 logic."""
    text = str(value or "").upper()
    text = re.sub(r"\b\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}\b", " DATE ", text)
    text = re.sub(r"\b(?:UTR|RRN|REF|IMPS|NEFT|RTGS|UPI)?[A-Z0-9/-]{10,}\b", " ID ", text)
    text = re.sub(r"\d+", " # ", text)
    return re.sub(r"[^A-Z#]+", " ", text).strip()


def direction_code(transaction: BankTransaction) -> str:
    return "D" if transaction.direction == "debit" else "C"


@dataclass(frozen=True)
class BankNarrationRule:
    narration_signature: str
    direction: str
    meaning: str
    confidence: float
    examples: int
    safe_action: str
    source_ref: str
    depth: PrismDepth = PrismDepth.BUSINESS_MEANING
    years_seen: tuple[str, ...] = ()
    branches_seen: tuple[str, ...] = ()

    def validate(self) -> None:
        if self.direction not in {"D", "C"}:
            raise ValueError("direction must be D or C")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if self.examples < 1:
            raise ValueError("examples must be positive")
        if not self.source_ref.strip():
            raise ValueError("source_ref is required")
        if self.depth >= PrismDepth.FINANCIAL_CONSEQUENCE:
            raise ValueError("historical narration rules cannot directly assert financial consequence")


@dataclass(frozen=True)
class BankLearningMatch:
    rule: BankNarrationRule | None
    candidate: PrismCandidate | None
    review_required: bool
    reason: str


def match_bank_rule(
    transaction: BankTransaction,
    rules: Iterable[BankNarrationRule],
) -> BankLearningMatch:
    """Match a bank narration against learned historical patterns.

    This carries forward the prior rule-library discipline: only exact normalized
    signature + direction rules marked `auto-fill` may act without review.  Even
    then, the result is capped below FINANCIAL_CONSEQUENCE.  Narration learning
    teaches meaning; it cannot by itself make a debit an expense or a credit
    income.
    """
    transaction.validate()
    sig = narration_signature(transaction.narration)
    code = direction_code(transaction)
    matches: list[BankNarrationRule] = []
    for rule in rules:
        rule.validate()
        if narration_signature(rule.narration_signature) == sig and rule.direction == code:
            matches.append(rule)
    if not matches:
        return BankLearningMatch(None, None, True, "no historical narration rule matched")

    rule = sorted(matches, key=lambda r: (-r.confidence, -r.examples, r.meaning))[0]
    safe = rule.safe_action.strip().lower() == "auto-fill"
    candidate = PrismCandidate(
        meaning=clean_label(rule.meaning),
        confidence=rule.confidence,
        depth=rule.depth,
        reason=f"historical narration rule; examples={rule.examples}; safe_action={rule.safe_action}",
        source_ref=rule.source_ref,
    )
    return BankLearningMatch(
        rule=rule,
        candidate=candidate,
        review_required=not safe,
        reason=(
            "safe historical rule may teach Prism meaning"
            if safe
            else "historical rule is suggestion-only and requires review"
        ),
    )


def learned_bank_candidates(
    transaction: BankTransaction,
    rules: Iterable[BankNarrationRule],
) -> tuple[PrismCandidate, ...]:
    match = match_bank_rule(transaction, rules)
    if match.candidate is None:
        return ()
    if match.review_required:
        # Preserve suggestion evidence below the normal descent threshold so it
        # cannot silently become a resolved narrower ray.
        c = match.candidate
        return (
            PrismCandidate(
                c.meaning,
                min(c.confidence, 0.79),
                c.depth,
                c.reason + "; review required",
                c.source_ref,
            ),
        )
    return (match.candidate,)
