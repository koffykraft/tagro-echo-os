#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
errors: list[str] = []


def require(path: str) -> Path:
    p = ROOT / path
    if not p.exists():
        errors.append(f"missing required file: {path}")
    return p


def load_json(path: str):
    p = require(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"invalid JSON {path}: {exc}")
        return None


constitution_path = require("governance/constitution/ECHO_OS_CONSTITUTION.md")
foundation = load_json("governance/state/ECHO_OS_FOUNDATION.json")
state = load_json("governance/state/CURRENT_STATE.json")
require("governance/decisions/DECISION_LEDGER.md")
require("governance/directives/TAGRO_VERTICAL_DEPLOYMENT_DIRECTIVE_2026-08-22.md")
require("schemas/core/EVENT_ENVELOPE.schema.json")
require("contracts/core/COMPONENT_CONTRACT.schema.json")
observer_path = require("observer/OBSERVER_CONTRACT.md")
require("ci/AI_BUILDER_PROTOCOL.md")
require("work-orders/WO-0001.json")
require("work-orders/WO-0002.json")

if foundation:
    ind = foundation.get("independence", {})
    if ind.get("legacy_tagro_runtime_dependency") is not False:
        errors.append("legacy TAGRO runtime dependency must remain false")
    if ind.get("legacy_tagro_data_dependency") is not False:
        errors.append("legacy TAGRO data dependency must remain false")
    if ind.get("busy_operational_source_of_truth") is not False:
        errors.append("BUSY must not become operational source of truth")
    control = foundation.get("control_model", {})
    if control.get("observer_operational_write_authority") is not False:
        errors.append("Observer operational write authority must remain false")
    if control.get("ai_architectural_sovereignty") is not False:
        errors.append("AI architectural sovereignty must remain false")
    if control.get("ai_consequential_truth_authority") is not False:
        errors.append("AI consequential truth authority must remain false")

if state:
    runtime = state.get("runtime", {})
    for key in (
        "aws_deployed",
        "aws_resources_created",
        "database_created",
        "warehouse_created",
        "observer_runtime_created",
        "mobile_app_created",
        "busy_adapter_created",
        "bank_adapter_created",
        "cash_adapter_created",
        "service_runtime_created",
    ):
        if runtime.get(key) not in (True, False):
            errors.append(f"runtime state {key} must be explicit boolean")

if constitution_path.exists():
    text = constitution_path.read_text(encoding="utf-8")
    required_phrases = [
        "AI builders have no architectural sovereignty",
        "BUSY is a docked accounting, finance and MIS engine",
        "Observer is structurally read-only",
        "Even the skeleton is versioned and replaceable",
    ]
    for phrase in required_phrases:
        if phrase not in text:
            errors.append(f"constitutional invariant missing: {phrase}")

if observer_path.exists():
    obs = observer_path.read_text(encoding="utf-8")
    forbidden_markers = ["adjust stock", "post to BUSY", "mutate operational truth"]
    for marker in forbidden_markers:
        if marker not in obs:
            errors.append(f"Observer prohibition missing: {marker}")

# Prevent obvious direct legacy runtime/path bleed into active source.
scan_roots = [ROOT / "src", ROOT / "contracts", ROOT / "schemas"]
for scan_root in scan_roots:
    if not scan_root.exists():
        continue
    for p in scan_root.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in {".py", ".js", ".ts", ".json", ".md", ".yaml", ".yml", ".toml"}:
            continue
        try:
            txt = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for forbidden in (
            "C:\\Users\\user\\Dropbox\\TAGRO_AUTOMATION\\projects\\tagro-os-build",
            "tagro-os-core",
            "tagro-os-staging",
        ):
            if forbidden in txt:
                errors.append(f"forbidden legacy runtime reference in {p.relative_to(ROOT)}: {forbidden}")

if errors:
    print("TAGRO ECHO OS foundation validation: FAILED")
    for err in errors:
        print(f"- {err}")
    sys.exit(1)

print("TAGRO ECHO OS foundation validation: PASS")
