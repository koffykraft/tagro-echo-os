from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class RuntimeConfig:
    environment: str
    aws_region: str
    db_secret_arn: str | None
    db_host: str | None
    db_port: int
    db_name: str | None

    @classmethod
    def from_env(cls) -> "RuntimeConfig":
        return cls(
            environment=os.getenv("ECHO_ENV", "nonprod"),
            aws_region=os.getenv("AWS_REGION", "ap-south-1"),
            db_secret_arn=os.getenv("DB_SECRET_ARN"),
            db_host=os.getenv("DB_HOST"),
            db_port=int(os.getenv("DB_PORT", "5432")),
            db_name=os.getenv("DB_NAME", "echoos"),
        )

    def database_configured(self) -> bool:
        return bool(self.db_secret_arn and self.db_host and self.db_name)
