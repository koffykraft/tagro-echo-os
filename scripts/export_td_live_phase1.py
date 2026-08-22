from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_package(state_path: Path) -> dict[str, Any]:
    state = json.loads(state_path.read_text(encoding="utf-8-sig"))
    if state.get("schema") != "tagro.echo-os.td-live-intake-state/1":
        raise RuntimeError("unsupported TD live intake state schema")
    checked_at = str(state.get("checked_at") or "")
    if not checked_at:
        raise RuntimeError("TD live intake state has no checked_at")
    state_sha = sha256(state_path)
    observations: list[dict[str, Any]] = []
    for row in state.get("results") or []:
        branch = str(row.get("branch") or "").upper()
        feed_state = str(row.get("status") or "unknown")
        if not branch:
            continue
        provenance = f"td-live:{state_sha}:{branch}"
        base = {
            "subject_kind": "branch",
            "source_subject_ref": f"td-live:branch:{branch}",
            "confidence": 1.0,
            "provenance_ref": provenance,
        }
        observations.append({**base, "dimension_code": "branch.code", "value": branch})
        observations.append({**base, "dimension_code": "branch.feed_state", "value": feed_state})
        observations.append({**base, "dimension_code": "branch.feed_checked_at", "value": checked_at})
        if row.get("age_minutes") is not None:
            observations.append({**base, "dimension_code": "branch.feed_age_minutes", "value": row["age_minutes"]})
        if row.get("source_last_modified"):
            observations.append(
                {**base, "dimension_code": "branch.feed_source_last_modified", "value": row["source_last_modified"]}
            )

    if not observations:
        raise RuntimeError("TD live intake state contained no branch observations")

    return {
        "schema": "tagro.echo-os.import-observation-package/1",
        "phase": "td_live_feed_health_phase1",
        "source_system": "TAGRO_TD_LIVE_AWS_INTAKE",
        "source_locator": "state/td-live/latest.json",
        "source_class": "verified_live_feed_health",
        "source_as_of": checked_at,
        "immutable_ref": state_sha,
        "observations": observations,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    state_path = Path(args.state)
    output = Path(args.output)
    package = build_package(state_path)
    output.write_text(json.dumps(package, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"status": "exported", "observations": len(package["observations"]), "output": str(output)}))


if __name__ == "__main__":
    main()
