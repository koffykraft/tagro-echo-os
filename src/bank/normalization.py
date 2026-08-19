from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

@dataclass(frozen=True)
class BankTransaction:
    transaction_id: str
    statement_id: str
    source_file: str
    source_row: int
    account_id: str
    transaction_date: date
    value_date: date | None
    direction: str
    amount: Decimal
    narration: str
    reference: str = ''
    balance: Decimal | None = None

    def validate(self):
        if self.direction not in {'credit','debit'}: raise ValueError('direction must be credit or debit')
        if self.amount <= 0: raise ValueError('amount must be positive')
        if self.source_row < 1: raise ValueError('source_row must be positive')
        if not self.source_file.strip(): raise ValueError('source_file is required')
        if not self.narration.strip(): raise ValueError('narration is required')


def candidate_reconciliation(bank_tx:BankTransaction, amount, business_date, tolerance_days=2):
    """Return evidence for review, never an automatic payment match."""
    amount=Decimal(str(amount))
    delta=abs((bank_tx.transaction_date-business_date).days)
    return {
        'amount_equal': bank_tx.amount==amount,
        'date_within_tolerance': delta<=tolerance_days,
        'date_delta_days': delta,
        'bank_transaction_id': bank_tx.transaction_id,
        'status': 'candidate_only_not_confirmed'
    }
