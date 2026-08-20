from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
from typing import Any, Mapping
from uuid import uuid4

from src.enterprise.registry import BusyBinding, BusyNode, EnterpriseDirectory, RegistryError
from src.repository.ports import RepositoryPort


class BusyDockError(ValueError):
    pass


class BusyOperation(str, Enum):
    MASTERS = "masters"
    TRANSACTIONS = "transactions"
    STOCK = "stock"
    BALANCES = "balances"
    LEDGERS = "ledgers"
    REPORT_CATALOGUE = "report_catalogue"
    REPORT = "report"


_REQUIRED_CAPABILITY = {
    BusyOperation.MASTERS: "masters_read",
    BusyOperation.TRANSACTIONS: "transactions_read",
    BusyOperation.STOCK: "stock_read",
    BusyOperation.BALANCES: "balances_read",
    BusyOperation.LEDGERS: "ledgers_read",
    BusyOperation.REPORT_CATALOGUE: "reports_read",
    BusyOperation.REPORT: "reports_read",
}


@dataclass(frozen=True)
class BusyRequest:
    request_id: str
    enterprise_id: str
    actor_id: str
    operation: BusyOperation
    binding_role: str = "primary_accounts"
    parameters: Mapping[str, Any] = field(default_factory=dict)
    idempotency_key: str = ""


@dataclass(frozen=True)
class BusyResult:
    request_id: str
    enterprise_id: str
    busy_node_id: str
    operation: str
    status: str
    data: Any
    source: str
    source_effective_at: str | None
    observed_at: str
    provenance: Mapping[str, Any] = field(default_factory=dict)
    stale: bool = False
    error: str | None = None


@dataclass(frozen=True)
class BusySnapshot:
    snapshot_id: str
    busy_node_id: str
    operation: str
    data: Any
    source_effective_at: str
    captured_at: str
    provenance: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BusyHandoffEnvelope:
    envelope_id: str
    request_id: str
    enterprise_id: str
    busy_node_id: str
    actor_id: str
    operation: str
    binding_role: str
    material_centre_ref: str | None
    voucher_series: Mapping[str, str]
    parameters: Mapping[str, Any]
    idempotency_key: str
    payload_hash: str
    created_at: str


@dataclass(frozen=True)
class BusyHandoffResult:
    envelope_id: str
    busy_node_id: str
    status: str
    completed_at: str
    result_ref: str | None = None
    result_hash: str | None = None
    error: str | None = None
    provenance: Mapping[str, Any] = field(default_factory=dict)


class BusyDock:
    """Multi-node BUSY accounting/finance/MIS dock.

    v1 is deliberately read-oriented. It resolves the enterprise-to-BUSY topology,
    enforces declared node capabilities, can serve last-known snapshots offline, and
    can prepare governed handoff envelopes for a local BUSY bridge when connectivity
    exists. It does not open or mutate a BUSY database itself.
    """

    SNAPSHOTS = "busy_dock.snapshots"
    HANDOFFS = "busy_dock.handoffs"
    HANDOFF_RESULTS = "busy_dock.handoff_results"

    def __init__(self, directory: EnterpriseDirectory, repository: RepositoryPort):
        self.directory = directory
        self.repository = repository

    def resolve(self, enterprise_id: str, binding_role: str = "primary_accounts") -> tuple[BusyNode, BusyBinding]:
        binding = self.directory.resolve_busy_binding(enterprise_id, binding_role)
        if not binding:
            raise BusyDockError(f"no active BUSY binding for role: {binding_role}")
        node = self.directory.get_busy_node(binding.busy_node_id)
        if not node or not node.active:
            raise BusyDockError("BUSY node unavailable or inactive")
        return node, binding

    def capabilities(self, enterprise_id: str, binding_role: str = "primary_accounts") -> dict[str, Any]:
        node, binding = self.resolve(enterprise_id, binding_role)
        latest = self.latest_snapshot_for_node(node.busy_node_id)
        return {
            "enterprise_id": enterprise_id,
            "busy_node_id": node.busy_node_id,
            "node_code": node.code,
            "company_ref": node.company_ref,
            "binding_role": binding.binding_role,
            "material_centre_ref": binding.material_centre_ref,
            "voucher_series": dict(binding.voucher_series),
            "capabilities": list(node.capabilities),
            "latest_snapshot_effective_at": latest.source_effective_at if latest else None,
            "online_state": "not_asserted_by_registry",
        }

    def read_offline(self, request: BusyRequest) -> BusyResult:
        self._validate_request(request)
        node, _ = self.resolve(request.enterprise_id, request.binding_role)
        self._require_capability(node, request.operation)
        snapshot = self.latest_snapshot(node.busy_node_id, request.operation.value)
        now = self._now()
        if not snapshot:
            return BusyResult(
                request_id=request.request_id,
                enterprise_id=request.enterprise_id,
                busy_node_id=node.busy_node_id,
                operation=request.operation.value,
                status="unavailable",
                data=None,
                source="offline_snapshot",
                source_effective_at=None,
                observed_at=now,
                provenance={"reason": "no_snapshot"},
                stale=True,
                error="No offline BUSY snapshot is available for this node and operation.",
            )
        return BusyResult(
            request_id=request.request_id,
            enterprise_id=request.enterprise_id,
            busy_node_id=node.busy_node_id,
            operation=request.operation.value,
            status="success",
            data=snapshot.data,
            source="offline_snapshot",
            source_effective_at=snapshot.source_effective_at,
            observed_at=now,
            provenance={
                "snapshot_id": snapshot.snapshot_id,
                "captured_at": snapshot.captured_at,
                **dict(snapshot.provenance),
            },
            stale=True,
        )

    def save_snapshot(self, snapshot: BusySnapshot) -> None:
        node = self.directory.get_busy_node(snapshot.busy_node_id)
        if not node:
            raise BusyDockError("cannot save snapshot for unknown BUSY node")
        if snapshot.operation not in {x.value for x in BusyOperation}:
            raise BusyDockError("unsupported BUSY snapshot operation")
        key = self._snapshot_key(snapshot.busy_node_id, snapshot.operation, snapshot.snapshot_id)
        self.repository.put(self.SNAPSHOTS, key, asdict(snapshot))

    def latest_snapshot(self, busy_node_id: str, operation: str) -> BusySnapshot | None:
        matches = [
            self._snapshot_from(row)
            for row in self.repository.list(self.SNAPSHOTS)
            if row.get("busy_node_id") == busy_node_id and row.get("operation") == operation
        ]
        if not matches:
            return None
        return max(matches, key=lambda x: (x.source_effective_at, x.captured_at, x.snapshot_id))

    def latest_snapshot_for_node(self, busy_node_id: str) -> BusySnapshot | None:
        matches = [
            self._snapshot_from(row)
            for row in self.repository.list(self.SNAPSHOTS)
            if row.get("busy_node_id") == busy_node_id
        ]
        if not matches:
            return None
        return max(matches, key=lambda x: (x.source_effective_at, x.captured_at, x.snapshot_id))

    def prepare_handoff(self, request: BusyRequest) -> BusyHandoffEnvelope:
        self._validate_request(request)
        node, binding = self.resolve(request.enterprise_id, request.binding_role)
        self._require_capability(node, request.operation)
        payload = {
            "request_id": request.request_id,
            "enterprise_id": request.enterprise_id,
            "busy_node_id": node.busy_node_id,
            "actor_id": request.actor_id,
            "operation": request.operation.value,
            "binding_role": request.binding_role,
            "material_centre_ref": binding.material_centre_ref,
            "voucher_series": dict(binding.voucher_series),
            "parameters": dict(request.parameters),
            "idempotency_key": request.idempotency_key,
        }
        payload_hash = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()

        existing = self.repository.get(self.HANDOFFS, request.idempotency_key)
        if existing:
            if existing.get("payload_hash") != payload_hash:
                raise BusyDockError("idempotency key replayed with different BUSY payload")
            return self._handoff_from(existing)

        envelope = BusyHandoffEnvelope(
            envelope_id=f"busy-env-{uuid4().hex[:16]}",
            payload_hash=payload_hash,
            created_at=self._now(),
            **payload,
        )
        self.repository.put(self.HANDOFFS, request.idempotency_key, asdict(envelope))
        return envelope

    def record_handoff_result(self, result: BusyHandoffResult) -> None:
        envelope = None
        for row in self.repository.list(self.HANDOFFS):
            if row.get("envelope_id") == result.envelope_id:
                envelope = row
                break
        if not envelope:
            raise BusyDockError("handoff result references unknown envelope")
        self.repository.put(self.HANDOFF_RESULTS, result.envelope_id, asdict(result))

    def handoff_result(self, envelope_id: str) -> BusyHandoffResult | None:
        row = self.repository.get(self.HANDOFF_RESULTS, envelope_id)
        return BusyHandoffResult(**dict(row)) if row else None

    def _validate_request(self, request: BusyRequest) -> None:
        if not request.request_id.strip():
            raise BusyDockError("request_id is required")
        if not request.enterprise_id.strip():
            raise BusyDockError("enterprise_id is required")
        if not request.actor_id.strip():
            raise BusyDockError("actor_id is required")
        if not request.idempotency_key.strip():
            raise BusyDockError("idempotency_key is required")
        try:
            self.directory.get_enterprise(request.enterprise_id)
        except RegistryError as exc:
            raise BusyDockError(str(exc)) from exc
        if not self.directory.get_enterprise(request.enterprise_id):
            raise BusyDockError("enterprise does not exist")

    @staticmethod
    def _require_capability(node: BusyNode, operation: BusyOperation) -> None:
        required = _REQUIRED_CAPABILITY[operation]
        if required not in node.capabilities:
            raise BusyDockError(f"BUSY node does not declare capability: {required}")

    @staticmethod
    def _snapshot_key(node_id: str, operation: str, snapshot_id: str) -> str:
        return f"{node_id}:{operation}:{snapshot_id}"

    @staticmethod
    def _snapshot_from(row: Mapping[str, Any]) -> BusySnapshot:
        return BusySnapshot(**dict(row))

    @staticmethod
    def _handoff_from(row: Mapping[str, Any]) -> BusyHandoffEnvelope:
        return BusyHandoffEnvelope(**dict(row))

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
