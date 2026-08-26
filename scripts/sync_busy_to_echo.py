from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TABLES = (
    "source_snapshots",
    "import_batches",
    "vouchers",
    "voucher_items",
    "voucher_ledger",
    "voucher_narration",
)
CONFIRMATION = "SYNC_OPERATIONAL_TWIN_V1"
PACKAGE_SCHEMA = "tagro.echo.busy-raw-export/1"
DEFAULT_SOURCE_LOCATOR = "TAGRO_AWS_OS_WAREHOUSE/databases/busy.sqlite"


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=False)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".incoming")
    tmp.write_text(json.dumps(value, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, path)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def table_count(db: sqlite3.Connection, table: str) -> int:
    return int(db.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0])


def primary_key_columns(db: sqlite3.Connection, table: str) -> list[str]:
    rows = db.execute(f'PRAGMA table_info("{table}")').fetchall()
    return [str(row[1]) for row in sorted(rows, key=lambda r: int(r[5] or 0)) if int(row[5] or 0) > 0]


def row_records(db: sqlite3.Connection, table: str, start: int, limit: int) -> list[dict[str, Any]]:
    db.row_factory = sqlite3.Row
    pk_cols = primary_key_columns(db, table)
    rows = db.execute(f'SELECT rowid AS _echo_rowid, * FROM "{table}" ORDER BY rowid LIMIT ? OFFSET ?', (limit, start)).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        payload = {k: row[k] for k in row.keys() if k != "_echo_rowid"}
        rowid = int(row["_echo_rowid"])
        if pk_cols and all(payload.get(c) not in (None, "") for c in pk_cols):
            identity = "|".join(f"{c}={payload[c]}" for c in pk_cols)
        else:
            identity = f"rowid={rowid}"
        branch = str(
            payload.get("branch_code")
            or payload.get("branch")
            or payload.get("material_centre")
            or payload.get("material_centre_code")
            or ""
        ).strip().upper()
        effective = (
            payload.get("voucher_date")
            or payload.get("business_date")
            or payload.get("date")
            or payload.get("source_effective_at")
            or None
        )
        updated = payload.get("updated_at") or payload.get("source_updated_at") or None
        result.append({
            "domain": "busy",
            "record_type": table,
            "source_record_id": f"{table}:{identity}",
            "branch_code": branch,
            "source_effective_at": effective,
            "source_updated_at": updated,
            "payload": payload,
            "provenance": {"busy_table": table, "busy_rowid": rowid, "primary_key_columns": pk_cols},
        })
    return result


def invoke_lambda(*, profile: str, region: str, function_name: str, event: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="echo-busy-") as td:
        root = Path(td)
        payload_path = root / "payload.json"
        response_path = root / "response.json"
        payload_path.write_text(stable_json(event), encoding="utf-8")
        cmd = [
            "aws", "lambda", "invoke",
            "--profile", profile,
            "--region", region,
            "--function-name", function_name,
            "--cli-binary-format", "raw-in-base64-out",
            "--payload", f"fileb://{payload_path}",
            str(response_path),
            "--output", "json",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise RuntimeError(f"AWS Lambda invoke failed: {proc.stderr.strip() or proc.stdout.strip()}")
        invoke_meta = json.loads(proc.stdout or "{}")
        body = json.loads(response_path.read_text(encoding="utf-8") or "{}")
        if invoke_meta.get("FunctionError"):
            raise RuntimeError(f"Ingestion Lambda FunctionError: {body}")
        if str(body.get("status") or "").lower() != "operational_twin_sync_complete":
            raise RuntimeError(f"Ingestion Lambda refused/failed BUSY batch: {body}")
        return body


def sync(args: argparse.Namespace) -> dict[str, Any]:
    database = Path(args.database)
    manifest_path = Path(args.manifest)
    checkpoint_path = Path(args.checkpoint)
    if not database.exists():
        raise FileNotFoundError(f"BUSY database not found: {database}")

    manifest = load_json(manifest_path)
    warehouse_run_id = str(manifest.get("run_id") or database.stat().st_mtime_ns)
    busy_manifest = ((manifest.get("databases") or {}).get("busy") or {})
    database_sha = str(busy_manifest.get("sha256") or "").strip().lower()
    if not database_sha:
        raise RuntimeError("warehouse manifest does not provide busy database sha256")
    actual_database_sha = sha256_file(database)
    if actual_database_sha.lower() != database_sha:
        raise RuntimeError("busy.sqlite digest does not match warehouse manifest")

    source_as_of = str(manifest.get("completed_at") or "") or None
    checkpoint = load_json(checkpoint_path)
    if checkpoint.get("warehouse_run_id") != warehouse_run_id or checkpoint.get("database_sha256") != database_sha:
        checkpoint = {
            "schema": "tagro.echo.busy-raw-sync-checkpoint/1",
            "warehouse_run_id": warehouse_run_id,
            "database_sha256": database_sha,
            "started_at": utcnow(),
            "tables": {},
        }

    summary: dict[str, Any] = {
        "warehouse_run_id": warehouse_run_id,
        "database_sha256": database_sha,
        "source_as_of": source_as_of,
        "source_locator": args.source_locator,
        "mode": "raw_busy_foundation",
        "planar_projection": False,
        "tables": {},
    }

    db = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
    try:
        integrity = db.execute("pragma quick_check").fetchone()[0]
        if str(integrity).lower() != "ok":
            raise RuntimeError(f"busy.sqlite integrity check failed: {integrity}")
        for table in TABLES:
            if not db.execute("select 1 from sqlite_master where type='table' and name=?", (table,)).fetchone():
                raise RuntimeError(f"required BUSY table missing: {table}")
            total = table_count(db, table)
            state = checkpoint["tables"].setdefault(table, {"offset": 0, "total": total, "complete": False})
            if int(state.get("total") or total) != total:
                state = {"offset": 0, "total": total, "complete": False}
                checkpoint["tables"][table] = state
            offset = int(state.get("offset") or 0)
            sent = 0
            while offset < total:
                records = row_records(db, table, offset, args.batch_size)
                if not records:
                    break
                fingerprint = sha256_text(stable_json(records))[:16]
                sync_run_id = f"busy:{warehouse_run_id}:{table}:{offset}:{fingerprint}"
                event = {
                    "confirm": CONFIRMATION,
                    "enterprise_id": args.enterprise_id,
                    "package": {
                        "schema": PACKAGE_SCHEMA,
                        "sync_run_id": sync_run_id,
                        "source_system": "TAGRO_AWS_OS_WAREHOUSE_BUSY",
                        "source_locator": args.source_locator,
                        "source_class": "busy_normalized_historical_foundation",
                        "source_as_of": source_as_of,
                        "provenance": {
                            "warehouse_run_id": warehouse_run_id,
                            "busy_sha256": database_sha,
                            "table": table,
                            "offset": offset,
                            "mode": "raw_as_is_no_planar",
                        },
                        "records": records,
                    },
                }
                if args.dry_run:
                    response = {"status": "dry_run", "record_count": len(records), "sync_run_id": sync_run_id}
                else:
                    response = invoke_lambda(
                        profile=args.profile,
                        region=args.region,
                        function_name=args.function_name,
                        event=event,
                    )
                offset += len(records)
                sent += len(records)
                if not args.dry_run:
                    state.update({
                        "offset": offset,
                        "total": total,
                        "last_sync_run_id": sync_run_id,
                        "last_response": response,
                        "updated_at": utcnow(),
                        "complete": offset >= total,
                    })
                    checkpoint["updated_at"] = utcnow()
                    save_json(checkpoint_path, checkpoint)
                    print(f"{table}: {offset}/{total}", flush=True)
            summary["tables"][table] = {"total": total, "offset": offset, "sent_this_run": sent, "complete": offset >= total}
    finally:
        db.close()

    if not args.dry_run:
        checkpoint["completed_at"] = utcnow()
        checkpoint["complete"] = all(bool(x.get("complete")) for x in checkpoint.get("tables", {}).values())
        save_json(checkpoint_path, checkpoint)
    summary["complete"] = all(x["complete"] for x in summary["tables"].values())
    return summary


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Checkpointed BUSY warehouse -> ECHO raw PostgreSQL foundation sync")
    p.add_argument("--database", required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--enterprise-id", required=True)
    p.add_argument("--profile", default=os.environ.get("ECHO_AWS_PROFILE", "tagro-echo-nonprod"))
    p.add_argument("--region", default=os.environ.get("AWS_REGION", "ap-south-1"))
    p.add_argument("--function-name", default="echo-nonprod-observation-import")
    p.add_argument("--source-locator", default=DEFAULT_SOURCE_LOCATOR)
    p.add_argument("--batch-size", type=int, default=500)
    p.add_argument("--dry-run", action="store_true")
    return p


if __name__ == "__main__":
    args = parser().parse_args()
    if args.batch_size < 1 or args.batch_size > 1000:
        raise SystemExit("--batch-size must be 1..1000")
    print(json.dumps(sync(args), indent=2, default=str))
