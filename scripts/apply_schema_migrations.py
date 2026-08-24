from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from src.aws_runtime.config import RuntimeConfig
from src.aws_runtime.database import connect

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "schemas" / "migrations" / "nonprod_v0_3_manifest.json"


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


def _start_index(migrations: list[dict[str, Any]], start_at: str | None) -> int:
    if start_at is None:
        return 0
    for index, migration in enumerate(migrations):
        if migration.get("id") == start_at:
            return index
    raise RuntimeError(f"migration start id is not present in manifest: {start_at}")


def _verify_recorded_baseline(
    migrations: list[dict[str, Any]],
    recorded: dict[str, str],
    start_index: int,
    start_at: str | None,
) -> set[str]:
    completed: set[str] = set()
    if start_index == 0:
        return completed

    for migration in migrations[:start_index]:
        migration_id = migration["id"]
        admitted_sha = migration["git_blob_sha"]
        recorded_sha = recorded.get(migration_id)
        if recorded_sha is None:
            raise RuntimeError(
                f"migration baseline incomplete before {start_at}: missing {migration_id}"
            )
        if recorded_sha != admitted_sha:
            raise RuntimeError(
                f"migration baseline drift for {migration_id}: recorded {recorded_sha}, admitted {admitted_sha}"
            )
        completed.add(migration_id)

    return completed


def apply(*, start_at: str | None = None) -> None:
    config = RuntimeConfig.from_env()
    manifest = _load_manifest()
    migrations = manifest.get("migrations", [])
    start_index = _start_index(migrations, start_at)

    with connect(config) as conn:
        _ensure_ledger(conn)

        rows = conn.execute(
            "select migration_id, git_blob_sha from echo_schema_migrations"
        ).fetchall()
        recorded = {row[0]: row[1] for row in rows}
        completed = _verify_recorded_baseline(
            migrations, recorded, start_index, start_at
        )

        for migration in migrations[start_index:]:
            migration_id = migration["id"]
            source_path = migration["path"]
            admitted_sha = migration["git_blob_sha"]
            dependencies = migration.get("depends_on", [])

            missing_dependencies = [
                dep for dep in dependencies if dep not in completed and dep not in recorded
            ]
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
