from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from src.aws_runtime.config import RuntimeConfig
from src.aws_runtime.database import connect

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "schemas" / "migrations" / "nonprod_v0_1_manifest.json"


def _git_blob_sha(content: bytes) -> str:
    header = f"blob {len(content)}\0".encode("utf-8")
    return hashlib.sha1(header + content).hexdigest()


def _load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _ensure_ledger(conn: Any) -> None:
    conn.execute(
        """
        create table if not exists echo_schema_migrations (
          migration_id text primary key,
          git_blob_sha text not null,
          source_path text not null,
          applied_at timestamptz not null default now()
        )
        """
    )
    conn.commit()


def apply() -> None:
    config = RuntimeConfig.from_env()
    manifest = _load_manifest()
    migrations = manifest.get("migrations", [])
    completed: set[str] = set()

    with connect(config) as conn:
        _ensure_ledger(conn)

        rows = conn.execute(
            "select migration_id, git_blob_sha from echo_schema_migrations"
        ).fetchall()
        recorded = {row[0]: row[1] for row in rows}

        for migration in migrations:
            migration_id = migration["id"]
            source_path = migration["path"]
            admitted_sha = migration["git_blob_sha"]
            dependencies = migration.get("depends_on", [])

            missing_dependencies = [dep for dep in dependencies if dep not in completed and dep not in recorded]
            if missing_dependencies:
                raise RuntimeError(
                    f"migration {migration_id} has unapplied dependencies: {missing_dependencies}"
                )

            sql_path = ROOT / source_path
            content = sql_path.read_bytes()
            actual_sha = _git_blob_sha(content)
            if actual_sha != admitted_sha:
                raise RuntimeError(
                    f"migration source drift for {migration_id}: admitted {admitted_sha}, actual {actual_sha}"
                )

            if migration_id in recorded:
                if recorded[migration_id] != admitted_sha:
                    raise RuntimeError(
                        f"migration ledger drift for {migration_id}: recorded {recorded[migration_id]}, admitted {admitted_sha}"
                    )
                completed.add(migration_id)
                print(f"SKIP {migration_id} already applied")
                continue

            sql = content.decode("utf-8")
            try:
                with conn.transaction():
                    conn.execute(sql)
                    conn.execute(
                        """
                        insert into echo_schema_migrations (migration_id, git_blob_sha, source_path)
                        values (%s, %s, %s)
                        """,
                        (migration_id, admitted_sha, source_path),
                    )
            except Exception:
                conn.rollback()
                raise

            completed.add(migration_id)
            print(f"APPLIED {migration_id}")


if __name__ == "__main__":
    apply()
