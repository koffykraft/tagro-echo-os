from __future__ import annotations
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Sequence
from uuid import uuid4


def _id(prefix): return f'{prefix}-{uuid4().hex[:12]}'

@dataclass(frozen=True)
class MachineRecord:
    machine_id: str
    customer_id: str
    product_id: str | None
    model: str
    serial_no: str = ''
    purchase_date: str = ''
    source: str = 'staff_confirmed'

@dataclass(frozen=True)
class ServiceEvent:
    event_id: str
    job_id: str
    occurred_at: datetime
    event_type: str
    note: str
    actor_id: str

@dataclass(frozen=True)
class ServiceJob:
    job_id: str
    branch_id: str
    customer_id: str
    machine_id: str
    opened_at: datetime
    complaint: str
    status: str = 'received'
    observations: str = ''
    estimate_id: str | None = None

class ServiceStore:
    def __init__(self): self.machines={}; self.jobs={}; self.events=[]
    def add_machine(self,m:MachineRecord):
        if m.machine_id in self.machines: raise ValueError('machine already exists')
        if not m.model.strip(): raise ValueError('model is required')
        self.machines[m.machine_id]=m; return m
    def open_job(self,branch_id,customer_id,machine_id,complaint,actor_id):
        if machine_id not in self.machines: raise ValueError('machine does not exist')
        if not complaint.strip(): raise ValueError('complaint is required')
        j=ServiceJob(_id('job'),branch_id,customer_id,machine_id,datetime.now(timezone.utc),complaint)
        self.jobs[j.job_id]=j; self._event(j.job_id,'received',complaint,actor_id); return j
    def update_status(self,job_id,status,note,actor_id):
        allowed={'received','inspecting','estimate_waiting','approved','repairing','ready','delivered','cancelled'}
        if status not in allowed: raise ValueError('invalid service status')
        j=self.jobs[job_id]; j=replace(j,status=status); self.jobs[job_id]=j; self._event(job_id,'status.'+status,note,actor_id); return j
    def add_observation(self,job_id,observation,actor_id):
        if not observation.strip(): raise ValueError('observation is required')
        j=self.jobs[job_id]; merged=(j.observations+'\n'+observation).strip(); j=replace(j,observations=merged); self.jobs[job_id]=j; self._event(job_id,'observation',observation,actor_id); return j
    def history_for_machine(self,machine_id):
        jobs=[j for j in self.jobs.values() if j.machine_id==machine_id]; ids={j.job_id for j in jobs}
        return {'machine':self.machines[machine_id],'jobs':jobs,'events':[e for e in self.events if e.job_id in ids]}
    def _event(self,job_id,event_type,note,actor_id): self.events.append(ServiceEvent(_id('sev'),job_id,datetime.now(timezone.utc),event_type,note,actor_id))
