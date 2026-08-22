from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from uuid import uuid4


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


SERVICE_STATUSES = (
    "received",
    "inspecting",
    "estimate_waiting",
    "approved",
    "repairing",
    "ready",
    "delivered",
    "cancelled",
)

# Normal staff flow is intentionally simple and explicit. An owner may override a
# transition, but that exception is recorded as evidence rather than silently
# weakening the workflow.
SERVICE_TRANSITIONS = {
    "received": {"inspecting", "cancelled"},
    "inspecting": {"estimate_waiting", "approved", "repairing", "cancelled"},
    "estimate_waiting": {"approved", "cancelled"},
    "approved": {"repairing", "cancelled"},
    "repairing": {"ready", "estimate_waiting", "cancelled"},
    "ready": {"delivered", "repairing", "cancelled"},
    "delivered": set(),
    "cancelled": set(),
}


@dataclass(frozen=True)
class MachineRecord:
    machine_id: str
    customer_id: str
    product_id: str | None
    model: str
    serial_no: str = ""
    purchase_date: str = ""
    source: str = "staff_confirmed"


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
    status: str = "received"
    observations: str = ""
    estimate_id: str | None = None


class ServiceStore:
    """Small in-memory service workflow model used by the proving layer.

    It deliberately separates reception evidence, observations and status
    transitions. No diagnosis, estimate approval or completion is inferred from
    free text. Owner overrides are explicit events so later persistence can keep
    the same audit semantics.
    """

    def __init__(self):
        self.machines: dict[str, MachineRecord] = {}
        self.jobs: dict[str, ServiceJob] = {}
        self.events: list[ServiceEvent] = []

    def add_machine(self, machine: MachineRecord) -> MachineRecord:
        if machine.machine_id in self.machines:
            raise ValueError("machine already exists")
        if not machine.customer_id.strip():
            raise ValueError("customer_id is required")
        if not machine.model.strip():
            raise ValueError("model is required")
        self.machines[machine.machine_id] = machine
        return machine

    def open_job(
        self,
        branch_id: str,
        customer_id: str,
        machine_id: str,
        complaint: str,
        actor_id: str,
    ) -> ServiceJob:
        if machine_id not in self.machines:
            raise ValueError("machine does not exist")
        machine = self.machines[machine_id]
        if customer_id != machine.customer_id:
            raise ValueError("customer does not own the selected machine record")
        if not branch_id.strip():
            raise ValueError("branch_id is required")
        if not actor_id.strip():
            raise ValueError("actor_id is required")
        if not complaint.strip():
            raise ValueError("complaint is required")
        job = ServiceJob(
            _id("job"),
            branch_id,
            customer_id,
            machine_id,
            datetime.now(timezone.utc),
            complaint.strip(),
        )
        self.jobs[job.job_id] = job
        self._event(job.job_id, "received", complaint.strip(), actor_id)
        return job

    def update_status(
        self,
        job_id: str,
        status: str,
        note: str,
        actor_id: str,
        *,
        owner_override: bool = False,
    ) -> ServiceJob:
        if status not in SERVICE_STATUSES:
            raise ValueError("invalid service status")
        if job_id not in self.jobs:
            raise ValueError("service job does not exist")
        if not actor_id.strip():
            raise ValueError("actor_id is required")
        job = self.jobs[job_id]
        if status == job.status:
            raise ValueError("service job is already in that status")
        allowed = SERVICE_TRANSITIONS[job.status]
        if status not in allowed and not owner_override:
            raise ValueError(f"invalid service transition: {job.status} -> {status}")
        previous = job.status
        job = replace(job, status=status)
        self.jobs[job_id] = job
        event_type = "owner_override.status" if status not in allowed else "status"
        event_note = f"{previous} -> {status}"
        if note.strip():
            event_note += f": {note.strip()}"
        self._event(job_id, event_type, event_note, actor_id)
        return job

    def add_observation(self, job_id: str, observation: str, actor_id: str) -> ServiceJob:
        if job_id not in self.jobs:
            raise ValueError("service job does not exist")
        if not actor_id.strip():
            raise ValueError("actor_id is required")
        if not observation.strip():
            raise ValueError("observation is required")
        job = self.jobs[job_id]
        merged = (job.observations + "\n" + observation.strip()).strip()
        job = replace(job, observations=merged)
        self.jobs[job_id] = job
        self._event(job_id, "observation", observation.strip(), actor_id)
        return job

    def history_for_machine(self, machine_id: str) -> dict[str, object]:
        if machine_id not in self.machines:
            raise ValueError("machine does not exist")
        jobs = sorted(
            (job for job in self.jobs.values() if job.machine_id == machine_id),
            key=lambda job: job.opened_at,
        )
        job_ids = {job.job_id for job in jobs}
        events = sorted(
            (event for event in self.events if event.job_id in job_ids),
            key=lambda event: event.occurred_at,
        )
        return {"machine": self.machines[machine_id], "jobs": jobs, "events": events}

    def _event(self, job_id: str, event_type: str, note: str, actor_id: str) -> None:
        self.events.append(
            ServiceEvent(
                _id("sev"),
                job_id,
                datetime.now(timezone.utc),
                event_type,
                note,
                actor_id,
            )
        )
