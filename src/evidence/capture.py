from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from uuid import uuid4


def _id(p): return f'{p}-{uuid4().hex[:12]}'
def now(): return datetime.now(timezone.utc)

@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id:str; branch_id:str; source_type:str; content_hash:str; mime_type:str; captured_at:datetime; actor_id:str; source_ref:str=''; note:str=''

@dataclass(frozen=True)
class InferenceProposal:
    proposal_id:str; evidence_id:str; proposal_type:str; payload:dict; confidence:float|None; created_at:datetime; provider_ref:str=''; status:str='proposed'

@dataclass(frozen=True)
class AcceptedObservation:
    observation_id:str; proposal_id:str; evidence_id:str; payload:dict; accepted_at:datetime; accepted_by:str

class EvidenceStore:
    SOURCE_TYPES={'photo','text','shelf','machine','document','audio','barcode'}
    def __init__(self): self.evidence={}; self.proposals={}; self.accepted={}
    def capture(self,branch_id,source_type,content_bytes,mime_type,actor_id,source_ref='',note=''):
        if source_type not in self.SOURCE_TYPES: raise ValueError('invalid evidence source type')
        if not actor_id: raise ValueError('actor required')
        h=sha256(content_bytes).hexdigest(); e=EvidenceRecord(_id('evd'),branch_id,source_type,h,mime_type,now(),actor_id,source_ref,note); self.evidence[e.evidence_id]=e; return e
    def propose(self,evidence_id,proposal_type,payload,confidence=None,provider_ref=''):
        if evidence_id not in self.evidence: raise ValueError('evidence does not exist')
        if confidence is not None and not 0<=float(confidence)<=1: raise ValueError('confidence must be 0..1')
        p=InferenceProposal(_id('prp'),evidence_id,proposal_type,dict(payload),None if confidence is None else float(confidence),now(),provider_ref); self.proposals[p.proposal_id]=p; return p
    def accept(self,proposal_id,actor_id):
        if not actor_id: raise ValueError('actor required')
        p=self.proposals[proposal_id]
        if proposal_id in self.accepted: raise ValueError('proposal already accepted')
        a=AcceptedObservation(_id('obs'),p.proposal_id,p.evidence_id,dict(p.payload),now(),actor_id); self.accepted[proposal_id]=a; return a
    def operational_observations(self): return list(self.accepted.values())
