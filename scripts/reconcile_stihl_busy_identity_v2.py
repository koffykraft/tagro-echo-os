from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

SCHEMA = "tagro.echo.stihl-identity-reconciliation/2"

MODEL_RE = re.compile(
    r"\b(?:MS|MSE|MSA|FS|FSE|FSA|FR|FT|SR|BR|BG|BGA|SH|HS|HSA|HT|HTA|KM|KA|RE|SE|SG|TS|BT)\s*[- ]?\s*\d+[A-Z0-9]*\b",
    re.I,
)
STOPWORDS = {
    "STIHL", "PART", "PARTS", "ASSEMBLY", "ASSY", "COMPLETE", "KIT", "NEW", "OLD",
    "FOR", "WITH", "WITHOUT", "AND", "THE", "OF", "A", "AN", "PCS", "PC", "NOS", "NO",
}
EACH_UNITS = {"PC", "PCS", "PIECE", "PIECES", "NO", "NOS", "NUMBER", "NUMBERS", "EACH"}


def raw(value: Any) -> str:
    return "" if value is None else str(value)


def text(value: Any) -> str:
    return raw(value).strip()


def compact(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]+", "", text(value).upper())


def stihl_part_key(value: Any) -> str:
    """Return a conservative STIHL part key. Identity admission is numeric-only here."""
    s = compact(value)
    if not s.isdigit() or not 7 <= len(s) <= 11:
        return ""
    return s.zfill(11) if len(s) < 11 else s


def name_key(value: Any) -> str:
    s = text(value).upper().replace("Ã˜", " ")
    s = re.sub(r"[^A-Z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def tokens(value: Any) -> set[str]:
    return {token for token in name_key(value).split() if len(token) > 1 and token not in STOPWORDS}


def models(value: Any) -> set[str]:
    return {re.sub(r"[^A-Z0-9]+", "", match.upper()) for match in MODEL_RE.findall(raw(value))}


def unit_family(value: Any) -> str:
    s = re.sub(r"[^A-Z0-9]+", "", text(value).upper())
    if not s:
        return "UNKNOWN"
    if s in EACH_UNITS:
        return "EACH"
    if s in {"LINK", "LINKS"}:
        return "LINK"
    if s in {"ROL", "ROLL", "ROLLS"}:
        return "ROLL"
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


def require_fields(fields: Iterable[str], required: set[str], label: str) -> None:
    missing = sorted(required - set(fields))
    if missing:
        raise RuntimeError(f"{label} missing required columns: {missing}")


def split_codes(value: Any) -> list[str]:
    result: list[str] = []
    for token in re.split(r"[|,;]+", text(value)):
        token = token.strip()
        if token and token not in result:
            result.append(token)
    return result


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def direct_key(branch: Any, item_name: Any, part: Any) -> tuple[str, str, str]:
    return text(branch).upper(), name_key(item_name), stihl_part_key(part)


def candidate_by_name(
    names: list[str],
    exact_name_index: dict[str, set[str]],
    model_index: dict[str, set[str]],
    canonical_names: dict[str, list[str]],
) -> tuple[str, str, float]:
    for value in names:
        nk = name_key(value)
        owners = exact_name_index.get(nk, set()) if nk else set()
        if len(owners) == 1:
            return next(iter(owners)), "exact_normalized_name", 1.0

    row_models = models(" ".join(names))
    possible: set[str] = set()
    for model in row_models:
        possible.update(model_index.get(model, set()))
    row_tokens = tokens(" ".join(names))
    if not possible or not row_tokens:
        return "", "", 0.0

    scored: list[tuple[float, str]] = []
    for part in possible:
        best = 0.0
        for known_name in canonical_names.get(part, []):
            known_tokens = tokens(known_name)
            if not known_tokens:
                continue
            union = row_tokens | known_tokens
            score = len(row_tokens & known_tokens) / len(union) if union else 0.0
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
    master_rows, master_fields = read_csv(busy_master_csv)
    admission_rows, admission_fields = read_csv(existing_admission_csv)

    require_fields(
        td_fields,
        {"branch", "item_code", "busy_name", "busy_alias", "busy_part_key", "print_name", "match_status"},
        "TD match CSV",
    )
    require_fields(
        master_fields,
        {"Branch", "Source row", "Item Name", "Alias / Part No", "Part No Normalized", "Parent Group", "Unit"},
        "BUSY all-branch master",
    )
    require_fields(
        admission_fields,
        {"Branch", "Original TAGRO item name", "BUSY item codes", "BUSY alias", "STIHL part number"},
        "existing STIHL admission CSV",
    )

    proven_parts: dict[str, list[dict[str, Any]]] = defaultdict(list)
    direct_seed_keys: set[tuple[str, str, str]] = set()
    canonical_names: dict[str, list[str]] = defaultdict(list)
    item_codes_by_key: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    td_rows_by_branch_name: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    admission_rows_by_branch_name: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)

    def add_name(part: str, value: Any) -> None:
        if part and text(value) and raw(value) not in canonical_names[part]:
            canonical_names[part].append(raw(value))

    # TD proves an exact STIHL identity only when the official STIHL lookup itself
    # returned the same part number as the BUSY alias. TAGRO-master corrections are
    # retained later as review evidence, never promoted here merely because populated.
    for row in td_rows:
        branch = text(row.get("branch")).upper()
        nk = name_key(row.get("busy_name"))
        td_rows_by_branch_name[(branch, nk)].append(row)
        busy_part = stihl_part_key(row.get("busy_alias") or row.get("busy_part_key"))
        official_part = stihl_part_key(row.get("stihl_part_no"))
        key = (branch, nk, busy_part)
        if text(row.get("item_code")) and busy_part:
            item_codes_by_key[key].add(text(row.get("item_code")))
        if text(row.get("match_status")).lower() == "matched_price" and official_part and official_part == busy_part:
            evidence = {
                "source": "TD",
                "branch": branch,
                "item_code": raw(row.get("item_code")),
                "busy_name_raw": raw(row.get("busy_name")),
                "busy_alias_raw": raw(row.get("busy_alias")),
                "stihl_part_no_raw": raw(row.get("stihl_part_no")),
                "method": "td_official_stihl_part_equals_busy_alias",
            }
            proven_parts[official_part].append(evidence)
            direct_seed_keys.add(key)
            for value in (row.get("busy_name"), row.get("print_name"), row.get("tagro_name"), row.get("stihl_name")):
                add_name(official_part, value)

    # The prior one-row-per-item admission file is also accepted as exact identity
    # evidence when its BUSY alias and stated STIHL part number are identical.
    for row in admission_rows:
        branch = text(row.get("Branch")).upper()
        nk = name_key(row.get("Original TAGRO item name"))
        admission_rows_by_branch_name[(branch, nk)].append(row)
        busy_part = stihl_part_key(row.get("BUSY alias"))
        official_part = stihl_part_key(row.get("STIHL part number"))
        key = (branch, nk, busy_part)
        for code in split_codes(row.get("BUSY item codes")):
            if busy_part:
                item_codes_by_key[key].add(code)
        if official_part and official_part == busy_part:
            evidence = {
                "source": "EXISTING_ADMISSION",
                "branch": branch,
                "item_code": raw(row.get("BUSY item codes")),
                "busy_name_raw": raw(row.get("Original TAGRO item name")),
                "busy_alias_raw": raw(row.get("BUSY alias")),
                "stihl_part_no_raw": raw(row.get("STIHL part number")),
                "method": "existing_admission_stihl_part_equals_busy_alias",
            }
            proven_parts[official_part].append(evidence)
            direct_seed_keys.add(key)
            for value in (row.get("Original TAGRO item name"), row.get("TAGRO display name"), row.get("Official STIHL name")):
                add_name(official_part, value)

    proven_part_keys = set(proven_parts)
    if not proven_part_keys:
        raise RuntimeError("No exact STIHL part identities were proven from TD/admission evidence")

    accepted_rows: list[dict[str, Any]] = []
    accepted_master_ids: set[tuple[str, str]] = set()
    branch_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    # This is the key cross-branch expansion: once a manufacturer part number is
    # independently proven, every BUSY branch row carrying the exact same numeric
    # alias is admitted as a branch/source alias of that one canonical identity.
    for row in master_rows:
        branch = text(row.get("Branch")).upper()
        source_row = text(row.get("Source row"))
        name = raw(row.get("Item Name"))
        alias = raw(row.get("Alias / Part No"))
        part = stihl_part_key(alias) or stihl_part_key(row.get("Part No Normalized"))
        if part not in proven_part_keys:
            continue
        key = direct_key(branch, name, part)
        item_codes = set(item_codes_by_key.get(key, set()))
        # Fall back to exact branch+name evidence if the old all-branch master has no item-code column.
        for td in td_rows_by_branch_name.get((branch, name_key(name)), []):
            if stihl_part_key(td.get("busy_alias") or td.get("busy_part_key")) == part and text(td.get("item_code")):
                item_codes.add(text(td.get("item_code")))
        for adm in admission_rows_by_branch_name.get((branch, name_key(name)), []):
            if stihl_part_key(adm.get("BUSY alias")) == part:
                item_codes.update(split_codes(adm.get("BUSY item codes")))
        accepted = {
            "branch": branch,
            "source_row": source_row,
            "busy_item_codes_evidence": " | ".join(sorted(item_codes)),
            "busy_name_raw": name,
            "busy_alias_raw": alias,
            "busy_part_key": part,
            "busy_unit_raw": raw(row.get("Unit")),
            "busy_unit_family": unit_family(row.get("Unit")),
            "busy_parent_group_raw": raw(row.get("Parent Group")),
            "opening_stock_raw": raw(row.get("Opening Stock")),
            "canonical_stihl_part_key": part,
            "identity_class": "EXACT_PART_ACCEPT",
            "identity_method": "busy_master_alias_equals_proven_stihl_part",
            "direct_seed_evidence": key in direct_seed_keys,
        }
        accepted_rows.append(accepted)
        accepted_master_ids.add((branch, source_row))
        branch_counts[branch]["exact_part_accept"] += 1
        if not accepted["direct_seed_evidence"]:
            branch_counts[branch]["cross_branch_exact_expansion"] += 1
        add_name(part, name)

    exact_by_part: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in accepted_rows:
        exact_by_part[row["canonical_stihl_part_key"]].append(row)

    variant_rows: list[dict[str, Any]] = []
    unit_rows: list[dict[str, Any]] = []
    for part, rows in sorted(exact_by_part.items()):
        branches: list[str] = []
        names: list[str] = []
        aliases: list[str] = []
        units: list[str] = []
        families: list[str] = []
        for row in rows:
            for value, collection in (
                (row["branch"], branches),
                (row["busy_name_raw"], names),
                (row["busy_alias_raw"], aliases),
                (row["busy_unit_raw"], units),
                (row["busy_unit_family"], families),
            ):
                if value not in collection:
                    collection.append(value)
        known_families = sorted({f for f in families if f and f != "UNKNOWN"})
        if len(names) > 1 or len(branches) > 1:
            variant_rows.append({
                "canonical_stihl_part_key": part,
                "branches": " | ".join(branches),
                "distinct_busy_names": len(names),
                "busy_names_exact": " || ".join(names),
                "busy_aliases_exact": " || ".join(aliases),
            })
        if len(units) > 1 or len(known_families) > 1:
            unit_rows.append({
                "canonical_stihl_part_key": part,
                "branches": " | ".join(branches),
                "busy_units_exact": " | ".join(units),
                "unit_families": " | ".join(known_families),
                "unit_state": "CONFLICT_REVIEW" if len(known_families) > 1 else "LABEL_VARIANT_ONLY",
                "conversion_inferred": False,
            })

    # Keep corrected-number evidence separate. These are useful candidates but are
    # not part of the first exact-identity admission.
    official_corrections: list[dict[str, Any]] = []
    tagro_candidates: list[dict[str, Any]] = []
    seen_corrections: set[tuple[str, str, str, str, str]] = set()
    for row in td_rows:
        branch = text(row.get("branch")).upper()
        busy_part = stihl_part_key(row.get("busy_alias") or row.get("busy_part_key"))
        official_part = stihl_part_key(row.get("stihl_part_no"))
        tagro_part = stihl_part_key(row.get("tagro_part_no"))
        if official_part and busy_part and official_part != busy_part:
            key = (branch, text(row.get("item_code")), busy_part, official_part, "TD")
            if key not in seen_corrections:
                seen_corrections.add(key)
                official_corrections.append({
                    "branch": branch,
                    "item_code": raw(row.get("item_code")),
                    "busy_name_raw": raw(row.get("busy_name")),
                    "busy_alias_raw": raw(row.get("busy_alias")),
                    "busy_part_key": busy_part,
                    "candidate_stihl_part_key": official_part,
                    "candidate_name_raw": raw(row.get("stihl_name")),
                    "evidence_source": "TD_STIHL_LOOKUP",
                    "review_state": "PART_NUMBER_DIFFERS_REVIEW",
                })
        elif tagro_part and busy_part and tagro_part != busy_part:
            key = (branch, text(row.get("item_code")), busy_part, tagro_part, "TAGRO")
            if key not in seen_corrections:
                seen_corrections.add(key)
                tagro_candidates.append({
                    "branch": branch,
                    "item_code": raw(row.get("item_code")),
                    "busy_name_raw": raw(row.get("busy_name")),
                    "busy_alias_raw": raw(row.get("busy_alias")),
                    "busy_part_key": busy_part,
                    "candidate_stihl_part_key": tagro_part,
                    "candidate_name_raw": raw(row.get("tagro_name")),
                    "evidence_source": "TAGRO_MASTER_ONLY",
                    "review_state": "PROVISIONAL_NOT_OFFICIAL_STIHL_PROOF",
                })
    for row in admission_rows:
        branch = text(row.get("Branch")).upper()
        busy_part = stihl_part_key(row.get("BUSY alias"))
        official_part = stihl_part_key(row.get("STIHL part number"))
        if official_part and busy_part and official_part != busy_part:
            key = (branch, text(row.get("BUSY item codes")), busy_part, official_part, "ADMISSION")
            if key not in seen_corrections:
                seen_corrections.add(key)
                official_corrections.append({
                    "branch": branch,
                    "item_code": raw(row.get("BUSY item codes")),
                    "busy_name_raw": raw(row.get("Original TAGRO item name")),
                    "busy_alias_raw": raw(row.get("BUSY alias")),
                    "busy_part_key": busy_part,
                    "candidate_stihl_part_key": official_part,
                    "candidate_name_raw": raw(row.get("Official STIHL name")),
                    "evidence_source": "EXISTING_ADMISSION",
                    "review_state": "PART_NUMBER_DIFFERS_REVIEW",
                })

    exact_name_index: dict[str, set[str]] = defaultdict(set)
    model_index: dict[str, set[str]] = defaultdict(set)
    for part, names in canonical_names.items():
        for value in names:
            nk = name_key(value)
            if nk:
                exact_name_index[nk].add(part)
            for model in models(value):
                model_index[model].add(part)

    name_candidates: list[dict[str, Any]] = []
    part_conflicts: list[dict[str, Any]] = []
    revalidated: list[dict[str, Any]] = []
    unmatched_clues: list[dict[str, Any]] = []

    for row in master_rows:
        branch = text(row.get("Branch")).upper()
        source_row = text(row.get("Source row"))
        if (branch, source_row) in accepted_master_ids:
            continue
        name = raw(row.get("Item Name"))
        alias = raw(row.get("Alias / Part No"))
        part_evidence = stihl_part_key(alias) or stihl_part_key(row.get("Part No Normalized"))
        candidate, method, score = candidate_by_name([name], exact_name_index, model_index, canonical_names)
        record = {
            "branch": branch,
            "source_row": source_row,
            "busy_name_raw": name,
            "busy_alias_raw": alias,
            "busy_part_evidence": part_evidence,
            "busy_unit_raw": raw(row.get("Unit")),
            "busy_parent_group_raw": raw(row.get("Parent Group")),
            "candidate_stihl_part_key": candidate,
            "candidate_method": method,
            "candidate_score": f"{score:.4f}" if score else "",
        }
        if candidate:
            if part_evidence == candidate:
                # Defensive: normally impossible because exact expansion above catches it.
                record["candidate_validation"] = "PART_REVALIDATED"
                revalidated.append(record)
                branch_counts[branch]["name_candidate_part_revalidated"] += 1
            elif part_evidence:
                record["candidate_validation"] = "PART_CONFLICT_REVIEW"
                part_conflicts.append(record)
                branch_counts[branch]["name_candidate_part_conflict"] += 1
            else:
                record["candidate_validation"] = "NAME_CANDIDATE_NEEDS_PART_EVIDENCE"
                name_candidates.append(record)
                branch_counts[branch]["name_candidate_needs_part_evidence"] += 1
            continue

        td_clue = td_rows_by_branch_name.get((branch, name_key(name)), [])
        adm_clue = admission_rows_by_branch_name.get((branch, name_key(name)), [])
        has_clue = (
            "STIHL" in name_key(name)
            or bool(models(name))
            or any(text(x.get("stihl_part_no")) or text(x.get("tagro_part_no")) or text(x.get("tagro_name")) for x in td_clue)
            or bool(adm_clue)
        )
        if has_clue:
            record["candidate_validation"] = "UNMATCHED_STIHL_CLUE_REVIEW"
            unmatched_clues.append(record)
            branch_counts[branch]["unmatched_stihl_clue"] += 1

    accepted_fields = [
        "branch", "source_row", "busy_item_codes_evidence", "busy_name_raw", "busy_alias_raw", "busy_part_key",
        "busy_unit_raw", "busy_unit_family", "busy_parent_group_raw", "opening_stock_raw",
        "canonical_stihl_part_key", "identity_class", "identity_method", "direct_seed_evidence",
    ]
    correction_fields = [
        "branch", "item_code", "busy_name_raw", "busy_alias_raw", "busy_part_key", "candidate_stihl_part_key",
        "candidate_name_raw", "evidence_source", "review_state",
    ]
    candidate_fields = [
        "branch", "source_row", "busy_name_raw", "busy_alias_raw", "busy_part_evidence", "busy_unit_raw",
        "busy_parent_group_raw", "candidate_stihl_part_key", "candidate_method", "candidate_score", "candidate_validation",
    ]

    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "01-exact-part-accepted-all-branches.csv", accepted_rows, accepted_fields)
    write_csv(out_dir / "02-same-part-branch-name-variants.csv", variant_rows, [
        "canonical_stihl_part_key", "branches", "distinct_busy_names", "busy_names_exact", "busy_aliases_exact",
    ])
    write_csv(out_dir / "03-exact-part-unit-variants.csv", unit_rows, [
        "canonical_stihl_part_key", "branches", "busy_units_exact", "unit_families", "unit_state", "conversion_inferred",
    ])
    write_csv(out_dir / "04-official-part-corrections-review.csv", official_corrections, correction_fields)
    write_csv(out_dir / "05-tagro-master-part-candidates-review.csv", tagro_candidates, correction_fields)
    write_csv(out_dir / "06-name-candidates-needing-part-evidence.csv", name_candidates, candidate_fields)
    write_csv(out_dir / "07-name-candidate-part-conflicts.csv", part_conflicts, candidate_fields)
    write_csv(out_dir / "08-name-candidates-part-revalidated.csv", revalidated, candidate_fields)
    write_csv(out_dir / "09-unmatched-stihl-clues.csv", unmatched_clues, candidate_fields)

    accepted_parts = set(exact_by_part)
    accepted_branches = {row["branch"] for row in accepted_rows if row["branch"]}
    unit_conflict_parts = sum(1 for row in unit_rows if row["unit_state"] == "CONFLICT_REVIEW")
    cross_branch_rows = sum(1 for row in accepted_rows if not row["direct_seed_evidence"])
    seed_evidence_rows = sum(len(rows) for rows in proven_parts.values())

    summary = {
        "schema": SCHEMA,
        "policy": {
            "foundation": "prove STIHL part identity, expand exact BUSY aliases across all branches, normalize later",
            "exact_identity_seed": "official STIHL part number equals BUSY alias, from TD official lookup or prior admission evidence",
            "cross_branch_rule": "a BUSY master row is accepted when its numeric alias equals an independently proven STIHL part key",
            "branch_source_text": "preserve exact BUSY name, alias, source row, item-code evidence and unit",
            "tagro_master_part_number": "candidate evidence only unless separately proven against official STIHL identity",
            "name_logic": "candidate generation only; no fuzzy/name match is auto-admitted",
            "unit_logic": "preserve branch units; report conflicts; infer no conversion multiplier",
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
            "busy_master_rows": len(master_rows),
            "existing_admission_rows": len(admission_rows),
            "exact_seed_evidence_rows": seed_evidence_rows,
            "exact_seed_unique_parts": len(proven_part_keys),
            "exact_part_accepted_rows": len(accepted_rows),
            "exact_part_accepted_unique_parts": len(accepted_parts),
            "exact_part_accepted_branches": len(accepted_branches),
            "exact_part_cross_branch_expansion_rows": cross_branch_rows,
            "canonical_parts_with_branch_name_variants": len(variant_rows),
            "canonical_parts_with_unit_variants": len(unit_rows),
            "canonical_parts_with_unit_conflicts": unit_conflict_parts,
            "official_part_corrections_review": len(official_corrections),
            "tagro_master_part_candidates_review": len(tagro_candidates),
            "name_candidates_need_part_evidence": len(name_candidates),
            "name_candidates_part_revalidated": len(revalidated),
            "name_candidate_part_conflicts": len(part_conflicts),
            "unmatched_stihl_clue_rows": len(unmatched_clues),
        },
        "by_branch": {branch: dict(sorted(values.items())) for branch, values in sorted(branch_counts.items()) if branch},
        "outputs": {
            "exact_part_accepted": str(out_dir / "01-exact-part-accepted-all-branches.csv"),
            "branch_name_variants": str(out_dir / "02-same-part-branch-name-variants.csv"),
            "unit_variants": str(out_dir / "03-exact-part-unit-variants.csv"),
            "official_corrections": str(out_dir / "04-official-part-corrections-review.csv"),
            "tagro_candidates": str(out_dir / "05-tagro-master-part-candidates-review.csv"),
            "name_candidates": str(out_dir / "06-name-candidates-needing-part-evidence.csv"),
            "part_conflicts": str(out_dir / "07-name-candidate-part-conflicts.csv"),
            "part_revalidated": str(out_dir / "08-name-candidates-part-revalidated.csv"),
            "unmatched_clues": str(out_dir / "09-unmatched-stihl-clues.csv"),
        },
    }
    (out_dir / "00-summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Conservative BUSY/TD STIHL identity reconciliation. No deployment or write-back.")
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
