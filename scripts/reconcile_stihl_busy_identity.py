from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

SCHEMA = "tagro.echo.stihl-identity-reconciliation/1"

MATCHED_STATUSES = {
    "matched_price",
    "matched_tagro_master_price_only",
    "matched_tagro_no_price",
}

MODEL_RE = re.compile(
    r"\b(?:MS|MSE|MSA|FS|FSE|FSA|FR|FT|SR|BR|BG|BGA|SH|HS|HSA|HT|HTA|KM|KA|RE|SE|SG|TS|BT)\s*[- ]?\s*\d+[A-Z0-9]*\b",
    re.I,
)

STOPWORDS = {
    "STIHL", "PART", "PARTS", "ASSEMBLY", "ASSY", "COMPLETE", "KIT", "NEW", "OLD",
    "FOR", "WITH", "WITHOUT", "AND", "THE", "OF", "A", "AN", "PCS", "PC", "NOS", "NO",
}


def raw(value: Any) -> str:
    return "" if value is None else str(value)


def text(value: Any) -> str:
    return raw(value).strip()


def part_key(value: Any) -> str:
    s = re.sub(r"[^A-Z0-9]+", "", text(value).upper())
    if s.isdigit() and 7 <= len(s) < 11:
        s = s.zfill(11)
    return s


def name_key(value: Any) -> str:
    s = text(value).upper().replace("Ã˜", " ")
    s = re.sub(r"[^A-Z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def tokens(value: Any) -> set[str]:
    return {t for t in name_key(value).split() if len(t) > 1 and t not in STOPWORDS}


def models(value: Any) -> set[str]:
    out = set()
    for m in MODEL_RE.findall(raw(value)):
        out.add(re.sub(r"[^A-Z0-9]+", "", m.upper()))
    return out


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="", errors="replace") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = [{k: raw(v) for k, v in row.items()} for row in reader]
    return rows, fields


def first(row: dict[str, str], names: Iterable[str]) -> str:
    for name in names:
        if name in row and text(row[name]):
            return row[name]
    return ""


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fields})


def load_busy_master(path: Path):
    rows, fields = read_csv(path)
    required = {"Branch", "Item Name", "Alias / Part No", "Part No Normalized", "Unit"}
    missing = sorted(required - set(fields))
    if missing:
        raise RuntimeError(f"BUSY master missing required columns: {missing}")

    by_branch_name: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    by_branch_item_code: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        branch = text(row.get("Branch")).upper()
        nk = name_key(row.get("Item Name"))
        if branch and nk:
            by_branch_name[(branch, nk)].append(row)
        item_code = first(row, ("Item Code", "ItemCode", "Code", "BUSY Item Code"))
        if branch and text(item_code):
            by_branch_item_code[(branch, text(item_code))].append(row)
    return rows, by_branch_name, by_branch_item_code


def load_existing_admission(path: Path) -> dict[tuple[str, str, str], list[dict[str, str]]]:
    rows, fields = read_csv(path)
    required = {"Branch", "Original TAGRO item name", "BUSY alias", "STIHL part number"}
    missing = sorted(required - set(fields))
    if missing:
        raise RuntimeError(f"existing STIHL admission CSV missing required columns: {missing}")
    out: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        branch = text(row.get("Branch")).upper()
        nk = name_key(row.get("Original TAGRO item name"))
        ak = part_key(row.get("BUSY alias"))
        if branch and nk:
            out[(branch, nk, ak)].append(row)
    return out


def choose_busy_master_row(
    td: dict[str, str],
    by_branch_name: dict[tuple[str, str], list[dict[str, str]]],
    by_branch_item_code: dict[tuple[str, str], list[dict[str, str]]],
) -> dict[str, str] | None:
    branch = text(td.get("branch")).upper()
    item_code = text(td.get("item_code"))
    if branch and item_code:
        candidates = by_branch_item_code.get((branch, item_code), [])
        if len(candidates) == 1:
            return candidates[0]
        if candidates:
            alias = part_key(td.get("busy_alias") or td.get("busy_part_key"))
            exact = [r for r in candidates if part_key(r.get("Part No Normalized") or r.get("Alias / Part No")) == alias]
            if len(exact) == 1:
                return exact[0]
    nk = name_key(td.get("busy_name"))
    candidates = by_branch_name.get((branch, nk), []) if branch and nk else []
    if len(candidates) == 1:
        return candidates[0]
    alias = part_key(td.get("busy_alias") or td.get("busy_part_key"))
    exact = [r for r in candidates if part_key(r.get("Part No Normalized") or r.get("Alias / Part No")) == alias]
    return exact[0] if len(exact) == 1 else None


def canonical_from_td(td: dict[str, str]) -> str:
    return part_key(td.get("stihl_part_no") or td.get("tagro_part_no"))


def classify_td_row(td: dict[str, str], admission_rows: list[dict[str, str]]) -> tuple[str, str, str]:
    status = text(td.get("match_status")).lower()
    busy_key = part_key(td.get("busy_alias") or td.get("busy_part_key"))
    canonical = canonical_from_td(td)

    if status in MATCHED_STATUSES and canonical and busy_key and canonical == busy_key:
        return "EXACT_PART_ACCEPT", canonical, "td_busy_alias_equals_stihl_part"

    for adm in admission_rows:
        adm_part = part_key(adm.get("STIHL part number"))
        adm_alias = part_key(adm.get("BUSY alias"))
        if adm_part and adm_alias and adm_part == adm_alias:
            return "EXACT_PART_ACCEPT", adm_part, "existing_admission_busy_alias_equals_stihl_part"

    if status in MATCHED_STATUSES and canonical:
        return "TD_CORRECTED_PROVISIONAL", canonical, "td_reviewed_mapping_part_differs_from_busy_alias"

    for adm in admission_rows:
        adm_part = part_key(adm.get("STIHL part number"))
        if adm_part:
            return "EXISTING_ADMISSION_PROVISIONAL", adm_part, "existing_admission_mapping_requires_identity_review"

    return "UNRESOLVED", "", ""


def is_stihl_looking(td: dict[str, str], master: dict[str, str] | None, classification: str) -> bool:
    if classification != "UNRESOLVED":
        return True
    if text(td.get("stihl_part_no")) or text(td.get("tagro_part_no")) or text(td.get("tagro_name")):
        return True
    if "STIHL" in name_key(td.get("busy_name")) or "STIHL" in name_key(td.get("print_name")):
        return True
    if master and "STIHL" in name_key(master.get("Parent Group")):
        return True
    return False


def row_evidence(td: dict[str, str], master: dict[str, str] | None, classification: str, canonical: str, method: str) -> dict[str, Any]:
    return {
        "branch": raw(td.get("branch")),
        "item_code": raw(td.get("item_code")),
        "busy_name_raw": raw(td.get("busy_name")),
        "print_name_raw": raw(td.get("print_name")),
        "busy_alias_raw": raw(td.get("busy_alias")),
        "busy_part_key_td": raw(td.get("busy_part_key")),
        "busy_part_key_recomputed": part_key(td.get("busy_alias") or td.get("busy_part_key")),
        "busy_unit_raw": raw((master or {}).get("Unit", "")) or raw(td.get("tagro_unit")),
        "busy_parent_group_raw": raw((master or {}).get("Parent Group", "")),
        "td_match_status": raw(td.get("match_status")),
        "tagro_name_raw": raw(td.get("tagro_name")),
        "tagro_part_no_raw": raw(td.get("tagro_part_no")),
        "tagro_alias_raw": raw(td.get("tagro_alias")),
        "stihl_part_no_raw": raw(td.get("stihl_part_no")),
        "stihl_name_raw": raw(td.get("stihl_name")),
        "canonical_stihl_part_key": canonical,
        "identity_class": classification,
        "identity_method": method,
    }


def unique_name_candidate(
    evidence: dict[str, Any],
    exact_name_index: dict[str, set[str]],
    model_index: dict[str, set[str]],
    canonical_names: dict[str, list[str]],
) -> tuple[str, str, float]:
    names = [evidence["busy_name_raw"], evidence["print_name_raw"]]
    for candidate_name in names:
        nk = name_key(candidate_name)
        owners = exact_name_index.get(nk, set()) if nk else set()
        if len(owners) == 1:
            return next(iter(owners)), "exact_normalized_name", 1.0

    row_models = models(" ".join(names))
    possible_parts: set[str] = set()
    for model in row_models:
        possible_parts.update(model_index.get(model, set()))
    if not possible_parts:
        return "", "", 0.0

    row_tokens = tokens(" ".join(names))
    if not row_tokens:
        return "", "", 0.0

    scored: list[tuple[float, str]] = []
    for part in possible_parts:
        best = 0.0
        for known in canonical_names.get(part, []):
            kt = tokens(known)
            if not kt:
                continue
            union = row_tokens | kt
            score = len(row_tokens & kt) / len(union) if union else 0.0
            best = max(best, score)
        if best >= 0.80:
            scored.append((best, part))
    scored.sort(reverse=True)
    if not scored:
        return "", "", 0.0
    if len(scored) > 1 and abs(scored[0][0] - scored[1][0]) < 0.08:
        return "", "ambiguous_model_token_match", scored[0][0]
    return scored[0][1], "model_token_candidate", scored[0][0]


def reconcile(td_match_csv: Path, busy_master_csv: Path, existing_admission_csv: Path, out_dir: Path) -> dict[str, Any]:
    td_rows, td_fields = read_csv(td_match_csv)
    required_td = {"branch", "item_code", "busy_name", "busy_alias", "busy_part_key", "print_name", "match_status"}
    missing_td = sorted(required_td - set(td_fields))
    if missing_td:
        raise RuntimeError(f"TD match CSV missing required columns: {missing_td}")

    busy_master_rows, by_branch_name, by_branch_item_code = load_busy_master(busy_master_csv)
    admission_index = load_existing_admission(existing_admission_csv)

    evidence_rows: list[dict[str, Any]] = []
    exact_rows: list[dict[str, Any]] = []
    provisional_rows: list[dict[str, Any]] = []
    unresolved_stihl_rows: list[dict[str, Any]] = []
    branch_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for td in td_rows:
        master = choose_busy_master_row(td, by_branch_name, by_branch_item_code)
        branch = text(td.get("branch")).upper()
        nk = name_key(td.get("busy_name"))
        ak = part_key(td.get("busy_alias") or td.get("busy_part_key"))
        admissions = admission_index.get((branch, nk, ak), [])
        classification, canonical, method = classify_td_row(td, admissions)
        evidence = row_evidence(td, master, classification, canonical, method)
        evidence["stihl_looking"] = is_stihl_looking(td, master, classification)
        evidence_rows.append(evidence)
        branch_counts[branch]["td_rows"] += 1
        if evidence["stihl_looking"]:
            branch_counts[branch]["stihl_looking"] += 1
        if classification == "EXACT_PART_ACCEPT":
            exact_rows.append(evidence)
            branch_counts[branch]["exact_part_accept"] += 1
        elif classification in {"TD_CORRECTED_PROVISIONAL", "EXISTING_ADMISSION_PROVISIONAL"}:
            provisional_rows.append(evidence)
            branch_counts[branch]["provisional_part_mapping"] += 1
        elif evidence["stihl_looking"]:
            unresolved_stihl_rows.append(evidence)
            branch_counts[branch]["unresolved_stihl"] += 1

    canonical_names: dict[str, list[str]] = defaultdict(list)
    exact_name_index: dict[str, set[str]] = defaultdict(set)
    model_index: dict[str, set[str]] = defaultdict(set)
    exact_by_part: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in exact_rows:
        part = row["canonical_stihl_part_key"]
        exact_by_part[part].append(row)
        for value in (
            row["busy_name_raw"], row["print_name_raw"], row["tagro_name_raw"], row["stihl_name_raw"],
        ):
            if not text(value):
                continue
            canonical_names[part].append(value)
            nk = name_key(value)
            if nk:
                exact_name_index[nk].add(part)
            for model in models(value):
                model_index[model].add(part)

    name_candidates: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    part_conflicts: list[dict[str, Any]] = []
    revalidated: list[dict[str, Any]] = []
    for row in unresolved_stihl_rows:
        candidate_part, candidate_method, score = unique_name_candidate(row, exact_name_index, model_index, canonical_names)
        out = dict(row)
        out["candidate_stihl_part_key"] = candidate_part
        out["candidate_method"] = candidate_method
        out["candidate_score"] = f"{score:.4f}" if score else ""
        busy_key = row["busy_part_key_recomputed"]
        if candidate_part:
            if busy_key and busy_key == candidate_part:
                out["candidate_validation"] = "PART_REVALIDATED"
                revalidated.append(out)
            elif busy_key and busy_key != candidate_part:
                out["candidate_validation"] = "PART_CONFLICT_REVIEW"
                part_conflicts.append(out)
            else:
                out["candidate_validation"] = "NAME_CANDIDATE_NEEDS_PART_EVIDENCE"
                name_candidates.append(out)
        else:
            out["candidate_validation"] = "UNMATCHED"
            unmatched.append(out)

    variant_rows: list[dict[str, Any]] = []
    for part, rows in sorted(exact_by_part.items()):
        names = []
        seen_names = set()
        branches = []
        for row in rows:
            b = raw(row["branch"])
            if b not in branches:
                branches.append(b)
            n = raw(row["busy_name_raw"])
            if n not in seen_names:
                seen_names.add(n)
                names.append(n)
        if len(names) > 1 or len(branches) > 1:
            variant_rows.append({
                "canonical_stihl_part_key": part,
                "branches": " | ".join(branches),
                "distinct_busy_names": len(names),
                "busy_names_exact": " || ".join(names),
            })

    evidence_fields = [
        "branch", "item_code", "busy_name_raw", "print_name_raw", "busy_alias_raw", "busy_part_key_td",
        "busy_part_key_recomputed", "busy_unit_raw", "busy_parent_group_raw", "td_match_status",
        "tagro_name_raw", "tagro_part_no_raw", "tagro_alias_raw", "stihl_part_no_raw", "stihl_name_raw",
        "canonical_stihl_part_key", "identity_class", "identity_method", "stihl_looking",
    ]
    candidate_fields = evidence_fields + ["candidate_stihl_part_key", "candidate_method", "candidate_score", "candidate_validation"]

    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "01-exact-part-accepted.csv", exact_rows, evidence_fields)
    write_csv(out_dir / "02-td-existing-provisional-part-mappings.csv", provisional_rows, evidence_fields)
    write_csv(out_dir / "03-name-candidates.csv", name_candidates, candidate_fields)
    write_csv(out_dir / "04-name-candidates-part-revalidated.csv", revalidated, candidate_fields)
    write_csv(out_dir / "05-name-candidate-part-conflicts.csv", part_conflicts, candidate_fields)
    write_csv(out_dir / "06-unmatched-stihl-looking.csv", unmatched, candidate_fields)
    write_csv(out_dir / "07-same-part-branch-name-variants.csv", variant_rows, [
        "canonical_stihl_part_key", "branches", "distinct_busy_names", "busy_names_exact",
    ])

    exact_parts = {r["canonical_stihl_part_key"] for r in exact_rows if r["canonical_stihl_part_key"]}
    provisional_parts = {r["canonical_stihl_part_key"] for r in provisional_rows if r["canonical_stihl_part_key"]}
    exact_alias_variants = sum(max(0, len(v) - 1) for v in exact_by_part.values())

    summary = {
        "schema": SCHEMA,
        "policy": {
            "foundation": "BUSY identity first; normalization and commercial enrichment later",
            "exact_acceptance": "BUSY alias/part key equals matched STIHL canonical part number",
            "branch_source_text": "preserve exact BUSY name, print name, alias, item code and unit",
            "td_corrected_mappings": "retain as provisional evidence unless exact part identity is independently revalidated",
            "name_logic": "candidate generation only; never auto-accept a fuzzy name match",
            "prices_required_for_identity": False,
            "busy_writeback": False,
            "aws_write": False,
        },
        "sources": {
            "td_match_csv": str(td_match_csv),
            "busy_master_csv": str(busy_master_csv),
            "existing_admission_csv": str(existing_admission_csv),
        },
        "counts": {
            "td_rows": len(td_rows),
            "busy_master_rows": len(busy_master_rows),
            "stihl_looking_rows": sum(1 for r in evidence_rows if r["stihl_looking"]),
            "exact_part_accepted_rows": len(exact_rows),
            "exact_part_accepted_unique_parts": len(exact_parts),
            "exact_part_additional_branch_alias_rows": exact_alias_variants,
            "provisional_existing_or_td_corrected_rows": len(provisional_rows),
            "provisional_unique_parts": len(provisional_parts),
            "name_candidates_need_part_evidence": len(name_candidates),
            "name_candidates_part_revalidated": len(revalidated),
            "name_candidate_part_conflicts": len(part_conflicts),
            "unmatched_stihl_looking_rows": len(unmatched),
            "canonical_parts_with_branch_name_variants": len(variant_rows),
        },
        "by_branch": {branch: dict(sorted(values.items())) for branch, values in sorted(branch_counts.items()) if branch},
        "outputs": {
            "exact_part_accepted": str(out_dir / "01-exact-part-accepted.csv"),
            "provisional_part_mappings": str(out_dir / "02-td-existing-provisional-part-mappings.csv"),
            "name_candidates": str(out_dir / "03-name-candidates.csv"),
            "part_revalidated": str(out_dir / "04-name-candidates-part-revalidated.csv"),
            "part_conflicts": str(out_dir / "05-name-candidate-part-conflicts.csv"),
            "unmatched": str(out_dir / "06-unmatched-stihl-looking.csv"),
            "branch_name_variants": str(out_dir / "07-same-part-branch-name-variants.csv"),
        },
    }
    (out_dir / "00-summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Reconcile existing BUSY/TD STIHL identity evidence without deploying or changing BUSY.")
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
