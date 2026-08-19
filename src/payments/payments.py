from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4


def D(v): return Decimal(str(v))
def _id(p): return f'{p}-{uuid4().hex[:12]}'

@dataclass(frozen=True)
class Payment:
    payment_id: str
    branch_id: str
    customer_id: str | None
    received_at: datetime
    method: str
    amount: Decimal
    reference: str = ''
    actor_id: str = ''
    status: str = 'received'

@dataclass(frozen=True)
class PaymentAllocation:
    allocation_id: str
    payment_id: str
    target_type: str
    target_id: str
    amount: Decimal
    allocated_at: datetime
    actor_id: str

class PaymentStore:
    def __init__(self): self.payments={}; self.allocations=[]
    def receive(self,branch_id,customer_id,method,amount,actor_id,reference=''):
        amount=D(amount)
        if amount<=0: raise ValueError('payment amount must be positive')
        if method not in {'cash','upi','card','bank_transfer','cheque','other'}: raise ValueError('invalid payment method')
        if not actor_id.strip(): raise ValueError('actor_id is required')
        p=Payment(_id('pay'),branch_id,customer_id,datetime.now(timezone.utc),method,amount,reference,actor_id)
        self.payments[p.payment_id]=p; return p
    def allocate(self,payment_id,target_type,target_id,amount,actor_id):
        if payment_id not in self.payments: raise ValueError('payment does not exist')
        if target_type not in {'sale','invoice','service_job','customer_account'}: raise ValueError('invalid allocation target')
        amount=D(amount)
        if amount<=0: raise ValueError('allocation must be positive')
        if self.unallocated(payment_id)<amount: raise ValueError('allocation exceeds unallocated payment')
        a=PaymentAllocation(_id('pal'),payment_id,target_type,target_id,amount,datetime.now(timezone.utc),actor_id)
        self.allocations.append(a); return a
    def allocated(self,payment_id): return sum((x.amount for x in self.allocations if x.payment_id==payment_id),Decimal('0'))
    def unallocated(self,payment_id): return self.payments[payment_id].amount-self.allocated(payment_id)
