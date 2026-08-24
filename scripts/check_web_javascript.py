#!/usr/bin/env python3
"""Syntax-check JavaScript shipped in the admitted ECHO web release."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from html.parser import HTMLParser
from pathlib import Path

from scripts.build_web_release import read_manifest


class InlineScriptParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._capture = False
        self._parts: list[str] = []
        self.scripts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "script":
            return
        attributes = {str(k).lower(): v for k, v in attrs}
        script_type = str(attributes.get("type") or "").lower()
        self._capture = "src" not in attributes and script_type in ("", "text/javascript", "application/javascript")
        self._parts = []

    def handle_data(self, data):
        if self._capture:
            self._parts.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "script" and self._capture:
            script = "".join(self._parts).strip()
            if script:
                self.scripts.append(script)
            self._capture = False
            self._parts = []


def node_check(node: str, source: str, label: str, suffix: str = ".js") -> None:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=suffix, delete=False) as tmp:
        tmp.write(source)
        tmp_path = Path(tmp.name)
    try:
        result = subprocess.run([node, "--check", str(tmp_path)], text=True, capture_output=True)
    finally:
        tmp_path.unlink(missing_ok=True)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise SystemExit(f"JavaScript syntax failure in {label}:\n{detail}")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    web = root / "web"
    entries = read_manifest(web / "deploy-manifest.txt")
    node = shutil.which("node")
    if not node:
        raise SystemExit("node is required for admitted web JavaScript syntax checking")

    checked = 0
    for entry in entries:
        path = web / entry
        if path.suffix.lower() == ".js":
            node_check(node, path.read_text(encoding="utf-8"), entry)
            checked += 1
        elif path.suffix.lower() == ".html":
            parser = InlineScriptParser()
            parser.feed(path.read_text(encoding="utf-8"))
            for index, source in enumerate(parser.scripts, 1):
                node_check(node, source, f"{entry} inline script {index}")
                checked += 1

    print(f"WEB JAVASCRIPT PASS scripts={checked}")


if __name__ == "__main__":
    main()
