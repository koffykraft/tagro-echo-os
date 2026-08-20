from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from src.aws_runtime.config import RuntimeConfig


@dataclass(frozen=True)
class DatabaseSecret:
    username: str
    password: str


def _load_secret(config: RuntimeConfig) -> DatabaseSecret:
    if not config.db_secret_arn:
        raise RuntimeError("DB_SECRET_ARN is not configured")

    import boto3

    client = boto3.client("secretsmanager", region_name=config.aws_region)
    response = client.get_secret_value(SecretId=config.db_secret_arn)
    payload = json.loads(response["SecretString"])

    username = payload.get("username")
    password = payload.get("password")
    if not username or not password:
        raise RuntimeError("database secret is missing username/password")
    return DatabaseSecret(username=str(username), password=str(password))


def connect(config: RuntimeConfig):
    if not config.database_configured():
        raise RuntimeError("database runtime is not fully configured")

    import psycopg

    secret = _load_secret(config)
    return psycopg.connect(
        host=config.db_host,
        port=config.db_port,
        dbname=config.db_name,
        user=secret.username,
        password=secret.password,
        connect_timeout=5,
        sslmode="require",
    )


def probe(config: RuntimeConfig) -> Mapping[str, Any]:
    """Prove private runtime reachability without mutating business state."""
    with connect(config) as connection:
        with connection.cursor() as cursor:
            cursor.execute("select current_database(), current_user, version()")
            database, user, version = cursor.fetchone()
    return {
        "database": database,
        "user": user,
        "engine": "postgresql",
        "version": str(version),
    }


def tenant_context(config: RuntimeConfig, external_identity_ref: str) -> Mapping[str, Any] | None:
    """Resolve the authenticated principal to active Enterprise memberships and entitlements.

    This is a read-only projection. The Cognito subject is treated only as an external
    identity reference; Enterprise authority comes from server-side membership state.
    """
    if not external_identity_ref:
        return None

    with connect(config) as connection:
        principal = connection.execute(
            """
            select principal_id, display_name
            from principals
            where external_identity_ref=%s and active=true
            """,
            (external_identity_ref,),
        ).fetchone()
        if not principal:
            return None

        principal_id, display_name = principal
        memberships = connection.execute(
            """
            select m.membership_id, e.enterprise_id, e.code, e.name, m.role_code, m.tool_pack_code
            from enterprise_memberships m
            join enterprises e on e.enterprise_id=m.enterprise_id
            where m.principal_id=%s
              and m.status='active'
              and e.status='active'
              and m.valid_from <= now()
              and (m.valid_to is null or m.valid_to > now())
            order by e.code, m.role_code
            """,
            (principal_id,),
        ).fetchall()

        enterprises: list[dict[str, Any]] = []
        for membership_id, enterprise_id, code, name, role_code, tool_pack_code in memberships:
            entitlements = connection.execute(
                """
                select capability_code
                from enterprise_entitlements
                where enterprise_id=%s
                  and status='enabled'
                  and effective_from <= now()
                  and (effective_to is null or effective_to > now())
                order by capability_code
                """,
                (enterprise_id,),
            ).fetchall()
            enterprises.append(
                {
                    "membership_id": membership_id,
                    "enterprise_id": enterprise_id,
                    "enterprise_code": code,
                    "enterprise_name": name,
                    "role_code": role_code,
                    "tool_pack_code": tool_pack_code,
                    "capabilities": [row[0] for row in entitlements],
                }
            )

    return {
        "principal_id": principal_id,
        "display_name": display_name,
        "enterprises": enterprises,
    }
