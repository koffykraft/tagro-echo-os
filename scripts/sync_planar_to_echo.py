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
from typing import Any, Iterable

TABLES = (
    ("entities", "entity", "entity_id"),
    ("events", "event", "event_id"),
    ("event_entities", "event_entity", None),
    ("evidence", "evidence", "evidence_id"),
    ("relationships", "relationship", "relationship_id"),
)
CONFIRMATION = "SYNC_OPERATIONAL_TWIN_V1"
PACKAGE_SCHEMA = "tagro.planar-export/1"


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=False)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".incoming")
    tmp.write_text(json.dumps(value, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def row_records(db: sqlite3.Connection, table: str, record_type: str, start: int, limit: int) -> list[dict[str, Any]]:
    db.row_factory = sqlite3.Row
    rows = db.execute(f'SELECT rowid AS _rowid, * FROM "{table}" ORDER BY rowid LIMIT ? OFFSET ?', (limit, start)).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        payload = {k: row[k] for k in row.keys() if k != "_rowid"}
        source_record_id = _source_record_id(table, payload, int(row["_rowid"]))
        branch = str(payload.get("branch") or payload.get("branch_code") or "").strip().upper()
        effective = payload.get("event_date") or payload.get("start_date") or None
        result.append({
            "domain": "planar",
            "record_type": record_type,
            "source_record_id": source_record_id,
            "branch_code": branch,
            "source_effective_at": effective,
            "payload": payload,
            "provenance": {"planar_table": table, "planar_rowid": int(row["_rowid"])},
        })
    return result


def _source_record_id(table: str, payload: dict[str, Any], rowid: int) -> str:
    if table == "entities":
        return str(payload.get("entity_id") or f"row:{rowid}")
    if table == "events":
        return str(payload.get("event_id") or f"row:{rowid}")
    if table == "evidence":
        return str(payload.get("evidence_id") or f"row:{rowid}")
    if table == "relationships":
        return str(payload.get("relationship_id") or f"row:{rowid}")
    if table == "event_entities":
        return sha256_text("|".join(str(payload.get(x) or "") for x in ("event_id", "entity_id", "role")))[:32]
    return f"row:{rowid}"


def table_count(db: sqlite3.Connection, table: str) -> int:
    return int(db.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0])


def invoke_lambda(*, profile: str, region: str, function_name: str, event: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="echo-planar-") as td:
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
        if str(body.get("status") or "").lower() not in {
            "operational_twin_planar_sync_complete", "operational_twin_sync_complete"
        }:
            raise RuntimeError(f"Ingestion Lambda refused/failed batch: {body}")
        return body


def sync(args: argparse.Namespace) -> dict[str, Any]:
    database = Path(args.database)
    manifest_path = Path(args.manifest)
    checkpoint_path = Path(args.checkpoint)
    if not database.exists():
        raise FileNotFoundError(f"Planar database not found: {database}")
    manifest = load_json(manifest_path)
    warehouse_run_id = str(manifest.get("run_id") or database.stat().st_mtime_ns)
    database_sha = str(((manifest.get("databases") or {}).get("planar") or {}).get("sha256") or "")
    source_as_of = str(manifest.get("completed_at") or "") or None
    source_locator = str(database)

    checkpoint = load_json(checkpoint_path)
    if checkpoint.get("warehouse_run_id") != warehouse_run_id or checkpoint.get("database_sha256") != database_sha:
        checkpoint = {
            "schema": "tagro.echo.planar-sync-checkpoint/1",
            "warehouse_run_id": warehouse_run_id,
            "database_sha256": database_sha,
            "started_at": utcnow(),
            "tables": {},
        }

    summary: dict[str, Any] = {
        "warehouse_run_id": warehouse_run_id,
        "database_sha256": database_sha,
        "source_as_of": source_as_of,
        "tables": {},
    }

    db = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
    try:
        integrity = db.execute("pragma quick_check").fetchone()[0]
        if str(integrity).lower() != "ok":
            raise RuntimeError(f"planar.sqlite integrity check failed: {integrity}")
        for table, record_type, _ in TABLES:
            if not db.execute("select 1 from sqlite_master where type='table' and name=?", (table,)).fetchone():
                raise RuntimeError(f"required Planar table missing: {table}")
            total = table_count(db, table)
            table_state = checkpoint["tables"].setdefault(table, {"offset": 0, "total": total, "complete": False})
            if int(table_state.get("total") or total) != total:
                table_state = {"offset": 0, "total": total, "complete": False}
                checkpoint["tables"][table] = table_state
            offset = int(table_state.get("offset") or 0)
            sent = 0
            while offset < total:
                records = row_records(db, table, record_type, offset, args.batch_size)
                if not records:
                    break
                batch_fingerprint = sha256_text(stable_json(records))[:16]
                sync_run_id = f"planar:{warehouse_run_id}:{table}:{offset}:{batch_fingerprint}"
                event = {
                    "confirm": CONFIRMATION,
                    "enterprise_id": args.enterprise_id,
                    "package": {
                        "schema": PACKAGE_SCHEMA,
                        "sync_run_id": sync_run_id,
                        "source_system": "TAGRO_AWS_OS_WAREHOUSE",
                        "source_locator": source_locator,
                        "source_class": "warehouse_derived_historical_backbone",
                        "source_as_of": source_as_of,
                        "provenance": {
                            "warehouse_run_id": warehouse_run_id,
                            "planar_sha256": database_sha,
                            "manifest": str(manifest_path),
                            "table": table,
                            "offset": offset,
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
                    table_state.update({
                        "offset": offset,
                        "total": total,
                        "last_sync_run_id": sync_run_id,
                        "last_response": response,
                        "updated_at": utcnow(),
                        "complete": offset >= total,
                    })
                    checkpoint["updated_at"] = utcnow()
                    save_json(checkpoint_path, checkpoint)
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
    p = argparse.ArgumentParser(description="Checkpointed TAGRO Planar warehouse -> ECHO PostgreSQL sync")
    p.add_argument("--database", required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--enterprise-id", required=True)
    p.add_argument("--profile", default=os.environ.get("ECHO_AWS_PROFILE", "tagro-echo-nonprod"))
    p.add_argument("--region", default=os.environ.get("AWS_REGION", "ap-south-1"))
    p.add_argument("--function-name", default="echo-nonprod-observation-import")
    p.add_argument("--batch-size", type=int, default=500)
    p.add_argument("--dry-run", action="store_true")
    return p


if __name__ == "__main__":
    args = parser().parse_args()
    if args.batch_size < 1 or args.batch_size > 1000:
        raise SystemExit("--batch-size must be 1..1000")
    print(json.dumps(sync(args), indent=2, default=str))
