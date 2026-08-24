#!/usr/bin/env python3
"""Build the admitted ECHO web release from an explicit manifest.

This script deliberately does not copy web/ wholesale. Historical prototypes,
review surfaces and retired experiments remain source evidence unless they are
explicitly admitted into web/deploy-manifest.txt.
"""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path, PurePosixPath


FORBIDDEN_RELEASE_PREFIXES = (
    "forms/",
    "page-builder/",
)
FORBIDDEN_RELEASE_NAMES = (
    "app.js",
    "intelligence.html",
    "intelligence.js",
    "page-builder.html",
)
FORBIDDEN_RELEASE_PATTERNS = (
    re.compile(r"^closing-cash-v\d+", re.I),
    re.compile(r"^closing-cash-table", re.I),
)


def read_manifest(path: Path) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        item = raw.strip()
        if not item or item.startswith("#"):
            continue
        posix = PurePosixPath(item)
        if posix.is_absolute() or ".." in posix.parts:
            raise SystemExit(f"unsafe manifest path: {item}")
        normalized = posix.as_posix()
        if normalized in seen:
            raise SystemExit(f"duplicate manifest path: {normalized}")
        if normalized.startswith(FORBIDDEN_RELEASE_PREFIXES):
            raise SystemExit(f"prototype path is not admitted: {normalized}")
        if normalized in FORBIDDEN_RELEASE_NAMES:
            raise SystemExit(f"retired/unadmitted asset is not admitted: {normalized}")
        if any(pattern.search(normalized) for pattern in FORBIDDEN_RELEASE_PATTERNS):
            raise SystemExit(f"historical prototype is not admitted: {normalized}")
        rows.append(normalized)
        seen.add(normalized)
    if not rows:
        raise SystemExit("web deploy manifest is empty")
    return rows


def build(web_root: Path, manifest: Path, output: Path) -> None:
    entries = read_manifest(manifest)
    required = {
        "404.html",
        "index.html",
        "login.html",
        "runtime-config.js",
        "runtime-client.js",
        "billing.html",
        "service.html",
        "stock-count.html",
        "po.html",
        "closing-cash.html",
        "sw.js",
    }
    missing_required = sorted(required.difference(entries))
    if missing_required:
        raise SystemExit("manifest missing required operational assets: " + ", ".join(missing_required))

    missing_files = [entry for entry in entries if not (web_root / Path(entry)).is_file()]
    if missing_files:
        raise SystemExit("manifest references missing files: " + ", ".join(missing_files))

    runtime_config = (web_root / "runtime-config.js").read_text(encoding="utf-8")
    if "execute-api.ap-south-1.amazonaws.com" not in runtime_config or "environment:'nonprod'" not in runtime_config:
        raise SystemExit("runtime-config.js is not the admitted ECHO nonprod AWS runtime configuration")

    index = (web_root / "index.html").read_text(encoding="utf-8")
    if "intelligence.html" in index:
        raise SystemExit("foundation release must not expose the frozen Intelligence lane")

    service_worker = (web_root / "sw.js").read_text(encoding="utf-8")
    if "intelligence.html" in service_worker or "intelligence.js" in service_worker:
        raise SystemExit("service worker still admits frozen Intelligence assets")

    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    for entry in entries:
        source = web_root / Path(entry)
        destination = output / Path(entry)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    built = sorted(p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file())
    if built != sorted(entries):
        raise SystemExit("release output differs from manifest")

    print(f"WEB RELEASE PASS files={len(entries)} output={output}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--web-root", default="web")
    parser.add_argument("--manifest", default="web/deploy-manifest.txt")
    parser.add_argument("--output", default="build/web-release")
    args = parser.parse_args()
    build(Path(args.web_root), Path(args.manifest), Path(args.output))


if __name__ == "__main__":
    main()
