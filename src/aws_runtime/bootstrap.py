from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence
from uuid import UUID, uuid5

from src.aws_runtime.config import RuntimeConfig
from src.aws_runtime.database import connect

BOOTSTRAP_NAMESPACE = UUID("8ad01cee-b66c-4df8-8c2d-7dfda630d04b")
CONFIRMATION = "BOOTSTRAP_NONPROD_ENTERPRISE_V0_1"


@dataclass(frozen=True)
class BootstrapRequest:
    enterprise_code: str
    enterprise_name: str
    owner_external_identity_ref: str
    owner_display_name: str
    capabilities: tuple[str, ...]
    owner_email: str | None = None


def _clean_code(value: Any) -> str:
    return str(value or "").strip().upper()


def validate_request(event: Mapping[str, Any]) -> BootstrapRequest:
    if event.get("confirm") != CONFIRMATION:
        raise ValueError("explicit_confirmation_required")

    enterprise_code = _clean_code(event.get("enterprise_code"))
    enterprise_name = str(event.get("enterprise_name") or "").strip()
    owner_external_identity_ref = str(event.get("owner_external_identity_ref") or "").strip()
    owner_display_name = str(event.get("owner_display_name") or "Owner").strip()
    owner_email = str(event.get("owner_email") or "").strip().lower() or None
    raw_capabilities = event.get("capabilities") or []

    if not enterprise_code or len(enterprise_code) > 40:
        raise ValueError("invalid_enterprise_code")
    if not enterprise_name or len(enterprise_name) > 160:
        raise ValueError("invalid_enterprise_name")
    if not owner_external_identity_ref or len(owner_external_identity_ref) > 200:
        raise ValueError("invalid_owner_external_identity_ref")
    if owner_email is not None and (len(owner_email) > 254 or "@" not in owner_email):
        raise ValueError("invalid_owner_email")
    if not isinstance(raw_capabilities, Sequence) or isinstance(raw_capabilities, (str, bytes)):
        raise ValueError("invalid_capabilities")

    capabilities = tuple(dict.fromkeys(_clean_code(item) for item in raw_capabilities if _clean_code(item)))
    if not capabilities:
        raise ValueError("at_least_one_capability_required")
    if len(capabilities) > 64 or any(len(code) > 64 for code in capabilities):
        raise ValueError("invalid_capabilities")

    return BootstrapRequest(
        enterprise_code=enterprise_code,
        enterprise_name=enterprise_name,
        owner_external_identity_ref=owner_external_identity_ref,
        owner_display_name=owner_display_name,
        capabilities=capabilities,
        owner_email=owner_email,
    )


def _stable_id(kind: str, value: str) -> str:
    return str(uuid5(BOOTSTRAP_NAMESPACE, f"{kind}:{value}"))


def bootstrap(config: RuntimeConfig, request: BootstrapRequest) -> dict[str, Any]:
    if config.environment != "nonprod":
        raise RuntimeError("bootstrap_is_nonprod_only")

    enterprise_id = _stable_id("enterprise", request.enterprise_code)
    principal_id = _stable_id("principal", request.owner_external_identity_ref)
    membership_id = _stable_id("membership", f"{enterprise_id}:{principal_id}:OWNER")
    user_id = _stable_id("user", f"{enterprise_id}:{principal_id}") if request.owner_email else None

    with connect(config) as conn:
        with conn.transaction():
            conn.execute(
                """
                insert into enterprises (enterprise_id, code, name, status, created_at, data_residency_region)
                values (%s, %s, %s, 'active', now(), %s)
                on conflict (enterprise_id) do nothing
                """,
                (enterprise_id, request.enterprise_code, request.enterprise_name, config.aws_region),
            )
            enterprise = conn.execute(
                "select enterprise_id, code, name, status from enterprises where enterprise_id=%s",
                (enterprise_id,),
            ).fetchone()
            if not enterprise or enterprise[1] != request.enterprise_code or enterprise[2] != request.enterprise_name:
                raise RuntimeError("enterprise_bootstrap_drift")

            conn.execute(
                """
                insert into principals (principal_id, principal_type, display_name, external_identity_ref, active, created_at)
                values (%s, 'human', %s, %s, true, now())
                on conflict (principal_id) do nothing
                """,
                (principal_id, request.owner_display_name, request.owner_external_identity_ref),
            )
            principal = conn.execute(
                "select principal_id, external_identity_ref, active from principals where principal_id=%s",
                (principal_id,),
            ).fetchone()
            if not principal or principal[1] != request.owner_external_identity_ref or principal[2] is not True:
                raise RuntimeError("principal_bootstrap_drift")

            conn.execute(
                """
                insert into enterprise_memberships
                  (membership_id, enterprise_id, principal_id, role_code, tool_pack_code, status, valid_from)
                values (%s, %s, %s, 'OWNER', 'OWNER_CONTROL', 'active', now())
                on conflict (membership_id) do nothing
                """,
                (membership_id, enterprise_id, principal_id),
            )

            # The operational runtime deliberately requires a separate active users row.
            # Create it only when an explicit email is supplied to this private NonProd
            # bootstrap; never invent an email from the Cognito subject or display name.
            if request.owner_email and user_id:
                conn.execute(
                    """
                    insert into users (user_id, enterprise_id, principal_id, name, email, role, branch_id, active)
                    values (%s, %s, %s, %s, %s, 'OWNER', null, true)
                    on conflict (user_id) do nothing
                    """,
                    (user_id, enterprise_id, principal_id, request.owner_display_name, request.owner_email),
                )
                user = conn.execute(
                    "select user_id,email,role,active from users where user_id=%s and enterprise_id=%s and principal_id=%s",
                    (user_id, enterprise_id, principal_id),
                ).fetchone()
                if not user or user[1] != request.owner_email or str(user[2]).upper() != "OWNER" or user[3] is not True:
                    raise RuntimeError("owner_user_bootstrap_drift")

            for capability_code in request.capabilities:
                conn.execute(
                    """
                    insert into capabilities (capability_code, name, capability_class, description, active)
                    values (%s, %s, 'business', 'Bootstrap-admitted capability', true)
                    on conflict (capability_code) do nothing
                    """,
                    (capability_code, capability_code.replace('_', ' ').title()),
                )
                entitlement_id = _stable_id("entitlement", f"{enterprise_id}:{capability_code}")
                conn.execute(
                    """
                    insert into enterprise_entitlements
                      (entitlement_id, enterprise_id, capability_code, status, effective_from, configuration_json)
                    values (%s, %s, %s, 'enabled', now(), '{}')
                    on conflict (entitlement_id) do nothing
                    """,
                    (entitlement_id, enterprise_id, capability_code),
                )

        enabled = conn.execute(
            """
            select capability_code
            from enterprise_entitlements
            where enterprise_id=%s and status='enabled'
            order by capability_code
            """,
            (enterprise_id,),
        ).fetchall()

    return {
        "status": "bootstrap_complete",
        "enterprise_id": enterprise_id,
        "enterprise_code": request.enterprise_code,
        "principal_id": principal_id,
        "membership_id": membership_id,
        "user_id": user_id,
        "role_code": "OWNER",
        "enabled_capabilities": [row[0] for row in enabled],
    }
