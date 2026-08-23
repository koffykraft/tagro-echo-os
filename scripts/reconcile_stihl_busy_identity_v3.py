from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import tempfile
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

SCHEMA = "tagro.echo.stihl-identity-reconciliation/3"

_BASE_PATH = Path(__file__).with_name("reconcile_stihl_busy_identity_v2.py")
_SPEC = importlib.util.spec_from_file_location("reconcile_stihl_busy_identity_v2_base", _BASE_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(f"Unable to load base reconciler: {_BASE_PATH}")
base = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(base)


def raw(value: Any) -> str:
    return "" if value is None else str(value)


def text(value: Any) -> str:
    return raw(value).strip()


def canonical_branch(value: Any) -> str:
    """Map source segment labels to the operational branch without erasing source evidence."""
    branch = text(value).upper()
    if branch in {"SDM JAIN", "SDM STIHL"}:
        return "SDM"
    return branch


def unit_family(value: Any) -> str:
    """Normalize labels only. Never infer a quantity conversion."""
    s = base.re.sub(r"[^A-Z0-9]+", "", text(value).upper())
    if not s:
        return "UNKNOWN"
    if s in {
        "PC", "PCS", "PIECE", "PIECES", "NO", "NOS", "NUMBER", "NUMBERS",
        "EACH", "UNIT", "UNITS",
    }:
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


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="", errors="replace") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        return [{key: raw(value) for key, value in row.items()} for row in reader], fields


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def transformed_copy(
    source: Path,
    target: Path,
    branch_field: str,
) -> tuple[list[dict[str, str]], list[str]]:
    rows, fields = read_csv(source)
    if branch_field not in fields:
        raise RuntimeError(f"{source.name} missing branch field {branch_field!r}")
    transformed: list[dict[str, str]] = []
    for row in rows:
        rec = dict(row)
        rec[branch_field] = canonical_branch(row.get(branch_field))
        transformed.append(rec)
    write_csv(target, fields, transformed)
    return rows, fields


def master_raw_branch_queues(master_rows: list[dict[str, str]]) -> dict[tuple[str, str, str, str], deque[str]]:
    queues: dict[tuple[str, str, str, str], deque[str]] = defaultdict(deque)
    for row in master_rows:
        key = (
            canonical_branch(row.get("Branch")),
            text(row.get("Source row")),
            raw(row.get("Item Name")),
            raw(row.get("Alias / Part No")),
        )
        queues[key].append(raw(row.get("Branch")))
    return queues


def add_raw_branch_to_master_output(path: Path, queues: dict[tuple[str, str, str, str], deque[str]]) -> None:
    rows, fields = read_csv(path)
    if not rows and "source_branch_raw" in fields:
        return
    out_fields = list(fields)
    if "source_branch_raw" not in out_fields:
        out_fields.insert(1, "source_branch_raw")
    out: list[dict[str, Any]] = []
    for row in rows:
        key = (
            canonical_branch(row.get("branch")),
            text(row.get("source_row")),
            raw(row.get("busy_name_raw")),
            raw(row.get("busy_alias_raw")),
        )
        queue = queues.get(key)
        rec = dict(row)
        rec["source_branch_raw"] = queue.popleft() if queue else raw(row.get("branch"))
        out.append(rec)
    write_csv(path, out_fields, out)


def add_source_branch_to_review_output(path: Path, field_name: str = "branch") -> None:
    rows, fields = read_csv(path)
    out_fields = list(fields)
    if "source_branch_raw" not in out_fields:
        out_fields.insert(1, "source_branch_raw")
    out: list[dict[str, Any]] = []
    for row in rows:
        rec = dict(row)
        rec["source_branch_raw"] = raw(row.get(field_name))
        rec[field_name] = canonical_branch(row.get(field_name))
        out.append(rec)
    write_csv(path, out_fields, out)


def reconcile(td_match_csv: Path, busy_master_csv: Path, existing_admission_csv: Path, out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    original_master_rows, _ = read_csv(busy_master_csv)

    with tempfile.TemporaryDirectory(prefix="tagro-stihl-recon-v3-") as tmp_name:
        tmp = Path(tmp_name)
        td_tmp = tmp / "td.csv"
        master_tmp = tmp / "master.csv"
        admission_tmp = tmp / "admission.csv"
        transformed_copy(td_match_csv, td_tmp, "branch")
        transformed_copy(busy_master_csv, master_tmp, "Branch")
        transformed_copy(existing_admission_csv, admission_tmp, "Branch")

        previous_unit_family = base.unit_family
        try:
            base.unit_family = unit_family
            summary = base.reconcile(td_tmp, master_tmp, admission_tmp, out_dir)
        finally:
            base.unit_family = previous_unit_family

    queues = master_raw_branch_queues(original_master_rows)
    for filename in (
        "01-exact-part-accepted-all-branches.csv",
        "06-name-candidates-needing-part-evidence.csv",
        "07-name-candidate-part-conflicts.csv",
        "08-name-candidates-part-revalidated.csv",
        "09-unmatched-stihl-clues.csv",
    ):
        add_raw_branch_to_master_output(out_dir / filename, queues)

    # Review outputs originate from TD/admission rather than the all-branch master.
    # Their raw branch label is already the source branch in those files; canonicalize only operationally.
    for filename in (
        "04-official-part-corrections-review.csv",
        "05-tagro-master-part-candidates-review.csv",
    ):
        add_source_branch_to_review_output(out_dir / filename)

    summary["schema"] = SCHEMA
    summary["policy"]["branch_logic"] = (
        "operational branch code is canonicalized; raw source branch/segment label is retained separately"
    )
    summary["policy"]["branch_mapping"] = {"SDM JAIN": "SDM", "SDM STIHL": "SDM"}
    summary["policy"]["unit_logic"] = (
        "normalize equivalent labels only; preserve branch raw unit; report true family conflicts; infer no multiplier"
    )
    summary["sources"] = {
        "td_match_csv": str(td_match_csv),
        "busy_master_csv": str(busy_master_csv),
        "existing_admission_csv": str(existing_admission_csv),
    }
    summary["validation"] = {
        "source_branch_preserved": True,
        "operational_branch_segments_collapsed": True,
        "unit_conversion_inferred": False,
        "corrected_part_numbers_auto_admitted": False,
        "name_candidates_auto_admitted": False,
    }

    (out_dir / "00-summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return summary


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="BUSY/TD STIHL identity reconciliation with canonical operational branches and preserved raw evidence."
    )
    p.add_argument("--td-match-csv", required=True)
    p.add_argument("--busy-master-csv", required=True)
    p.add_argument("--existing-admission-csv", required=True)
    p.add_argument("--out-dir", required=True)
    return p


def main() -> int:
    args = parser().parse_args()
    summary = reconcile(
        Path(args.td_match_csv),
        Path(args.busy_master_csv),
        Path(args.existing_admission_csv),
        Path(args.out_dir),
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
