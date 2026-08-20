from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Iterable, Mapping

from src.repository.ports import RepositoryPort


class RegistryError(ValueError):
    pass


@dataclass(frozen=True)
class Enterprise:
    enterprise_id: str
    code: str
    name: str
    enterprise_type: str = "counter"
    parent_enterprise_id: str | None = None
    legal_identity_ref: str | None = None
    district: str | None = None
    region: str | None = None
    active: bool = True
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class EnterpriseUser:
    assignment_id: str
    user_id: str
    enterprise_id: str
    roles: tuple[str, ...] = ()
    tool_packs: tuple[str, ...] = ()
    active: bool = True


@dataclass(frozen=True)
class BusyNode:
    busy_node_id: str
    code: str
    name: str
    company_ref: str
    node_type: str = "company"
    company_data_locator: str | None = None
    active: bool = True
    capabilities: tuple[str, ...] = (
        "masters_read",
        "transactions_read",
        "reports_read",
    )
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class BusyBinding:
    binding_id: str
    enterprise_id: str
    busy_node_id: str
    binding_role: str = "primary_accounts"
    material_centre_ref: str | None = None
    voucher_series: Mapping[str, str] = field(default_factory=dict)
    active: bool = True


class EnterpriseDirectory:
    """Executable enterprise identity, user-access and BUSY topology registry.

    Enterprise identity is independent from organizational hierarchy and from BUSY.
    Any number of users may be assigned to the same enterprise/material centre, each
    with separate roles and tool packs. BUSY nodes are registered engines. Bindings
    map an enterprise to a BUSY node, optional material centre, and voucher series.

    The registry deliberately stores no BUSY credentials and performs no BUSY I/O.
    """

    ENTERPRISES = "enterprise_directory.enterprises"
    USERS = "enterprise_directory.users"
    BUSY_NODES = "enterprise_directory.busy_nodes"
    BUSY_BINDINGS = "enterprise_directory.busy_bindings"

    def __init__(self, repository: RepositoryPort):
        self.repository = repository

    def register_enterprise(self, enterprise: Enterprise) -> None:
        self._require_nonempty(enterprise.enterprise_id, "enterprise_id")
        self._require_nonempty(enterprise.code, "enterprise code")
        self._require_nonempty(enterprise.name, "enterprise name")
        self._require_unique_code(self.ENTERPRISES, enterprise.code, "enterprise", enterprise.enterprise_id)

        if enterprise.parent_enterprise_id:
            if enterprise.parent_enterprise_id == enterprise.enterprise_id:
                raise RegistryError("enterprise cannot be its own parent")
            if not self.get_enterprise(enterprise.parent_enterprise_id):
                raise RegistryError("parent enterprise does not exist")
            if self._would_create_cycle(enterprise.enterprise_id, enterprise.parent_enterprise_id):
                raise RegistryError("enterprise hierarchy cycle rejected")

        self.repository.put(self.ENTERPRISES, enterprise.enterprise_id, self._record(enterprise))

    def register_user(self, assignment: EnterpriseUser) -> None:
        self._require_nonempty(assignment.assignment_id, "assignment_id")
        self._require_nonempty(assignment.user_id, "user_id")
        if not self.get_enterprise(assignment.enterprise_id):
            raise RegistryError("enterprise does not exist")
        self.repository.put(self.USERS, assignment.assignment_id, self._record(assignment))

    def register_busy_node(self, node: BusyNode) -> None:
        self._require_nonempty(node.busy_node_id, "busy_node_id")
        self._require_nonempty(node.code, "BUSY node code")
        self._require_nonempty(node.name, "BUSY node name")
        self._require_nonempty(node.company_ref, "BUSY company_ref")
        self._require_unique_code(self.BUSY_NODES, node.code, "BUSY node", node.busy_node_id)
        self.repository.put(self.BUSY_NODES, node.busy_node_id, self._record(node))

    def bind_busy(self, binding: BusyBinding) -> None:
        self._require_nonempty(binding.binding_id, "binding_id")
        if not self.get_enterprise(binding.enterprise_id):
            raise RegistryError("enterprise does not exist")
        if not self.get_busy_node(binding.busy_node_id):
            raise RegistryError("BUSY node does not exist")

        for existing in self.busy_bindings_for_enterprise(binding.enterprise_id, active_only=False):
            if (
                existing.binding_id != binding.binding_id
                and existing.binding_role == binding.binding_role
                and existing.active
                and binding.active
            ):
                raise RegistryError(
                    f"active BUSY binding role already exists for enterprise: {binding.binding_role}"
                )

        self.repository.put(self.BUSY_BINDINGS, binding.binding_id, self._record(binding))

    def get_enterprise(self, enterprise_id: str) -> Enterprise | None:
        row = self.repository.get(self.ENTERPRISES, enterprise_id)
        return self._enterprise_from(row) if row else None

    def get_busy_node(self, busy_node_id: str) -> BusyNode | None:
        row = self.repository.get(self.BUSY_NODES, busy_node_id)
        return self._busy_node_from(row) if row else None

    def enterprises(self, active_only: bool = True) -> list[Enterprise]:
        rows = [self._enterprise_from(r) for r in self.repository.list(self.ENTERPRISES)]
        return [r for r in rows if r.active or not active_only]

    def children_of(self, enterprise_id: str, active_only: bool = True) -> list[Enterprise]:
        return [
            e for e in self.enterprises(active_only=active_only)
            if e.parent_enterprise_id == enterprise_id
        ]

    def ancestors_of(self, enterprise_id: str) -> list[Enterprise]:
        current = self.get_enterprise(enterprise_id)
        if not current:
            raise RegistryError("enterprise does not exist")
        result: list[Enterprise] = []
        seen: set[str] = set()
        while current.parent_enterprise_id:
            parent_id = current.parent_enterprise_id
            if parent_id in seen:
                raise RegistryError("stored enterprise hierarchy cycle detected")
            seen.add(parent_id)
            parent = self.get_enterprise(parent_id)
            if not parent:
                raise RegistryError("stored parent enterprise is missing")
            result.append(parent)
            current = parent
        return result

    def users_for_enterprise(self, enterprise_id: str, active_only: bool = True) -> list[EnterpriseUser]:
        rows = [self._user_from(r) for r in self.repository.list(self.USERS)]
        return [
            r for r in rows
            if r.enterprise_id == enterprise_id and (r.active or not active_only)
        ]

    def assignments_for_user(self, user_id: str, active_only: bool = True) -> list[EnterpriseUser]:
        rows = [self._user_from(r) for r in self.repository.list(self.USERS)]
        return [r for r in rows if r.user_id == user_id and (r.active or not active_only)]

    def user_has_role(self, user_id: str, enterprise_id: str, role: str) -> bool:
        wanted = role.strip().casefold()
        return any(
            wanted in {r.strip().casefold() for r in assignment.roles}
            for assignment in self.assignments_for_user(user_id)
            if assignment.enterprise_id == enterprise_id
        )

    def user_has_tool(self, user_id: str, enterprise_id: str, tool_pack: str) -> bool:
        wanted = tool_pack.strip().casefold()
        return any(
            wanted in {t.strip().casefold() for t in assignment.tool_packs}
            for assignment in self.assignments_for_user(user_id)
            if assignment.enterprise_id == enterprise_id
        )

    def busy_nodes(self, active_only: bool = True) -> list[BusyNode]:
        rows = [self._busy_node_from(r) for r in self.repository.list(self.BUSY_NODES)]
        return [r for r in rows if r.active or not active_only]

    def busy_bindings_for_enterprise(
        self, enterprise_id: str, active_only: bool = True
    ) -> list[BusyBinding]:
        rows = [self._binding_from(r) for r in self.repository.list(self.BUSY_BINDINGS)]
        return [
            r for r in rows
            if r.enterprise_id == enterprise_id and (r.active or not active_only)
        ]

    def enterprises_for_busy_node(
        self, busy_node_id: str, active_only: bool = True
    ) -> list[Enterprise]:
        ids = {
            b.enterprise_id
            for b in self._all_bindings(active_only=active_only)
            if b.busy_node_id == busy_node_id
        }
        return [e for e in self.enterprises(active_only=active_only) if e.enterprise_id in ids]

    def resolve_busy_binding(self, enterprise_id: str, binding_role: str = "primary_accounts") -> BusyBinding | None:
        matches = [
            b for b in self.busy_bindings_for_enterprise(enterprise_id)
            if b.binding_role == binding_role
        ]
        if len(matches) > 1:
            raise RegistryError("multiple active BUSY bindings found for same role")
        return matches[0] if matches else None

    def _all_bindings(self, active_only: bool = True) -> list[BusyBinding]:
        rows = [self._binding_from(r) for r in self.repository.list(self.BUSY_BINDINGS)]
        return [r for r in rows if r.active or not active_only]

    def _would_create_cycle(self, enterprise_id: str, proposed_parent_id: str) -> bool:
        current_id: str | None = proposed_parent_id
        seen: set[str] = set()
        while current_id:
            if current_id == enterprise_id:
                return True
            if current_id in seen:
                return True
            seen.add(current_id)
            current = self.get_enterprise(current_id)
            if not current:
                return False
            current_id = current.parent_enterprise_id
        return False

    def _require_unique_code(self, collection: str, code: str, label: str, own_id: str) -> None:
        normalized = code.strip().casefold()
        for row in self.repository.list(collection):
            if str(row.get("code", "")).strip().casefold() == normalized:
                current_id = row.get("enterprise_id") or row.get("busy_node_id")
                if current_id != own_id:
                    raise RegistryError(f"duplicate {label} code: {code}")

    @staticmethod
    def _require_nonempty(value: str, label: str) -> None:
        if not value or not value.strip():
            raise RegistryError(f"{label} is required")

    @staticmethod
    def _record(value) -> dict:
        row = asdict(value)
        for key, item in list(row.items()):
            if isinstance(item, tuple):
                row[key] = list(item)
        return row

    @staticmethod
    def _enterprise_from(row: Mapping) -> Enterprise:
        return Enterprise(**dict(row))

    @staticmethod
    def _user_from(row: Mapping) -> EnterpriseUser:
        data = dict(row)
        data["roles"] = tuple(data.get("roles", ()))
        data["tool_packs"] = tuple(data.get("tool_packs", ()))
        return EnterpriseUser(**data)

    @staticmethod
    def _busy_node_from(row: Mapping) -> BusyNode:
        data = dict(row)
        data["capabilities"] = tuple(data.get("capabilities", ()))
        return BusyNode(**data)

    @staticmethod
    def _binding_from(row: Mapping) -> BusyBinding:
        return BusyBinding(**dict(row))
