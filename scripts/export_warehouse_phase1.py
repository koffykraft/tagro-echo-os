from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest(root: Path) -> dict[str, Any]:
    return json.loads((root / "manifests" / "latest.json").read_text(encoding="utf-8"))


def export_phase1(root: Path) -> dict[str, Any]:
    manifest = load_manifest(root)
    planar = root / "databases" / "planar.sqlite"
    if not planar.is_file():
        raise FileNotFoundError(planar)

    expected = manifest.get("databases", {}).get("planar", {}).get("sha256")
    actual = sha256(planar)
    if expected and expected != actual:
        raise RuntimeError(f"planar digest mismatch: manifest={expected} actual={actual}")

    uri = f"file:{planar.as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as db:
        rows = db.execute(
            "select branch_id, name, status from branches order by branch_id"
        ).fetchall()

    observations: list[dict[str, Any]] = []
    for branch_id, name, status in rows:
        ref = f"warehouse:planar:branch:{branch_id}"
        provenance = f"{manifest.get('run_id','')}:{actual}:branches:{branch_id}"
        observations.extend(
            [
                {
                    "subject_kind": "branch",
                    "source_subject_ref": ref,
                    "dimension_code": "branch.code",
                    "value": branch_id,
                    "confidence": 1.0,
                    "provenance_ref": provenance,
                },
                {
                    "subject_kind": "branch",
                    "source_subject_ref": ref,
                    "dimension_code": "branch.name",
                    "value": name,
                    "confidence": 1.0,
                    "provenance_ref": provenance,
                },
                {
                    "subject_kind": "branch",
                    "source_subject_ref": ref,
                    "dimension_code": "branch.operational_state",
                    "value": status,
                    "confidence": 0.6,
                    "provenance_ref": provenance,
                },
            ]
        )

    return {
        "schema": "tagro.echo-os.import-observation-package/1",
        "phase": "warehouse_phase1_branches",
        "source_system": "TAGRO_AWS_OS_WAREHOUSE",
        "source_locator": "databases/planar.sqlite#branches",
        "source_class": "warehouse_derived_historical_backbone",
        "source_as_of": manifest.get("completed_at"),
        "immutable_ref": actual,
        "warehouse_run_id": manifest.get("run_id"),
        "observations": observations,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--warehouse-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    root = Path(args.warehouse_root)
    package = export_phase1(root)
    Path(args.output).write_text(
        json.dumps(package, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps({"status": "exported", "observations": len(package["observations"]), "output": args.output}))


if __name__ == "__main__":
    main()
