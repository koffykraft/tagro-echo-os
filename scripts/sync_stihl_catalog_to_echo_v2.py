from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any, Mapping

_BASE_PATH = Path(__file__).with_name("sync_stihl_catalog_to_echo.py")
_SPEC = importlib.util.spec_from_file_location("sync_stihl_catalog_to_echo_base", _BASE_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(f"Unable to load base importer: {_BASE_PATH}")
base = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(base)
_BASE_BUILD_RECORDS = base.build_records


def _load_official_safe(path: Path) -> tuple[dict[str, dict[str, Any]], int]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("official STIHL JSON must contain a non-empty rows array")
    official: dict[str, dict[str, Any]] = {}
    duplicates = 0
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, Mapping):
            raise RuntimeError(f"official row {index} is not an object")
        part_no = base._part(row.get("part_key") or row.get("part_no"))
        name = base._text(row.get("name"))
        if not part_no or not name:
            continue
        incoming = {
            "part_no": part_no,
            "name": name,
            "category": base._text(row.get("type")) or "UNCLASSIFIED",
            "hsn": base._text(row.get("hsn")),
            "gst": base._decimal(row.get("gst")),
            "price": base._decimal(row.get("price")),
            "mrp": base._decimal(row.get("mrp")),
        }
        prior = official.get(part_no)
        if prior is None:
            official[part_no] = incoming
            continue
        duplicates += 1
        # Descriptions/categories may vary for the same official part number.
        # Commercial/tax values may not conflict.
        for field in ("hsn", "gst", "price", "mrp"):
            left, right = prior[field], incoming[field]
            if left not in (None, "") and right not in (None, "") and left != right:
                raise RuntimeError(f"conflicting official {field} for STIHL part {part_no}: {left!r} vs {right!r}")
            if left in (None, "") and right not in (None, ""):
                prior[field] = right
    return official, duplicates


def build_records(*args: Any, **kwargs: Any):
    original_loader = base._load_official
    base._load_official = _load_official_safe
    try:
        # IMPORTANT: call the captured base implementation, not base.build_records,
        # because sync() temporarily points base.build_records at this wrapper.
        records, stats = _BASE_BUILD_RECORDS(*args, **kwargs)
    finally:
        base._load_official = original_loader

    # Existing BUSY identity remains the operational display identity.
    # STIHL wording is enrichment/reference only.
    for record in records:
        official_name = record.get("name", "")
        busy_names = [
            a["value"] for a in record.get("aliases", [])
            if a.get("type") == "busy_original_name" and a.get("value")
        ]
        if busy_names:
            record["name"] = busy_names[0]
            record["model"] = busy_names[0]
        if official_name:
            existing = {(a.get("type"), a.get("value"), a.get("branch_code", "")) for a in record.get("aliases", [])}
            key = ("stihl_official_name", official_name, "")
            if key not in existing:
                record.setdefault("aliases", []).append({"type": key[0], "value": key[1], "branch_code": ""})
    stats["operational_name_source"] = "BUSY original item name"
    stats["official_stihl_name_role"] = "reference_alias"
    return records, stats


def sync(args):
    original_build = base.build_records
    base.build_records = build_records
    try:
        return base.sync(args)
    finally:
        base.build_records = original_build


if __name__ == "__main__":
    print(json.dumps(sync(base.parser().parse_args()), indent=2, default=str))
