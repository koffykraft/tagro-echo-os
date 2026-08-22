from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any


BRANCHES = ("KVR", "PKM", "NDD", "MDM", "SKT")
SOURCE_SYSTEM = "tagro_canonical_financial_projection"
SOURCE_CLASS = "governed_read_only_financial_evidence"
MAX_CHUNK = 450  # private importer limit is 500; keep headroom.


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def norm_name(value: str | None) -> str:
    text = (value or "").upper()
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    text = re.sub(r"\b(STIHL|GENUINE|ASSY|ASSEMBLY|NO|NOS|PCS|PC)\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def fy_start(iso_date: str) -> int:
    year, month = int(iso_date[:4]), int(iso_date[5:7])
    return year if month >= 4 else year - 1


def unit_cost(row: sqlite3.Row) -> Decimal | None:
    qty = abs(Decimal(str(row["qty"] or 0)))
    if qty <= 0:
        return None
    taxable = abs(Decimal(str(row["taxable_amount"] or 0)))
    if taxable > 0:
        return taxable / qty
    rate = abs(Decimal(str(row["unit_rate"] or 0)))
    return rate if rate > 0 else None


def item_key(row: sqlite3.Row) -> str:
    code = str(row["item_code"] or "").strip()
    return f"CODE:{code}" if code else f"NAME:{norm_name(row['item_name'])}"


def money(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")


def classify_cost_confidence(
    recent: list[dict[str, Any]],
    *,
    selected_fy: int | None,
    sale_fy: int,
) -> tuple[str, Decimal | None, str]:
    """Apply the same guarded confidence rule as FinancialHealthEngine.

    Historical export evidence is supporting/read-only. It must not label a
    cost reference strong merely because three old prices exist. Strong needs
    at least three recent references from the sale financial year and a recent
    price band no wider than 30% of the latest LIFO-style reference. Exact is
    reserved for deterministic sale-linked acquisition cost and is therefore
    not emitted by this historical purchase-evidence exporter.
    """
    if not recent or selected_fy is None:
        return "unknown", None, "no qualifying pre-sale purchase-price evidence"

    latest = Decimal(recent[0]["cost_before_tax"])
    values = [Decimal(p["cost_before_tax"]) for p in recent]
    low, high = min(values), max(values)
    dispersion = (
        Decimal("0.00")
        if latest == 0
        else ((high - low) / latest * Decimal("100")).quantize(Decimal("0.01"))
    )
    same_fy = selected_fy == sale_fy
    coherent_band = dispersion <= Decimal("30.00")
    if len(recent) >= 3 and same_fy and coherent_band:
        return (
            "strong",
            dispersion,
            "three or more coherent purchase references in the sale financial year",
        )

    reasons: list[str] = []
    if len(recent) < 3:
        reasons.append("fewer than three recent purchase references")
    if not same_fy:
        reasons.append("cost evidence falls back to a prior financial year")
    if not coherent_band:
        reasons.append(f"recent purchase-price band is volatile ({dispersion}%)")
    return "weak", dispersion, "; ".join(reasons) or "purchase evidence is supportive but not deterministic"


def parse_args() -> argparse.Namespace:
    runtime = Path(os.environ.get("TAGRO_AWS_RUNTIME_ROOT", r"T:\TAGRO_AWS_RUNTIME"))
    parser = argparse.ArgumentParser(description="Export read-only TAGRO financial projection observations.")
    parser.add_argument("--source", type=Path, default=runtime / "data/canonical/tagro-data-platform/tagro_history.sqlite")
    parser.add_argument("--output", type=Path, default=runtime / "data/staging/financial-observation-export")
    parser.add_argument("--sale-start", default="2026-04-01")
    parser.add_argument("--sale-end", default="")
    parser.add_argument("--branches", default=",".join(BRANCHES))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = args.source.resolve()
    if not source.is_file():
        raise SystemExit(f"Missing canonical history: {source}")
    branches = tuple(x.strip().upper() for x in args.branches.split(",") if x.strip())
    if not branches:
        raise SystemExit("At least one branch is required")

    con = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    quick = con.execute("pragma quick_check").fetchone()[0]
    if quick != "ok":
        raise SystemExit(f"Canonical history quick_check failed: {quick}")

    max_date = con.execute(
        "select max(vch_date) from vouchers where branch in ({})".format(",".join("?" for _ in branches)),
        branches,
    ).fetchone()[0]
    sale_end = args.sale_end or str(max_date or "")
    if not sale_end:
        raise SystemExit("Could not determine source max voucher date")
    if args.sale_start > sale_end:
        raise SystemExit("sale-start is after sale-end")

    source_hash = file_sha256(source)
    branch_marks = ",".join("?" for _ in branches)
    purchase_sql = f"""
      select v.branch,v.vch_date,v.voucher_id,v.vch_no,v.vch_code,v.party_name,
             i.item_line_id,i.item_code,i.item_name,i.qty,i.unit_rate,i.taxable_amount,
             i.source_sha256,i.record_sha256
      from vouchers v join voucher_items i on i.voucher_id=v.voucher_id
      where v.branch in ({branch_marks}) and v.vch_type=2 and v.vch_date<=?
        and coalesce(v.cancelled,0)=0 and coalesce(v.vch_cancelled,0)=0
        and abs(coalesce(i.qty,0))>0
      order by v.vch_date,v.vch_code,i.sr_no
    """
    purchase_rows = list(con.execute(purchase_sql, (*branches, sale_end)))
    purchase_by_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in purchase_rows:
        cost = unit_cost(row)
        key = item_key(row)
        vendor_norm = norm_name(str(row["party_name"] or ""))
        stock_transfer = "THUMPASSERY AGRO" in vendor_norm or "STOCK TRANSFER" in vendor_norm
        if cost is None or not key or key == "NAME:" or stock_transfer:
            continue
        purchase_by_key[key].append(
            {
                "branch": str(row["branch"]),
                "purchase_date": str(row["vch_date"]),
                "purchase_voucher_id": str(row["voucher_id"]),
                "purchase_voucher_no": str(row["vch_no"] or ""),
                "purchase_vch_code": str(row["vch_code"]),
                "item_line_id": str(row["item_line_id"]),
                "cost_before_tax": cost,
                "source_sha256": str(row["source_sha256"] or ""),
                "record_sha256": str(row["record_sha256"] or ""),
            }
        )

    sale_sql = f"""
      select v.branch,v.vch_date,v.voucher_id,v.vch_no,v.vch_code,
             i.item_line_id,i.item_code,i.item_name,i.unit_name,i.qty,i.unit_rate,
             i.taxable_amount,i.total_amount,i.source_sha256,i.record_sha256
      from vouchers v join voucher_items i on i.voucher_id=v.voucher_id
      where v.branch in ({branch_marks}) and v.vch_type=9 and v.vch_date between ? and ?
        and coalesce(v.cancelled,0)=0 and coalesce(v.vch_cancelled,0)=0
        and abs(coalesce(i.qty,0))>0
      order by v.vch_date,v.branch,v.vch_code,i.sr_no
    """
    sales = list(con.execute(sale_sql, (*branches, args.sale_start, sale_end)))

    observations: list[dict[str, Any]] = []
    cost_counts = {"exact": 0, "strong": 0, "weak": 0, "unknown": 0}
    for row in sales:
        key = item_key(row)
        sale_fy = fy_start(str(row["vch_date"]))
        eligible = [p for p in purchase_by_key.get(key, ()) if p["purchase_date"] <= row["vch_date"]]
        by_fy: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for p in eligible:
            by_fy[fy_start(p["purchase_date"])].append(p)
        selected_fy = max((fy for fy in by_fy if fy <= sale_fy), default=None)
        selected: list[dict[str, Any]] = []
        recent: list[dict[str, Any]] = []
        scope = "none"
        if selected_fy is not None:
            year_rows = by_fy[selected_fy]
            same_branch = [p for p in year_rows if p["branch"] == row["branch"]]
            scoped = same_branch if same_branch else year_rows
            scope = "same_branch" if same_branch else "enterprise_fallback"
            ordered = sorted(scoped, key=lambda p: (p["purchase_date"], p["purchase_vch_code"], p["item_line_id"]), reverse=True)
            recent = ordered[:4]
            selected = list(recent)
            protected_high = max(scoped, key=lambda p: (p["cost_before_tax"], p["purchase_date"], p["purchase_vch_code"], p["item_line_id"]))
            if protected_high not in selected:
                selected.append(protected_high)
        confidence, dispersion, confidence_reason = classify_cost_confidence(
            recent,
            selected_fy=selected_fy,
            sale_fy=sale_fy,
        )
        cost_counts[confidence] += 1
        sale_ref = f"{row['branch']}|{row['voucher_id']}|{row['item_line_id']}"
        value = {
            "branch": str(row["branch"]),
            "sale_date": str(row["vch_date"]),
            "sale_voucher_id": str(row["voucher_id"]),
            "sale_voucher_no": str(row["vch_no"] or ""),
            "sale_vch_code": str(row["vch_code"]),
            "item_line_id": str(row["item_line_id"]),
            "item_key": key,
            "item_code": str(row["item_code"] or ""),
            "item_name": str(row["item_name"] or ""),
            "unit_name": str(row["unit_name"] or ""),
            "quantity": str(abs(Decimal(str(row["qty"] or 0)))),
            "sale_before_tax": money(abs(Decimal(str(row["taxable_amount"] or 0)))),
            "sale_total": money(abs(Decimal(str(row["total_amount"] or 0)))),
            "cost_reference_confidence": confidence,
            "cost_reference_confidence_reason": confidence_reason,
            "cost_reference_recent_count": len(recent),
            "cost_reference_recent_dispersion_pct": None if dispersion is None else str(dispersion),
            "cost_reference_scope": scope,
            "cost_reference_fy_start": selected_fy,
            "cost_policy": "LIFO-style latest external purchase; up to four recent comparison prices plus protected pre-sale high; prior-FY fallback; strong requires sale-FY coherent evidence",
            "purchase_references": [
                {
                    "branch": p["branch"],
                    "purchase_date": p["purchase_date"],
                    "cost_before_tax": money(p["cost_before_tax"]),
                    "source_ref": f"warehouse:purchase:{p['purchase_voucher_id']}:{p['item_line_id']}",
                    "purchase_voucher_no": p["purchase_voucher_no"],
                    "record_sha256": p["record_sha256"],
                }
                for p in selected
            ],
            "source_ref": f"warehouse:sale:{row['voucher_id']}:{row['item_line_id']}",
            "source_sha256": str(row["source_sha256"] or ""),
            "record_sha256": str(row["record_sha256"] or ""),
        }
        observations.append(
            {
                "subject_kind": "financial_sale_line",
                "source_subject_ref": sale_ref,
                "dimension_code": "financial.sale_cost_evidence",
                "value": value,
                "observed_at": f"{row['vch_date']}T00:00:00+05:30",
                "confidence": 1.0,
                "provenance_ref": value["source_ref"],
            }
        )

    run_hasher = hashlib.sha256()
    run_hasher.update(source_hash.encode())
    run_hasher.update(f"|{args.sale_start}|{sale_end}|{','.join(branches)}|".encode())
    for observation in observations:
        run_hasher.update(json.dumps(observation, sort_keys=True, separators=(",", ":")).encode())
        run_hasher.update(b"\n")
    run_hash = run_hasher.hexdigest()
    run_id = f"financial-{sale_end}-{run_hash[:12]}"
    run_dir = args.output / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    source_as_of = f"{sale_end}T23:59:59+05:30"
    chunk_files: list[str] = []
    for index in range(0, len(observations), MAX_CHUNK):
        chunk = observations[index:index + MAX_CHUNK]
        chunk_no = index // MAX_CHUNK + 1
        package = {
            "source_system": SOURCE_SYSTEM,
            "source_locator": f"{run_id}/chunk-{chunk_no:04d}",
            "source_class": SOURCE_CLASS,
            "source_as_of": source_as_of,
            "immutable_ref": run_hash,
            "observations": chunk,
        }
        path = run_dir / f"chunk-{chunk_no:04d}.json"
        path.write_text(json.dumps(package, indent=2, sort_keys=True), encoding="utf-8")
        chunk_files.append(path.name)

    manifest_value = {
        "run_id": run_id,
        "run_hash": run_hash,
        "source_path": str(source),
        "source_sha256": source_hash,
        "source_quick_check": quick,
        "sale_start": args.sale_start,
        "sale_end": sale_end,
        "branches": list(branches),
        "sale_line_observations": len(observations),
        "chunk_count": len(chunk_files),
        "chunk_files": chunk_files,
        "cost_reference_counts": cost_counts,
        "cost_policy": "LIFO-style latest external purchase; up to four recent comparison prices plus protected pre-sale high; stock transfers excluded; prior-FY fallback; strong requires same-FY coherent evidence",
        "canonical_write": False,
    }
    manifest_package = {
        "source_system": SOURCE_SYSTEM,
        "source_locator": f"{run_id}/manifest",
        "source_class": SOURCE_CLASS,
        "source_as_of": source_as_of,
        "immutable_ref": run_hash,
        "observations": [
            {
                "subject_kind": "financial_snapshot",
                "source_subject_ref": run_id,
                "dimension_code": "financial.export_manifest",
                "value": manifest_value,
                "observed_at": source_as_of,
                "confidence": 1.0,
                "provenance_ref": f"sha256:{run_hash}",
            }
        ],
    }
    manifest_path = run_dir / "manifest-package.json"
    manifest_path.write_text(json.dumps(manifest_package, indent=2, sort_keys=True), encoding="utf-8")
    (run_dir / "export-report.json").write_text(json.dumps(manifest_value, indent=2, sort_keys=True), encoding="utf-8")

    print(f"Financial observation export complete: {run_id}")
    print(f"Source quick_check={quick} sha256={source_hash}")
    print(f"Sale lines={len(observations)} chunks={len(chunk_files)}")
    print(
        "Cost references "
        f"exact={cost_counts['exact']} strong={cost_counts['strong']} "
        f"weak={cost_counts['weak']} unknown={cost_counts['unknown']}"
    )
    print(f"RunHash={run_hash}")
    print(f"Output={run_dir}")
    print("CanonicalWrite=False")


if __name__ == "__main__":
    main()
