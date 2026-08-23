from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

CONFIRMATION = "SYNC_OPERATIONAL_TWIN_V1"
PACKAGE_SCHEMA = "tagro.echo.canonical-master/1"
DEFAULT_SOURCE_LOCATOR = "TAGRO_AUTOMATION/price_update_2026_27/outputs/TAGRO_STIHL_BUSY_Update_One_Row_Per_Item.csv"


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=False)


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def invoke_lambda(*, profile: str, region: str, function_name: str, event: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="echo-stihl-master-") as td:
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
        if str(body.get("status") or "").lower() != "canonical_master_sync_complete":
            raise RuntimeError(f"Canonical master Lambda refused/failed batch: {body}")
        return body


def _yes(value: Any) -> bool:
    return str(value or "").strip().lower() in {"yes", "y", "true", "1"}


def _text(row: dict[str, str], key: str) -> str:
    return str(row.get(key) or "").strip()


def _price(value: str) -> str | None:
    text = str(value or "").strip().replace(",", "")
    if not text:
        return None
    return text


def build_records(csv_path: Path, effective_from: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_part: dict[str, dict[str, Any]] = {}
    source_rows = ready_rows = skipped_rows = 0
    branches: defaultdict[str, int] = defaultdict(int)

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "Branch", "Original TAGRO item name", "TAGRO display name", "BUSY item codes",
            "BUSY alias", "STIHL part number", "Official STIHL name", "Official type", "HSN",
            "GST %", "STIHL price before GST", "STIHL price incl GST", "STIHL MRP", "Ready for BUSY",
        }
        missing = sorted(required - set(reader.fieldnames or []))
        if missing:
            raise RuntimeError(f"STIHL master CSV missing columns: {missing}")

        for row in reader:
            source_rows += 1
            if not _yes(row.get("Ready for BUSY")):
                skipped_rows += 1
                continue
            part_no = _text(row, "STIHL part number")
            official_name = _text(row, "Official STIHL name")
            if not part_no or not official_name:
                skipped_rows += 1
                continue
            ready_rows += 1
            branch = _text(row, "Branch").upper()
            if branch:
                branches[branch] += 1

            record = by_part.setdefault(part_no, {
                "manufacturer": "STIHL",
                "sku": part_no,
                "model": official_name,
                "name": official_name,
                "category": _text(row, "Official type") or "UNCLASSIFIED",
                "hsn_code": _text(row, "HSN"),
                "gst_rate": _text(row, "GST %") or "0",
                "unit": "nos",
                "serial_tracked": (_text(row, "Official type").upper() == "MACHINES"),
                "aliases": [],
                "prices": [],
            })

            # Refuse inconsistent official identity instead of silently choosing one branch row.
            if (
                record["name"] != official_name
                or str(record["gst_rate"]) != (_text(row, "GST %") or "0")
                or str(record["hsn_code"]) != _text(row, "HSN")
            ):
                raise RuntimeError(f"conflicting official identity for STIHL part {part_no}")

            candidates = (
                ("tagro_original_name", _text(row, "Original TAGRO item name")),
                ("tagro_display_name", _text(row, "TAGRO display name")),
                ("busy_item_code", _text(row, "BUSY item codes")),
                ("busy_alias", _text(row, "BUSY alias")),
            )
            existing_aliases = {(a["type"], a["value"], a["branch_code"]) for a in record["aliases"]}
            for alias_type, alias_value in candidates:
                key = (alias_type, alias_value, branch)
                if alias_value and key not in existing_aliases:
                    record["aliases"].append({"type": alias_type, "value": alias_value, "branch_code": branch})
                    existing_aliases.add(key)

            price_candidates = (
                ("official_before_gst", _price(row.get("STIHL price before GST", ""))),
                ("official_incl_gst", _price(row.get("STIHL price incl GST", ""))),
                ("mrp", _price(row.get("STIHL MRP", ""))),
            )
            existing_prices = {(p["type"], p["effective_from"], p.get("branch_code", "")): p["amount"] for p in record["prices"]}
            for price_type, amount in price_candidates:
                if amount is None:
                    continue
                key = (price_type, effective_from, "")
                prior = existing_prices.get(key)
                if prior is not None and prior != amount:
                    raise RuntimeError(f"conflicting {price_type} for STIHL part {part_no}: {prior} vs {amount}")
                if prior is None:
                    record["prices"].append({
                        "type": price_type,
                        "amount": amount,
                        "effective_from": effective_from,
                        "branch_code": "",
                    })
                    existing_prices[key] = amount

    records = sorted(by_part.values(), key=lambda item: item["sku"])
    stats = {
        "source_rows": source_rows,
        "ready_rows": ready_rows,
        "skipped_rows": skipped_rows,
        "unique_products": len(records),
        "branch_ready_rows": dict(sorted(branches.items())),
        "aliases": sum(len(item["aliases"]) for item in records),
        "prices": sum(len(item["prices"]) for item in records),
    }
    return records, stats


def sync(args: argparse.Namespace) -> dict[str, Any]:
    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise FileNotFoundError(f"STIHL master CSV not found: {csv_path}")
    digest = sha256_file(csv_path)
    records, stats = build_records(csv_path, args.effective_from)
    responses: list[dict[str, Any]] = []

    for offset in range(0, len(records), args.batch_size):
        batch = records[offset:offset + args.batch_size]
        fingerprint = hashlib.sha256(stable_json(batch).encode("utf-8")).hexdigest()[:16]
        sync_run_id = f"stihl-master:{digest[:12]}:{offset}:{fingerprint}"
        event = {
            "confirm": CONFIRMATION,
            "enterprise_id": args.enterprise_id,
            "package": {
                "schema": PACKAGE_SCHEMA,
                "sync_run_id": sync_run_id,
                "source_system": "TAGRO_STIHL_MASTER",
                "source_locator": args.source_locator,
                "source_class": "reviewed_canonical_product_price_master",
                "source_as_of": args.effective_from,
                "provenance": {
                    "source_sha256": digest,
                    "effective_from": args.effective_from,
                    "offset": offset,
                    "mode": "canonical_master_no_planar",
                },
                "records": batch,
            },
        }
        if args.dry_run:
            responses.append({"status": "dry_run", "sync_run_id": sync_run_id, "record_count": len(batch)})
        else:
            responses.append(invoke_lambda(
                profile=args.profile,
                region=args.region,
                function_name=args.function_name,
                event=event,
            ))

    return {
        "schema": "tagro.echo.stihl-master-sync-summary/1",
        "source": str(csv_path),
        "source_sha256": digest,
        "effective_from": args.effective_from,
        "stats": stats,
        "batches": len(responses),
        "inserted": sum(int(r.get("inserted") or 0) for r in responses),
        "updated": sum(int(r.get("updated") or 0) for r in responses),
        "unchanged": sum(int(r.get("unchanged") or 0) for r in responses),
        "aliases_upserted": sum(int(r.get("aliases_upserted") or 0) for r in responses),
        "prices_upserted": sum(int(r.get("prices_upserted") or 0) for r in responses),
        "dry_run": bool(args.dry_run),
        "planar_projection": False,
    }


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Deduplicate reviewed TAGRO/STIHL item rows and admit canonical products/prices into ECHO.")
    p.add_argument("--csv", required=True)
    p.add_argument("--effective-from", required=True, help="Authoritative price effective date (YYYY-MM-DD); never inferred from filename.")
    p.add_argument("--enterprise-id", required=True)
    p.add_argument("--profile", default="tagro-echo-nonprod")
    p.add_argument("--region", default="ap-south-1")
    p.add_argument("--function-name", default="echo-nonprod-observation-import")
    p.add_argument("--source-locator", default=DEFAULT_SOURCE_LOCATOR)
    p.add_argument("--batch-size", type=int, default=500)
    p.add_argument("--dry-run", action="store_true")
    return p


if __name__ == "__main__":
    print(json.dumps(sync(parser().parse_args()), indent=2, default=str))
