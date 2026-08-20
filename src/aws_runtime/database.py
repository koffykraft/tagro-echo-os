from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

import boto3
import psycopg

from src.aws_runtime.config import RuntimeConfig


@dataclass(frozen=True)
class DatabaseSecret:
    username: str
    password: str


def _load_secret(config: RuntimeConfig) -> DatabaseSecret:
    if not config.db_secret_arn:
        raise RuntimeError("DB_SECRET_ARN is not configured")

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
