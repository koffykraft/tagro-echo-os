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
from typing import Any, Mapping

CONFIRMATION = "SYNC_OPERATIONAL_TWIN_V1"
PACKAGE_SCHEMA = "tagro.echo.canonical-master/1"
DEFAULT_SOURCE_LOCATOR = "TAGRO_AUTOMATION/price_update_2026_27/outputs/TAGRO_STIHL_BUSY_Update_One_Row_Per_Item.csv"

UNIT_EQUIVALENTS = {
    "PCS": "Pcs", "PCS.": "Pcs", "PC": "Pcs", "PIECE": "Pcs", "PIECES": "Pcs",
    "NOS": "Pcs", "NOS.": "Pcs", "NO": "Pcs", "NUMBERS": "Pcs",
    "LINK": "Links", "LINKS": "Links",
    "ROL": "ROL", "ROLL": "ROL", "REEL": "Reel",
    "KGS": "Kgs.", "KGS.": "Kgs.", "KG": "Kgs.",
    "LTR": "Ltr", "LITRE": "Ltr", "LITRES": "Ltr",
    "MTR": "Mtr", "MTRS": "Mtr", "METER": "Mtr", "METERS": "Mtr",
    "CFT": "CFT",
}


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


def _name_key(value: Any) -> str:
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
    return [x.strip() for x in re.split(r"\s*\|\s*", _text(value)) if x.strip()]


def _canonical_unit(value: Any) -> str:
    raw = _text(value)
    if not raw:
        return ""
    return UNIT_EQUIVALENTS.get(raw.upper(), raw)


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


def _load_busy_existing(path: Path) -> dict[str, list[dict[str, str]]]:
    by_part: dict[str, list[dict[str, str]]] = defaultdict(list)
    with path.open("r", encoding="utf-8-sig", newline="", errors="replace") as handle:
        reader = csv.DictReader(handle)
        required = {
            "Branch", "Original TAGRO item name", "TAGRO display name", "BUSY item codes",
            "BUSY alias", "STIHL part number",
        }
        missing = sorted(required - set(reader.fieldnames or []))
        if missing:
            raise RuntimeError(f"BUSY-existing STIHL CSV missing columns: {missing}")
        for row in reader:
            part_no = _part(row.get("STIHL part number"))
            original = _text(row.get("Original TAGRO item name"))
            branch = _text(row.get("Branch")).upper()
            if not part_no or not original or not branch:
                continue
            by_part[part_no].append({k: _text(v) for k, v in row.items()})
    if not by_part:
        raise RuntimeError("BUSY-existing STIHL CSV produced no eligible part-number matches")
    return by_part


def _load_busy_master(path: Path) -> tuple[dict[tuple[str, str], list[dict[str, str]]], dict[str, list[dict[str, str]]]]:
    by_branch_name: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    by_part: dict[str, list[dict[str, str]]] = defaultdict(list)
    with path.open("r", encoding="utf-8-sig", newline="", errors="replace") as handle:
        reader = csv.DictReader(handle)
        required = {"Branch", "Item Name", "Part No Normalized", "Alias / Part No", "Unit"}
        missing = sorted(required - set(reader.fieldnames or []))
        if missing:
            raise RuntimeError(f"BUSY item master missing columns: {missing}")
        for row in reader:
            clean = {k: _text(v) for k, v in row.items()}
            branch = clean.get("Branch", "").upper()
            name = clean.get("Item Name", "")
            part_no = _part(clean.get("Part No Normalized") or clean.get("Alias / Part No"))
            if branch and name:
                by_branch_name[(branch, _name_key(name))].append(clean)
            if part_no:
                by_part[part_no].append(clean)
    return by_branch_name, by_part


def _load_official(path: Path) -> tuple[dict[str, dict[str, Any]], int]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("official STIHL JSON must contain a non-empty rows array")
    official: dict[str, dict[str, Any]] = {}
    duplicates = 0
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, Mapping):
            raise RuntimeError(f"official row {index} is not an object")
        part_no = _part(row.get("part_key") or row.get("part_no"))
        name = _text(row.get("name"))
        if not part_no or not name:
            continue
        incoming = {
            "part_no": part_no,
            "name": name,
            "category": _text(row.get("type")) or "UNCLASSIFIED",
            "hsn": _text(row.get("hsn")),
            "gst": _decimal(row.get("gst")),
            "price": _decimal(row.get("price")),
            "mrp": _decimal(row.get("mrp")),
        }
        if part_no not in official:
            official[part_no] = incoming
            continue
        duplicates += 1
        prior = official[part_no]
        for field in ("name", "category", "hsn", "gst", "price", "mrp"):
            left, right = prior[field], incoming[field]
            if left not in (None, "") and right not in (None, "") and left != right:
                raise RuntimeError(f"conflicting official {field} for STIHL part {part_no}: {left!r} vs {right!r}")
            if left in (None, "") and right not in (None, ""):
                prior[field] = right
    return official, duplicates


def build_records(
    official_json: Path,
    *,
    tagro_alias_csv: Path,
    busy_item_master: Path,
    effective_from: str = "2026-06-01",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build only STIHL products already present in BUSY-derived admitted matches.

    BUSY names/codes are preserved as aliases. This function never writes back to BUSY.
    Official STIHL data enriches matched items with part/name/HSN/GST and June price basis.
    """
    busy_existing = _load_busy_existing(tagro_alias_csv)
    by_branch_name, busy_by_part = _load_busy_master(busy_item_master)
    official, duplicate_official_rows = _load_official(official_json)

    records: list[dict[str, Any]] = []
    unmatched_official: list[str] = []
    unit_conflicts: dict[str, list[str]] = {}
    conversion_candidates: list[dict[str, str]] = []

    for part_no in sorted(busy_existing):
        source_rows = busy_existing[part_no]
        off = official.get(part_no)
        if not off:
            unmatched_official.append(part_no)
            continue

        exact_master_rows: list[dict[str, str]] = []
        for src in source_rows:
            branch = src["Branch"].upper()
            original = src["Original TAGRO item name"]
            candidates = by_branch_name.get((branch, _name_key(original)), [])
            exact = [r for r in candidates if _part(r.get("Part No Normalized") or r.get("Alias / Part No")) == part_no]
            exact_master_rows.extend(exact)

        # If name-level lookup is absent, use only same-part BUSY rows; never a different part/name guess.
        master_rows = exact_master_rows or busy_by_part.get(part_no, [])
        original_units = sorted({_text(r.get("Unit")) for r in master_rows if _text(r.get("Unit"))})
        canonical_units = sorted({_canonical_unit(u) for u in original_units if _canonical_unit(u)})
        if len(canonical_units) > 1:
            unit_conflicts[part_no] = original_units
            continue
        unit = canonical_units[0] if canonical_units else ""

        record: dict[str, Any] = {
            "manufacturer": "STIHL",
            "sku": part_no,
            "model": off["name"],
            "name": off["name"],
            "category": off["category"],
            "hsn_code": off["hsn"],
            "gst_rate": _decimal_text(off["gst"]),
            "unit": unit or "Pcs",
            "serial_tracked": off["category"].upper() == "MACHINES",
            "aliases": [],
            "prices": [],
            "unit_conversions": [],
            "_alias_keys": set(),
        }

        # Preserve every existing BUSY/TAGRO identity; never overwrite or normalize it in BUSY.
        for src in source_rows:
            branch = src["Branch"].upper()
            _add_alias(record, "busy_original_name", src.get("Original TAGRO item name"), branch)
            _add_alias(record, "tagro_display_name", src.get("TAGRO display name"), branch)
            _add_alias(record, "busy_alias", src.get("BUSY alias"), branch)
            for code in _split_codes(src.get("BUSY item codes")):
                _add_alias(record, "busy_item_code", code, branch)

        for r in master_rows:
            branch = _text(r.get("Branch")).upper()
            _add_alias(record, "busy_master_name", r.get("Item Name"), branch)
            _add_alias(record, "busy_master_alias", r.get("Alias / Part No"), branch)

        # User-authorised June STIHL price basis. Missing price/tax stays missing.
        if effective_from:
            if off["price"] is not None:
                record["prices"].append({
                    "type": "stihl_june_before_gst", "amount": _decimal_text(off["price"]),
                    "effective_from": effective_from, "branch_code": "",
                })
                if off["gst"] is not None:
                    incl = (off["price"] * (Decimal("1") + off["gst"] / Decimal("100"))).quantize(Decimal("0.01"))
                    record["prices"].append({
                        "type": "stihl_june_incl_gst", "amount": _decimal_text(incl),
                        "effective_from": effective_from, "branch_code": "",
                    })
            if off["mrp"] is not None:
                record["prices"].append({
                    "type": "stihl_june_mrp", "amount": _decimal_text(off["mrp"]),
                    "effective_from": effective_from, "branch_code": "",
                })

        # Flag purchase-pack conversion needs, but never invent a multiplier.
        for r in master_rows:
            name = _text(r.get("Item Name"))
            raw_unit = _text(r.get("Unit"))
            if re.search(r"\b(REEL|ROLL)\b", name, re.I) and _canonical_unit(raw_unit) == "Links":
                conversion_candidates.append({
                    "part_no": part_no,
                    "busy_name": name,
                    "busy_unit": raw_unit,
                    "needed": "purchase reel/roll to retail Links factor requires explicit source",
                })
                break

        record.pop("_alias_keys", None)
        records.append(record)

    if unit_conflicts:
        sample = dict(list(sorted(unit_conflicts.items()))[:20])
        raise RuntimeError(f"BUSY unit conflicts require review ({len(unit_conflicts)} products); sample={sample}")

    # Preflight alias ownership across admitted existing BUSY items.
    alias_owner: dict[tuple[str, str, str], str] = {}
    collisions: list[dict[str, str]] = []
    for record in records:
        for alias in record["aliases"]:
            key = (alias["type"], alias["value"], alias["branch_code"])
            prior = alias_owner.get(key)
            if prior and prior != record["sku"]:
                collisions.append({
                    "alias_type": key[0], "alias_value": key[1], "branch_code": key[2],
                    "first_part": prior, "second_part": record["sku"],
                })
            else:
                alias_owner[key] = record["sku"]
    if collisions:
        raise RuntimeError(f"unsafe BUSY/TAGRO alias collisions found ({len(collisions)}); sample={collisions[:10]}")

    stats = {
        "busy_matched_part_numbers": len(busy_existing),
        "admitted_existing_busy_products": len(records),
        "not_introduced_from_full_stihl_catalogue": max(0, len(official) - len(records)),
        "busy_matches_missing_official_stihl_row": len(unmatched_official),
        "missing_official_sample": unmatched_official[:20],
        "duplicate_official_rows": duplicate_official_rows,
        "unknown_hsn": sum(1 for r in records if not r["hsn_code"]),
        "unknown_gst": sum(1 for r in records if not r["gst_rate"]),
        "busy_aliases_preserved": sum(len(r["aliases"]) for r in records),
        "prices": sum(len(r["prices"]) for r in records),
        "price_base": "STIHL June 2026",
        "price_effective_from": effective_from,
        "unit_conversion_candidates": len(conversion_candidates),
        "unit_conversion_candidate_sample": conversion_candidates[:20],
        "busy_writeback": False,
        "new_non_busy_products_allowed": False,
    }
    return records, stats


def invoke_lambda(*, profile: str, region: str, function_name: str, event: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="echo-stihl-busy-existing-") as td:
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
    alias_csv = Path(args.tagro_alias_csv)
    item_master = Path(args.busy_item_master)
    for path in (official_json, alias_csv, item_master):
        if not path.exists():
            raise FileNotFoundError(path)

    records, stats = build_records(
        official_json,
        tagro_alias_csv=alias_csv,
        busy_item_master=item_master,
        effective_from=args.effective_from,
    )
    source_shas = {
        "official_stihl": sha256_file(official_json),
        "busy_existing_matches": sha256_file(alias_csv),
        "busy_item_master": sha256_file(item_master),
    }
    responses: list[dict[str, Any]] = []
    for offset in range(0, len(records), args.batch_size):
        batch = records[offset:offset + args.batch_size]
        fingerprint = hashlib.sha256(stable_json(batch).encode("utf-8")).hexdigest()[:16]
        sync_run_id = f"stihl-busy-existing:{source_shas['busy_existing_matches'][:12]}:{offset}:{fingerprint}"
        event = {
            "confirm": CONFIRMATION,
            "enterprise_id": args.enterprise_id,
            "package": {
                "schema": PACKAGE_SCHEMA,
                "sync_run_id": sync_run_id,
                "source_system": "TAGRO_BUSY_EXISTING_WITH_STIHL_JUNE_ENRICHMENT",
                "source_locator": args.source_locator,
                "source_class": "existing_busy_product_master_enriched_from_stihl",
                "source_as_of": args.source_as_of or None,
                "provenance": {
                    **{f"{k}_sha256": v for k, v in source_shas.items()},
                    "price_base": "STIHL June 2026",
                    "price_effective_from": args.effective_from,
                    "busy_writeback": False,
                    "new_non_busy_products_allowed": False,
                    "offset": offset,
                    "mode": "busy_foundation_no_planar",
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
        "schema": "tagro.echo.stihl-busy-existing-sync-summary/1",
        "official_source": str(official_json),
        "busy_existing_source": str(alias_csv),
        "busy_item_master_source": str(item_master),
        "source_as_of": args.source_as_of or None,
        "stats": stats,
        "batches": len(responses),
        "inserted": sum(int(r.get("inserted") or 0) for r in responses),
        "updated": sum(int(r.get("updated") or 0) for r in responses),
        "unchanged": sum(int(r.get("unchanged") or 0) for r in responses),
        "aliases_upserted": sum(int(r.get("aliases_upserted") or 0) for r in responses),
        "prices_upserted": sum(int(r.get("prices_upserted") or 0) for r in responses),
        "dry_run": bool(args.dry_run),
        "busy_writeback": False,
        "new_non_busy_products_allowed": False,
        "planar_projection": False,
    }


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Admit only STIHL items already present in TAGRO/BUSY, preserving BUSY identities and units.")
    p.add_argument("--official-json", required=True)
    p.add_argument("--tagro-alias-csv", required=True, help="TAGRO_STIHL_BUSY_Update_One_Row_Per_Item.csv; this is the admission boundary.")
    p.add_argument("--busy-item-master", required=True)
    p.add_argument("--source-as-of", help="Optional observation date; does not alter BUSY.")
    p.add_argument("--effective-from", default="2026-06-01", help="User-authorised STIHL June 2026 price base date; default 2026-06-01.")
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
