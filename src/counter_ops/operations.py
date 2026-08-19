from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4


def D(v): return Decimal(str(v))
def _id(p): return f'{p}-{uuid4().hex[:12]}'
def now(): return datetime.now(timezone.utc)

@dataclass
class PurchaseOrder:
    po_id:str; branch_id:str; supplier_id:str; lines:list[dict]; created_by:str
    created_at:datetime=field(default_factory=now); status:str='draft'; approved_by:str=''; approved_at:datetime|None=None

@dataclass
class Transfer:
    transfer_id:str; from_branch_id:str; to_branch_id:str; lines:list[dict]; requested_by:str
    requested_at:datetime=field(default_factory=now); status:str='requested'; dispatched_by:str=''; dispatched_at:datetime|None=None; received_by:str=''; received_at:datetime|None=None

@dataclass
class StockCount:
    count_id:str; branch_id:str; created_by:str; created_at:datetime=field(default_factory=now); status:str='open'; lines:list[dict]=field(default_factory=list); finalized_by:str=''; finalized_at:datetime|None=None

class CounterOpsStore:
    def __init__(self): self.purchase_orders={}; self.transfers={}; self.counts={}
    def create_po(self,branch_id,supplier_id,lines,actor_id):
        if not branch_id or not supplier_id or not actor_id or not lines: raise ValueError('branch supplier lines actor required')
        po=PurchaseOrder(_id('po'),branch_id,supplier_id,[dict(x) for x in lines],actor_id); self.purchase_orders[po.po_id]=po; return po
    def approve_po(self,po_id,actor_id):
        po=self.purchase_orders[po_id]
        if po.status!='draft': raise ValueError('only draft PO can be approved')
        po.status='approved'; po.approved_by=actor_id; po.approved_at=now(); return po
    def request_transfer(self,from_branch,to_branch,lines,actor_id):
        if from_branch==to_branch: raise ValueError('transfer branches must differ')
        if not lines: raise ValueError('transfer lines required')
        t=Transfer(_id('trf'),from_branch,to_branch,[dict(x) for x in lines],actor_id); self.transfers[t.transfer_id]=t; return t
    def dispatch_transfer(self,transfer_id,actor_id):
        t=self.transfers[transfer_id]
        if t.status!='requested': raise ValueError('transfer not requestable for dispatch')
        t.status='dispatched'; t.dispatched_by=actor_id; t.dispatched_at=now(); return t
    def receive_transfer(self,transfer_id,actor_id):
        t=self.transfers[transfer_id]
        if t.status!='dispatched': raise ValueError('only dispatched transfer can be received')
        t.status='received'; t.received_by=actor_id; t.received_at=now(); return t
    def start_count(self,branch_id,actor_id):
        c=StockCount(_id('cnt'),branch_id,actor_id); self.counts[c.count_id]=c; return c
    def record_count_line(self,count_id,product_id,counted_qty,system_qty,evidence_ids=()):
        c=self.counts[count_id]
        if c.status!='open': raise ValueError('count is not open')
        row={'product_id':product_id,'counted_qty':D(counted_qty),'system_qty':D(system_qty),'variance':D(counted_qty)-D(system_qty),'evidence_ids':list(evidence_ids)}
        c.lines=[x for x in c.lines if x['product_id']!=product_id]+[row]; return row
    def finalize_count(self,count_id,actor_id):
        c=self.counts[count_id]
        if c.status!='open': raise ValueError('count already finalized')
        c.status='finalized'; c.finalized_by=actor_id; c.finalized_at=now(); return {'count':c,'variances':[x for x in c.lines if x['variance']!=0],'stock_mutated':False}
