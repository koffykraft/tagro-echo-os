from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json


def now(): return datetime.now(timezone.utc)

def canonical_hash(payload):
    return sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest()

@dataclass(frozen=True)
class SyncEnvelope:
    idempotency_key:str; device_id:str; counter_id:str; sequence:int; payload_type:str; payload:dict; created_at:datetime; payload_hash:str

class SyncQueue:
    def __init__(self): self._items={}; self._acked=set()
    def enqueue(self,idempotency_key,device_id,counter_id,sequence,payload_type,payload):
        if not idempotency_key or not device_id or not counter_id: raise ValueError('idempotency device counter required')
        if int(sequence)<0: raise ValueError('sequence must be non-negative')
        h=canonical_hash(payload)
        if idempotency_key in self._items:
            old=self._items[idempotency_key]
            if old.payload_hash!=h: raise ValueError('idempotency key reused with different payload')
            return old
        e=SyncEnvelope(idempotency_key,device_id,counter_id,int(sequence),payload_type,dict(payload),now(),h); self._items[idempotency_key]=e; return e
    def pending(self): return sorted([x for k,x in self._items.items() if k not in self._acked],key=lambda x:(x.device_id,x.sequence,x.created_at))
    def acknowledge(self,idempotency_key):
        if idempotency_key not in self._items: raise ValueError('unknown envelope')
        self._acked.add(idempotency_key)
    def is_acknowledged(self,idempotency_key): return idempotency_key in self._acked
