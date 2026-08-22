from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

STATE_REL = Path("data/canonical/tagro-data-platform/state/current_fy_refresh_state.json")
VERIFY_REL = Path("data/canonical/tagro-data-platform/verification/refresh_through_2026-08-15.json")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def export_branch_state(root: Path) -> dict[str, Any]:
    state_path = root / STATE_REL
    verify_path = root / VERIFY_REL
    state = json.loads(state_path.read_text(encoding="utf-8"))
    verify = json.loads(verify_path.read_text(encoding="utf-8"))

    if state.get("status") != "complete":
        raise RuntimeError("current FY refresh is not complete")
    if not verify.get("verified") or verify.get("quick_check") != "ok":
        raise RuntimeError("current FY refresh verification is not admitted")
    if int(verify.get("foreign_key_errors") or 0) != 0:
        raise RuntimeError("current FY refresh has foreign-key errors")
    if state.get("through_date") != "2026-08-15":
        raise RuntimeError("unexpected current FY through_date")

    db_sha_state = str(state.get("extra", {}).get("database_sha256") or "")
    db_sha_verify = str(verify.get("database", {}).get("sha256") or "")
    if not db_sha_state or db_sha_state != db_sha_verify:
        raise RuntimeError("canonical database SHA mismatch between state and verification")

    state_branches = [str(x.get("branch") or "") for x in state.get("sources", []) if x.get("exists")]
    verify_branches = [str(x.get("branch") or "") for x in verify.get("coverage", [])]
    if sorted(state_branches) != sorted(verify_branches):
        raise RuntimeError("branch coverage mismatch between state and verification")

    state_sha = _sha256(state_path)
    verify_sha = _sha256(verify_path)
    observations: list[dict[str, Any]] = []
    for branch in sorted(state_branches):
        provenance = f"aws-runtime:{state['through_date']}:{db_sha_state}:{branch}"
        subject_ref = f"aws-runtime:current-fy:branch:{branch}"
        for dimension, value, confidence in (
            ("branch.code", branch, 1.0),
            ("branch.name", branch, 1.0),
            ("branch.operational_state", "active", 0.95),
        ):
            observations.append(
                {
                    "subject_kind": "branch",
                    "source_subject_ref": subject_ref,
                    "dimension_code": dimension,
                    "value": value,
                    "confidence": confidence,
                    "provenance_ref": provenance,
                }
            )

    return {
        "schema": "tagro.echo-os.import-observation-package/1",
        "phase": "aws_runtime_current_fy_branches",
        "source_system": "TAGRO_AWS_RUNTIME",
        "source_locator": str(STATE_REL).replace("\\", "/"),
        "source_class": "aws_runtime_verified_current_fy",
        "source_as_of": str(state.get("checked_at") or ""),
        "immutable_ref": f"state:{state_sha};verify:{verify_sha};db:{db_sha_state}",
        "through_date": state["through_date"],
        "financial_year": state.get("financial_year"),
        "verification_batch_id": verify.get("batch_id"),
        "observations": observations,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aws-runtime-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    package = export_branch_state(Path(args.aws_runtime_root))
    out = Path(args.output)
    out.write_text(json.dumps(package, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"status": "exported", "observation_count": len(package["observations"]), "output": str(out)}))


if __name__ == "__main__":
    main()
