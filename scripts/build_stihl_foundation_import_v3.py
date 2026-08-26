from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

SCHEMA = "tagro.echo.stihl-foundation-import-pack/1"
SCOUT_SCHEMA = "tagro.echo.wo0014-stihl-scout/4"
RECON_SCHEMA = "tagro.echo.stihl-identity-reconciliation/3"
KNOWN_OPERATIONAL_BRANCHES = {"KVR", "PKM", "NDD", "MDM", "SKT", "OYR", "SDM"}
BRANCH_PRIORITY = {code: index for index, code in enumerate(("KVR", "PKM", "NDD", "MDM", "SKT", "OYR", "SDM"))}


def raw(value: Any) -> str:
    return "" if value is None else str(value)


def text(value: Any) -> str:
    return raw(value).strip()


def bool_value(value: Any) -> bool:
    return text(value).lower() in {"1", "true", "yes", "y"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="", errors="replace") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        return [{key: raw(value) for key, value in row.items()} for row in reader], fields


def require_fields(fields: list[str], required: set[str], label: str) -> None:
    missing = sorted(required - set(fields))
    if missing:
        raise RuntimeError(f"{label} missing required columns: {missing}")


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def unit_family(value: Any) -> str:
    s = re.sub(r"[^A-Z0-9]+", "", text(value).upper())
    if not s:
        return "UNKNOWN"
    if s in {"PC", "PCS", "PIECE", "PIECES", "NO", "NOS", "NUMBER", "NUMBERS", "EACH", "UNIT", "UNITS"}:
        return "EACH"
    if s in {"LTR", "LTRS", "LITRE", "LITRES", "LITER", "LITERS"}:
        return "LTR"
    if s in {"LINK", "LINKS"}:
        return "LINK"
    if s in {"ROL", "ROLL", "ROLLS"}:
        return "ROLL"
    if s in {"PKT", "PKTS", "PACKET", "PACKETS"}:
        return "PKT"
    if s in {"KG", "KGS", "KILOGRAM", "KILOGRAMS"}:
        return "KG"
    if s in {"M", "MTR", "MTRS", "METER", "METERS", "METRE", "METRES"}:
        return "M"
    return s


def source_row_sort(value: Any) -> tuple[int, str]:
    s = text(value)
    try:
        return int(s), s
    except ValueError:
        return 10**12, s


def row_sort_key(row: dict[str, str]) -> tuple[Any, ...]:
    branch = text(row.get("branch")).upper()
    source_branch = text(row.get("source_branch_raw")).upper()
    return (
        0 if bool_value(row.get("direct_seed_evidence")) else 1,
        BRANCH_PRIORITY.get(branch, 999),
        source_branch,
        source_row_sort(row.get("source_row")),
        text(row.get("busy_name_raw")).upper(),
        text(row.get("busy_alias_raw")).upper(),
    )


def split_codes(value: Any) -> list[str]:
    result: list[str] = []
    for token in re.split(r"\s*\|\s*|\s*,\s*|\s*;\s*", text(value)):
        token = token.strip()
        if token and token not in result:
            result.append(token)
    return result


def alias_key(alias: dict[str, str]) -> tuple[str, str, str]:
    return alias["type"], alias["value"], alias["branch_code"]


def build_pack(scout_report_dir: Path, out_dir: Path) -> dict[str, Any]:
    scout_report_dir = scout_report_dir.resolve()
    out_dir = out_dir.resolve()
    scout_summary_path = scout_report_dir / "99-scout-summary.json"
    recon_dir = scout_report_dir / "identity-reconciliation"
    recon_summary_path = recon_dir / "00-summary.json"
    accepted_path = recon_dir / "01-exact-part-accepted-all-branches.csv"
    unit_variants_path = recon_dir / "03-exact-part-unit-variants.csv"

    for path in (scout_summary_path, recon_summary_path, accepted_path, unit_variants_path):
        if not path.is_file():
            raise FileNotFoundError(path)

    scout = json.loads(scout_summary_path.read_text(encoding="utf-8-sig"))
    recon = json.loads(recon_summary_path.read_text(encoding="utf-8-sig"))
    if scout.get("schema") != SCOUT_SCHEMA or scout.get("status") != "scout_complete":
        raise RuntimeError("source scout report is not a completed WO-0014 scout v4")
    if recon.get("schema") != RECON_SCHEMA:
        raise RuntimeError(f"unexpected reconciliation schema: {recon.get('schema')!r}")
    if scout.get("deploy_executed") or scout.get("migration_executed") or scout.get("live_import_executed"):
        raise RuntimeError("source scout report is not mutation-free")
    validation = recon.get("validation") or {}
    required_validation = {
        "source_branch_preserved": True,
        "operational_branch_segments_collapsed": True,
        "unit_conversion_inferred": False,
        "corrected_part_numbers_auto_admitted": False,
        "name_candidates_auto_admitted": False,
    }
    for key, expected in required_validation.items():
        if validation.get(key) is not expected:
            raise RuntimeError(f"reconciliation validation failed: {key}={validation.get(key)!r}")

    accepted_rows, accepted_fields = read_csv(accepted_path)
    require_fields(
        accepted_fields,
        {
            "branch", "source_branch_raw", "source_row", "busy_item_codes_evidence", "busy_name_raw",
            "busy_alias_raw", "busy_part_key", "busy_unit_raw", "busy_unit_family",
            "busy_parent_group_raw", "canonical_stihl_part_key", "identity_class", "direct_seed_evidence",
        },
        "accepted reconciliation",
    )
    unit_rows, unit_fields = read_csv(unit_variants_path)
    require_fields(unit_fields, {"canonical_stihl_part_key", "unit_families", "unit_state"}, "unit variants")

    expected_rows = int(recon["counts"]["exact_part_accepted_rows"])
    expected_parts = int(recon["counts"]["exact_part_accepted_unique_parts"])
    expected_unit_conflicts = int(recon["counts"]["canonical_parts_with_unit_conflicts"])
    if len(accepted_rows) != expected_rows:
        raise RuntimeError(f"accepted row count mismatch: {len(accepted_rows)} != {expected_rows}")

    by_part: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in accepted_rows:
        part = text(row.get("canonical_stihl_part_key"))
        branch = text(row.get("branch")).upper()
        if not part or text(row.get("identity_class")) != "EXACT_PART_ACCEPT":
            raise RuntimeError("accepted reconciliation contains a non-exact or missing canonical part")
        if branch not in KNOWN_OPERATIONAL_BRANCHES:
            raise RuntimeError(f"unknown operational branch in accepted evidence: {branch!r}")
        by_part[part].append(row)
    if len(by_part) != expected_parts:
        raise RuntimeError(f"accepted unique part mismatch: {len(by_part)} != {expected_parts}")

    conflict_parts_from_file = {
        text(row.get("canonical_stihl_part_key"))
        for row in unit_rows
        if text(row.get("unit_state")) == "CONFLICT_REVIEW"
    }
    if len(conflict_parts_from_file) != expected_unit_conflicts:
        raise RuntimeError(
            f"unit conflict count mismatch: {len(conflict_parts_from_file)} != {expected_unit_conflicts}"
        )

    recomputed_conflicts: dict[str, list[str]] = {}
    missing_unit_parts: list[str] = []
    for part, rows in by_part.items():
        families = sorted({unit_family(row.get("busy_unit_raw")) for row in rows if unit_family(row.get("busy_unit_raw")) != "UNKNOWN"})
        if not families:
            missing_unit_parts.append(part)
        elif len(families) > 1:
            recomputed_conflicts[part] = families
    if set(recomputed_conflicts) != conflict_parts_from_file:
        raise RuntimeError(
            "unit conflict evidence mismatch between accepted rows and 03-exact-part-unit-variants.csv"
        )

    blocked_parts = set(conflict_parts_from_file) | set(missing_unit_parts)
    evidence_rows: list[dict[str, Any]] = []
    candidate_records: dict[str, dict[str, Any]] = {}
    all_alias_candidates: dict[str, list[dict[str, str]]] = defaultdict(list)

    for part, rows in sorted(by_part.items()):
        ordered = sorted(rows, key=row_sort_key)
        primary = ordered[0]
        families = sorted({unit_family(row.get("busy_unit_raw")) for row in rows if unit_family(row.get("busy_unit_raw")) != "UNKNOWN"})
        blocked_reason = ""
        if part in conflict_parts_from_file:
            blocked_reason = "UNIT_FAMILY_CONFLICT"
        elif part in missing_unit_parts:
            blocked_reason = "UNIT_MISSING"

        for row in ordered:
            evidence_rows.append({
                "canonical_stihl_part_key": part,
                "import_state": "BLOCKED" if blocked_reason else "ELIGIBLE",
                "blocked_reason": blocked_reason,
                "branch": text(row.get("branch")).upper(),
                "source_branch_raw": raw(row.get("source_branch_raw")),
                "source_row": raw(row.get("source_row")),
                "busy_item_codes_evidence": raw(row.get("busy_item_codes_evidence")),
                "busy_name_raw": raw(row.get("busy_name_raw")),
                "busy_alias_raw": raw(row.get("busy_alias_raw")),
                "busy_unit_raw": raw(row.get("busy_unit_raw")),
                "busy_unit_family": unit_family(row.get("busy_unit_raw")),
                "busy_parent_group_raw": raw(row.get("busy_parent_group_raw")),
                "direct_seed_evidence": bool_value(row.get("direct_seed_evidence")),
            })
        if blocked_reason:
            continue

        primary_name = text(primary.get("busy_name_raw"))
        primary_unit = text(primary.get("busy_unit_raw"))
        primary_category = text(primary.get("busy_parent_group_raw")) or "UNCLASSIFIED"
        if not primary_name or not primary_unit:
            raise RuntimeError(f"eligible part {part} lacks primary name/unit")

        alias_candidates: list[dict[str, str]] = []
        seen_aliases: set[tuple[str, str, str]] = set()
        for row in ordered:
            branch = text(row.get("branch")).upper()
            for alias_type, value in (
                ("busy_original_name", raw(row.get("busy_name_raw"))),
                ("busy_alias", raw(row.get("busy_alias_raw"))),
            ):
                if text(value):
                    alias = {"type": alias_type, "value": raw(value), "branch_code": branch}
                    if alias_key(alias) not in seen_aliases:
                        seen_aliases.add(alias_key(alias))
                        alias_candidates.append(alias)
            for code in split_codes(row.get("busy_item_codes_evidence")):
                alias = {"type": "busy_item_code", "value": code, "branch_code": branch}
                if alias_key(alias) not in seen_aliases:
                    seen_aliases.add(alias_key(alias))
                    alias_candidates.append(alias)
        all_alias_candidates[part] = alias_candidates
        candidate_records[part] = {
            "manufacturer": "STIHL",
            "sku": part,
            "model": primary_name,
            "name": primary_name,
            "category": primary_category,
            "hsn_code": "",
            "gst_rate": "",
            "unit": primary_unit,
            "serial_tracked": primary_category.strip().upper() == "MACHINES",
            "aliases": [],
            "prices": [],
            "unit_conversions": [],
        }

    owners: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for part, aliases in all_alias_candidates.items():
        for alias in aliases:
            owners[alias_key(alias)].add(part)

    alias_collision_rows: list[dict[str, str]] = []
    omitted_alias_count = 0
    for part, record in candidate_records.items():
        safe_aliases: list[dict[str, str]] = []
        for alias in all_alias_candidates[part]:
            key = alias_key(alias)
            owner_parts = sorted(owners[key])
            if len(owner_parts) > 1:
                omitted_alias_count += 1
                alias_collision_rows.append({
                    "alias_type": key[0],
                    "alias_value": key[1],
                    "branch_code": key[2],
                    "owner_parts": " | ".join(owner_parts),
                    "omitted_from_runtime_aliases": "True",
                })
                continue
            safe_aliases.append(alias)
        record["aliases"] = safe_aliases

    records = [candidate_records[part] for part in sorted(candidate_records)]
    if any(record["prices"] for record in records):
        raise RuntimeError("foundation pack unexpectedly contains prices")
    if any(record["unit_conversions"] for record in records):
        raise RuntimeError("foundation pack unexpectedly contains unit conversions")
    if any(text(record["gst_rate"]) or text(record["hsn_code"]) for record in records):
        raise RuntimeError("foundation pack unexpectedly contains tax enrichment")

    out_dir.mkdir(parents=True, exist_ok=True)
    canonical_records_path = out_dir / "01-canonical-records.json"
    evidence_path = out_dir / "02-busy-evidence.csv"
    blocked_path = out_dir / "03-blocked-unit-parts.csv"
    collisions_path = out_dir / "04-alias-collisions-review.csv"

    canonical_records_path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    write_csv(evidence_path, [
        "canonical_stihl_part_key", "import_state", "blocked_reason", "branch", "source_branch_raw", "source_row",
        "busy_item_codes_evidence", "busy_name_raw", "busy_alias_raw", "busy_unit_raw", "busy_unit_family",
        "busy_parent_group_raw", "direct_seed_evidence",
    ], evidence_rows)
    blocked_rows = [
        {
            "canonical_stihl_part_key": part,
            "blocked_reason": "UNIT_FAMILY_CONFLICT" if part in conflict_parts_from_file else "UNIT_MISSING",
            "unit_families": " | ".join(recomputed_conflicts.get(part, [])),
        }
        for part in sorted(blocked_parts)
    ]
    write_csv(blocked_path, ["canonical_stihl_part_key", "blocked_reason", "unit_families"], blocked_rows)

    unique_collision_rows: dict[tuple[str, str, str, str], dict[str, str]] = {}
    for row in alias_collision_rows:
        key = (row["alias_type"], row["alias_value"], row["branch_code"], row["owner_parts"])
        unique_collision_rows[key] = row
    collision_rows = [unique_collision_rows[key] for key in sorted(unique_collision_rows)]
    write_csv(collisions_path, [
        "alias_type", "alias_value", "branch_code", "owner_parts", "omitted_from_runtime_aliases",
    ], collision_rows)

    summary = {
        "schema": SCHEMA,
        "status": "dry_run_pack_complete",
        "source_scout_report_dir": str(scout_report_dir),
        "source_scout_git_head": scout.get("git_head"),
        "source_reconciliation_schema": recon.get("schema"),
        "sources": {
            "scout_summary": {"path": str(scout_summary_path), "sha256": sha256_file(scout_summary_path)},
            "reconciliation_summary": {"path": str(recon_summary_path), "sha256": sha256_file(recon_summary_path)},
            "accepted_exact_parts": {"path": str(accepted_path), "sha256": sha256_file(accepted_path)},
            "unit_variants": {"path": str(unit_variants_path), "sha256": sha256_file(unit_variants_path)},
        },
        "policy": {
            "identity_source": "v3 exact-part accepted reconciliation only",
            "prices_included": False,
            "tax_enrichment_included": False,
            "unit_conversion_inferred": False,
            "unit_conflict_parts_imported": False,
            "ambiguous_runtime_aliases_imported": False,
            "busy_writeback": False,
            "aws_write": False,
            "planar_projection": False,
        },
        "counts": {
            "accepted_evidence_rows": len(accepted_rows),
            "proven_identity_parts": len(by_part),
            "canonical_records_ready": len(records),
            "unit_conflict_parts_blocked": len(conflict_parts_from_file),
            "missing_unit_parts_blocked": len(missing_unit_parts),
            "total_parts_blocked": len(blocked_parts),
            "runtime_aliases_ready": sum(len(record["aliases"]) for record in records),
            "ambiguous_alias_keys_omitted": len(collision_rows),
            "ambiguous_alias_occurrences_omitted": omitted_alias_count,
        },
        "outputs": {
            "canonical_records": str(canonical_records_path),
            "busy_evidence": str(evidence_path),
            "blocked_unit_parts": str(blocked_path),
            "alias_collisions_review": str(collisions_path),
        },
    }
    (out_dir / "00-summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Build a non-mutating STIHL foundation import pack from a completed v3 scout report.")
    p.add_argument("--scout-report-dir", required=True)
    p.add_argument("--out-dir")
    return p


def main() -> int:
    args = parser().parse_args()
    scout_dir = Path(args.scout_report_dir)
    out_dir = Path(args.out_dir) if args.out_dir else scout_dir / "foundation-import-pack"
    summary = build_pack(scout_dir, out_dir)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
