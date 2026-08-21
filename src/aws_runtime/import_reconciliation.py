from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from src.aws_runtime.config import RuntimeConfig
from src.aws_runtime.database import connect


SUBJECT_KINDS = {"branch", "person", "financial_sale_line", "financial_snapshot"}
DIMENSION_CODES = {
    "branch.code",
    "branch.name",
    "branch.operational_state",
    "branch.feed_state",
    "branch.feed_checked_at",
    "branch.feed_source_last_modified",
    "branch.feed_age_minutes",
    "person.name",
    "person.branch_code",
    "person.role",
    "person.phone",
    "person.email",
    "person.active_state",
    "financial.sale_cost_evidence",
    "financial.export_manifest",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4()}"


def _parse_timestamp(value: Any, fallback: datetime | None) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return fallback
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def record_observations(
    config: RuntimeConfig,
    *,
    enterprise_id: str,
    source_system: str,
    source_locator: str,
    source_class: str,
    observations: Iterable[Mapping[str, Any]],
    immutable_ref: str = "",
    source_as_of: str | None = None,
) -> Mapping[str, Any]:
    """Store source evidence without granting canonical authority.

    This function only writes import_sources/import_observations. Financial
    projection observations are deliberately supporting evidence: their presence
    never inserts or updates canonical sales, purchases, stock, cash or bank state.
    """
    if not enterprise_id or not source_system or not source_locator or not source_class:
        raise ValueError("enterprise_id, source_system, source_locator and source_class are required")

    captured_at = _now()
    source_id = _id("src")
    parsed_as_of = _parse_timestamp(source_as_of, None)

    rows = list(observations)
    for row in rows:
        if row.get("subject_kind") not in SUBJECT_KINDS:
            raise ValueError("unsupported subject_kind")
        if row.get("dimension_code") not in DIMENSION_CODES:
            raise ValueError("unsupported dimension_code")
        if not row.get("source_subject_ref"):
            raise ValueError("source_subject_ref is required")
        _parse_timestamp(row.get("observed_at"), parsed_as_of)

    with connect(config) as connection:
        with connection.transaction():
            connection.execute(
                """
                insert into import_sources
                  (source_id, enterprise_id, source_system, source_locator, source_as_of,
                   captured_at, source_class, immutable_ref, notes)
                values (%s,%s,%s,%s,%s,%s,%s,%s,'')
                """,
                (
                    source_id,
                    enterprise_id,
                    source_system,
                    source_locator,
                    parsed_as_of,
                    captured_at,
                    source_class,
                    immutable_ref,
                ),
            )
            for row in rows:
                connection.execute(
                    """
                    insert into import_observations
                      (observation_id, enterprise_id, source_id, subject_kind, source_subject_ref,
                       dimension_code, observed_value_json, observed_at, confidence,
                       acceptance_state, provenance_ref, created_at)
                    values (%s,%s,%s,%s,%s,%s,%s,%s,%s,'raw_supporting',%s,%s)
                    """,
                    (
                        _id("obs"),
                        enterprise_id,
                        source_id,
                        row["subject_kind"],
                        str(row["source_subject_ref"]),
                        row["dimension_code"],
                        json.dumps(row.get("value"), separators=(",", ":"), sort_keys=True),
                        _parse_timestamp(row.get("observed_at"), parsed_as_of),
                        row.get("confidence"),
                        str(row.get("provenance_ref") or immutable_ref or source_locator),
                        captured_at,
                    ),
                )

    return {"source_id": source_id, "observation_count": len(rows), "status": "observations_recorded"}


def reconciliation_readback(
    config: RuntimeConfig,
    *,
    enterprise_id: str,
    subject_kind: str | None = None,
) -> Mapping[str, Any]:
    """Read source evidence and reconciliation state without mutating canonical truth."""
    if subject_kind is not None and subject_kind not in SUBJECT_KINDS:
        raise ValueError("unsupported subject_kind")

    with connect(config) as connection:
        params: list[Any] = [enterprise_id]
        where = "where o.enterprise_id=%s"
        if subject_kind:
            where += " and o.subject_kind=%s"
            params.append(subject_kind)

        observations = connection.execute(
            f"""
            select o.observation_id, o.subject_kind, o.source_subject_ref, o.dimension_code,
                   o.observed_value_json, o.confidence, o.acceptance_state, o.provenance_ref,
                   s.source_system, s.source_locator, s.source_as_of, s.captured_at
            from import_observations o
            join import_sources s on s.source_id=o.source_id
            {where}
            order by o.subject_kind, o.source_subject_ref, o.dimension_code, s.captured_at
            """,
            tuple(params),
        ).fetchall()

        candidates = connection.execute(
            """
            select candidate_id, subject_kind, canonical_subject_ref, candidate_key,
                   candidate_value_json, status, confidence, evidence_json, conflict_json,
                   decision_reason, created_at, decided_at
            from reconciliation_candidates
            where enterprise_id=%s
            order by subject_kind, candidate_key, created_at
            """,
            (enterprise_id,),
        ).fetchall()

    return {
        "enterprise_id": enterprise_id,
        "observations": [
            {
                "observation_id": row[0],
                "subject_kind": row[1],
                "source_subject_ref": row[2],
                "dimension_code": row[3],
                "value": json.loads(row[4]),
                "confidence": float(row[5]) if row[5] is not None else None,
                "acceptance_state": row[6],
                "provenance_ref": row[7],
                "source_system": row[8],
                "source_locator": row[9],
                "source_as_of": row[10].isoformat() if row[10] else None,
                "captured_at": row[11].isoformat() if row[11] else None,
            }
            for row in observations
        ],
        "candidates": [
            {
                "candidate_id": row[0],
                "subject_kind": row[1],
                "canonical_subject_ref": row[2],
                "candidate_key": row[3],
                "candidate_value": json.loads(row[4]),
                "status": row[5],
                "confidence": float(row[6]) if row[6] is not None else None,
                "evidence": json.loads(row[7]),
                "conflicts": json.loads(row[8]),
                "decision_reason": row[9],
                "created_at": row[10].isoformat() if row[10] else None,
                "decided_at": row[11].isoformat() if row[11] else None,
            }
            for row in candidates
        ],
    }
