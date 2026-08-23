from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
import tempfile
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Mapping

CONFIRMATION = "SYNC_OPERATIONAL_TWIN_V1"
PACKAGE_SCHEMA = "tagro.echo.canonical-master/1"
DEFAULT_SOURCE_LOCATOR = "TAGRO_AUTOMATION/safe_base/master_data/latest/stihl_prices_june_2026.json"


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=False)


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _part(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]+", "", _text(value).upper())


def _decimal(value: Any) -> Decimal | None:
    text = _text(value).replace(",", "")
    if not text:
        return None
    try:
        return Decimal(text).normalize()
    except InvalidOperation as exc:
        raise RuntimeError(f"invalid numeric value: {value!r}") from exc


def _decimal_text(value: Decimal | None) -> str:
    if value is None:
        return ""
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _split_codes(value: Any) -> list[str]:
    return [part.strip() for part in re.split(r"\s*\|\s*", _text(value)) if part.strip()]


def _add_alias(record: dict[str, Any], alias_type: str, value: Any, branch: str = "") -> None:
    alias_value = _text(value)
    if not alias_value:
        return
    key = (alias_type, alias_value, branch)
    seen = record.setdefault("_alias_keys", set())
    if key in seen:
        return
    seen.add(key)
    record["aliases"].append({"type": alias_type, "value": alias_value, "branch_code": branch})


def _load_busy_units(path: Path | None) -> dict[str, set[str]]:
    units: dict[str, set[str]] = defaultdict(set)
    if path is None:
        return units
    with path.open("r", encoding="utf-8-sig", newline="", errors="replace") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        if "Unit" not in fields:
            raise RuntimeError("BUSY item master has no Unit column")
        for row in reader:
            part_no = _part(row.get("Part No Normalized") or row.get("Alias / Part No"))
            unit = _text(row.get("Unit"))
            if part_no and unit:
                units[part_no].add(unit)
    return units


def _load_tagro_alias_rows(path: Path | None) -> dict[str, list[dict[str, str]]]:
    by_part: dict[str, list[dict[str, str]]] = defaultdict(list)
    if path is None:
        return by_part
    with path.open("r", encoding="utf-8-sig", newline="", errors="replace") as handle:
        reader = csv.DictReader(handle)
        required = {
            "Branch", "Original TAGRO item name", "TAGRO display name", "BUSY item codes",
            "BUSY alias", "STIHL part number",
        }
        missing = sorted(required - set(reader.fieldnames or []))
        if missing:
            raise RuntimeError(f"TAGRO alias CSV missing columns: {missing}")
        for row in reader:
            part_no = _part(row.get("STIHL part number"))
            if part_no:
                by_part[part_no].append({k: _text(v) for k, v in row.items()})
    return by_part


def build_records(
    official_json: Path,
    *,
    tagro_alias_csv: Path | None = None,
    busy_item_master: Path | None = None,
    effective_from: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payload = json.loads(official_json.read_text(encoding="utf-8-sig"))
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("official STIHL JSON must contain a non-empty rows array")

    aliases_by_part = _load_tagro_alias_rows(tagro_alias_csv)
    units_by_part = _load_busy_units(busy_item_master)
    by_part: dict[str, dict[str, Any]] = {}
    duplicate_rows = 0

    for index, row in enumerate(rows, start=1):
        if not isinstance(row, Mapping):
            raise RuntimeError(f"official row {index} is not an object")
        part_no = _part(row.get("part_key") or row.get("part_no"))
        name = _text(row.get("name"))
        if not part_no or not name:
            continue
        hsn = _text(row.get("hsn"))
        gst = _decimal(row.get("gst"))
        price = _decimal(row.get("price"))
        mrp = _decimal(row.get("mrp"))
        category = _text(row.get("type")) or "UNCLASSIFIED"

        if part_no in by_part:
            duplicate_rows += 1
            existing = by_part[part_no]
            checks = {
                "name": (existing["name"], name),
                "category": (existing["category"], category),
                "hsn": (existing["hsn_code"], hsn),
                "gst": (_decimal(existing["gst_rate"]), gst),
            }
            for field, (left, right) in checks.items():
                if left not in (None, "") and right not in (None, "") and left != right:
                    raise RuntimeError(f"conflicting official {field} for STIHL part {part_no}: {left!r} vs {right!r}")
            if not existing["hsn_code"] and hsn:
                existing["hsn_code"] = hsn
            if not existing["gst_rate"] and gst is not None:
                existing["gst_rate"] = _decimal_text(gst)
            existing.setdefault("_price_candidates", set()).add((price, mrp))
            continue

        by_part[part_no] = {
            "manufacturer": "STIHL",
            "sku": part_no,
            "model": name,
            "name": name,
            "category": category,
            "hsn_code": hsn,
            "gst_rate": _decimal_text(gst),
            "unit": "nos",
            "serial_tracked": category.upper() == "MACHINES",
            "aliases": [],
            "prices": [],
            "_alias_keys": set(),
            "_price_candidates": {(price, mrp)},
        }

    unit_conflicts: dict[str, list[str]] = {}
    for part_no, record in by_part.items():
        units = sorted(units_by_part.get(part_no, set()))
        if len(units) == 1:
            record["unit"] = units[0]
        elif len(units) > 1:
            unit_conflicts[part_no] = units

        for row in aliases_by_part.get(part_no, []):
            branch = _text(row.get("Branch")).upper()
            _add_alias(record, "tagro_original_name", row.get("Original TAGRO item name"), branch)
            _add_alias(record, "tagro_display_name", row.get("TAGRO display name"), branch)
            _add_alias(record, "busy_alias", row.get("BUSY alias"), branch)
            for code in _split_codes(row.get("BUSY item codes")):
                _add_alias(record, "busy_item_code", code, branch)

        candidates = record.pop("_price_candidates")
        known_prices = {p for p, _ in candidates if p is not None}
        known_mrps = {m for _, m in candidates if m is not None}
        if len(known_prices) > 1:
            raise RuntimeError(f"conflicting official price values for STIHL part {part_no}: {sorted(known_prices)}")
        if len(known_mrps) > 1:
            raise RuntimeError(f"conflicting official MRP values for STIHL part {part_no}: {sorted(known_mrps)}")
        if effective_from:
            price = next(iter(known_prices), None)
            mrp = next(iter(known_mrps), None)
            gst = _decimal(record["gst_rate"])
            if price is not None:
                record["prices"].append({"type": "official_before_gst", "amount": _decimal_text(price), "effective_from": effective_from, "branch_code": ""})
                if gst is not None:
                    incl = (price * (Decimal("1") + gst / Decimal("100"))).quantize(Decimal("0.01"))
                    record["prices"].append({"type": "official_incl_gst", "amount": _decimal_text(incl), "effective_from": effective_from, "branch_code": ""})
            if mrp is not None:
                record["prices"].append({"type": "mrp", "amount": _decimal_text(mrp), "effective_from": effective_from, "branch_code": ""})
        record.pop("_alias_keys", None)

    # Preflight alias identity across the whole package. Do not rely on database
    # upsert semantics to decide which product owns a local name/code.
    alias_owner: dict[tuple[str, str, str], str] = {}
    alias_collisions: list[dict[str, str]] = []
    for part_no, record in by_part.items():
        for alias in record["aliases"]:
            key = (alias["type"], alias["value"], alias["branch_code"])
            prior = alias_owner.get(key)
            if prior and prior != part_no:
                alias_collisions.append({
                    "alias_type": key[0], "alias_value": key[1], "branch_code": key[2],
                    "first_part": prior, "second_part": part_no,
                })
            else:
                alias_owner[key] = part_no
    if alias_collisions:
        sample = alias_collisions[:10]
        raise RuntimeError(f"TAGRO/BUSY alias collisions found ({len(alias_collisions)}); sample={sample}")

    records = sorted(by_part.values(), key=lambda item: item["sku"])
    stats = {
        "official_rows": len(rows),
        "duplicate_official_rows": duplicate_rows,
        "unique_products": len(records),
        "unknown_hsn": sum(1 for item in records if not item["hsn_code"]),
        "unknown_gst": sum(1 for item in records if not item["gst_rate"]),
        "tagro_alias_products": sum(1 for item in records if item["aliases"]),
        "aliases": sum(len(item["aliases"]) for item in records),
        "unit_from_busy_master": sum(1 for item in records if item["unit"] != "nos"),
        "unit_conflicts": len(unit_conflicts),
        "unit_conflict_sample": dict(list(sorted(unit_conflicts.items()))[:20]),
        "prices_included": bool(effective_from),
        "prices": sum(len(item["prices"]) for item in records),
    }
    return records, stats


def invoke_lambda(*, profile: str, region: str, function_name: str, event: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="echo-stihl-catalog-") as td:
        root = Path(td)
        payload_path = root / "payload.json"
        response_path = root / "response.json"
        payload_path.write_text(stable_json(event), encoding="utf-8")
        cmd = [
            "aws", "lambda", "invoke", "--profile", profile, "--region", region,
            "--function-name", function_name, "--cli-binary-format", "raw-in-base64-out",
            "--payload", f"fileb://{payload_path}", str(response_path), "--output", "json",
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


def sync(args: argparse.Namespace) -> dict[str, Any]:
    official_json = Path(args.official_json)
    alias_csv = Path(args.tagro_alias_csv) if args.tagro_alias_csv else None
    item_master = Path(args.busy_item_master) if args.busy_item_master else None
    for path in (official_json, alias_csv, item_master):
        if path is not None and not path.exists():
            raise FileNotFoundError(path)

    records, stats = build_records(
        official_json,
        tagro_alias_csv=alias_csv,
        busy_item_master=item_master,
        effective_from=args.effective_from or None,
    )
    source_sha = sha256_file(official_json)
    alias_sha = sha256_file(alias_csv) if alias_csv else None
    item_sha = sha256_file(item_master) if item_master else None
    responses: list[dict[str, Any]] = []

    for offset in range(0, len(records), args.batch_size):
        batch = records[offset:offset + args.batch_size]
        fingerprint = hashlib.sha256(stable_json(batch).encode("utf-8")).hexdigest()[:16]
        sync_run_id = f"stihl-catalog:{source_sha[:12]}:{offset}:{fingerprint}"
        event = {
            "confirm": CONFIRMATION,
            "enterprise_id": args.enterprise_id,
            "package": {
                "schema": PACKAGE_SCHEMA,
                "sync_run_id": sync_run_id,
                "source_system": "STIHL_OFFICIAL_CATALOGUE_WITH_TAGRO_ENRICHMENT",
                "source_locator": args.source_locator,
                "source_class": "reviewed_canonical_product_master",
                "source_as_of": args.source_as_of or None,
                "provenance": {
                    "official_source_sha256": source_sha,
                    "tagro_alias_sha256": alias_sha,
                    "busy_item_master_sha256": item_sha,
                    "price_effective_from": args.effective_from or None,
                    "offset": offset,
                    "mode": "canonical_catalogue_no_planar",
                },
                "records": batch,
            },
        }
        if args.dry_run:
            responses.append({"status": "dry_run", "sync_run_id": sync_run_id, "record_count": len(batch)})
        else:
            responses.append(invoke_lambda(
                profile=args.profile, region=args.region, function_name=args.function_name, event=event,
            ))

    return {
        "schema": "tagro.echo.stihl-catalog-sync-summary/1",
        "official_source": str(official_json),
        "official_source_sha256": source_sha,
        "tagro_alias_source": str(alias_csv) if alias_csv else None,
        "busy_item_master_source": str(item_master) if item_master else None,
        "source_as_of": args.source_as_of or None,
        "price_effective_from": args.effective_from or None,
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
    p = argparse.ArgumentParser(description="Admit the full official STIHL catalogue into ECHO and enrich it with TAGRO/BUSY aliases.")
    p.add_argument("--official-json", required=True)
    p.add_argument("--tagro-alias-csv")
    p.add_argument("--busy-item-master")
    p.add_argument("--source-as-of", help="Observed/issued source date if independently known; may be omitted.")
    p.add_argument("--effective-from", help="Authoritative price effective date YYYY-MM-DD. Omit to admit products without prices.")
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
