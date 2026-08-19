from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4


def D(v): return Decimal(str(v))
def _id(): return 'cash-'+uuid4().hex[:12]

@dataclass(frozen=True)
class ClosingCash:
    closing_id: str
    branch_id: str
    business_date: date
    opening_cash: Decimal
    cash_sales: Decimal
    other_cash_in: Decimal
    cash_expenses: Decimal
    cash_deposits_or_transfers: Decimal
    declared_closing: Decimal
    recorded_at: datetime
    actor_id: str
    note: str = ''
    @property
    def expected_closing(self): return self.opening_cash+self.cash_sales+self.other_cash_in-self.cash_expenses-self.cash_deposits_or_transfers
    @property
    def variance(self): return self.declared_closing-self.expected_closing


def create_closing(branch_id,business_date,opening_cash,cash_sales,other_cash_in,cash_expenses,cash_deposits_or_transfers,declared_closing,actor_id,note=''):
    values=[opening_cash,cash_sales,other_cash_in,cash_expenses,cash_deposits_or_transfers,declared_closing]
    if any(D(x)<0 for x in values): raise ValueError('cash fields cannot be negative')
    if not actor_id.strip(): raise ValueError('actor_id is required')
    return ClosingCash(_id(),branch_id,business_date,*[D(x) for x in values],datetime.now(timezone.utc),actor_id,note)
