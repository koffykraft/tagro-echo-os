from __future__ import annotations

from typing import Any

from src.aws_runtime.config import RuntimeConfig
from src.aws_runtime.database import connect


def load_tenant_context(config: RuntimeConfig, external_identity_ref: str) -> dict[str, Any] | None:
    """Resolve authenticated identity to active Enterprise memberships and entitlements."""
    identity_ref = str(external_identity_ref or "").strip()
    if not identity_ref:
        return None

    with connect(config) as conn:
        principal = conn.execute(
            """
            select principal_id, display_name
            from principals
            where external_identity_ref=%s and active=true
            """,
            (identity_ref,),
        ).fetchone()
        if not principal:
            return None

        memberships = conn.execute(
            """
            select e.enterprise_id, e.code, e.name, m.role_code, m.tool_pack_code
            from enterprise_memberships m
            join enterprises e on e.enterprise_id=m.enterprise_id
            where m.principal_id=%s
              and m.status='active'
              and e.status='active'
              and m.valid_from <= now()
              and (m.valid_to is null or m.valid_to > now())
            order by e.code, m.role_code
            """,
            (principal[0],),
        ).fetchall()

        enterprises: list[dict[str, Any]] = []
        for enterprise_id, code, name, role_code, tool_pack_code in memberships:
            capabilities = conn.execute(
                """
                select distinct ee.capability_code
                from enterprise_entitlements ee
                join capabilities c on c.capability_code=ee.capability_code
                where ee.enterprise_id=%s
                  and ee.status='enabled'
                  and c.active=true
                  and ee.effective_from <= now()
                  and (ee.effective_to is null or ee.effective_to > now())
                order by ee.capability_code
                """,
                (enterprise_id,),
            ).fetchall()
            enterprises.append(
                {
                    "enterprise_id": enterprise_id,
                    "code": code,
                    "name": name,
                    "role_code": role_code,
                    "tool_pack_code": tool_pack_code,
                    "capabilities": [row[0] for row in capabilities],
                }
            )

    return {
        "principal_id": principal[0],
        "display_name": principal[1],
        "enterprises": enterprises,
    }
