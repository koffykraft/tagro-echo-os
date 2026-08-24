from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.build_web_release import build, read_manifest


ROOT = Path(__file__).resolve().parents[1]


class NonprodWebReleaseTests(unittest.TestCase):
    def test_manifest_admits_only_current_operational_surface(self):
        entries = read_manifest(ROOT / "web" / "deploy-manifest.txt")
        required = {
            "404.html",
            "index.html",
            "login.html",
            "billing.html",
            "service.html",
            "customers.html",
            "stock-count.html",
            "po.html",
            "closing-cash.html",
            "runtime-config.js",
            "runtime-client.js",
            "sw.js",
        }
        self.assertTrue(required.issubset(entries))
        self.assertNotIn("app.js", entries)
        self.assertNotIn("intelligence.html", entries)
        self.assertNotIn("intelligence.js", entries)
        self.assertNotIn("page-builder.html", entries)
        self.assertFalse(any(x.startswith("forms/") for x in entries))
        self.assertFalse(any(x.startswith("closing-cash-v") for x in entries))

    def test_release_builder_produces_exact_manifest(self):
        entries = read_manifest(ROOT / "web" / "deploy-manifest.txt")
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "web-release"
            build(ROOT / "web", ROOT / "web" / "deploy-manifest.txt", output)
            built = sorted(p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file())
            self.assertEqual(sorted(entries), built)

    def test_web_stack_is_private_cloudfront_origin(self):
        text = (ROOT / "architecture" / "aws" / "nonprod-web-template.yaml").read_text(encoding="utf-8")
        self.assertIn("OriginAccessControl", text)
        self.assertIn("BlockPublicAcls: true", text)
        self.assertIn("BlockPublicPolicy: true", text)
        self.assertIn("CloudFrontDefaultCertificate: true", text)
        self.assertIn("ResponsePagePath: /404.html", text)
        self.assertNotIn("WebsiteConfiguration", text)

    def test_data_foundation_keeps_evidence_and_warehouse_private(self):
        text = (ROOT / "architecture" / "aws" / "nonprod-data-foundation-template.yaml").read_text(encoding="utf-8")
        self.assertIn("EvidenceBucket", text)
        self.assertIn("WarehouseBucket", text)
        self.assertIn("VersioningConfiguration", text)
        self.assertGreaterEqual(text.count("BlockPublicPolicy: true"), 2)
        self.assertIn("OperationalEventBus", text)
        self.assertIn("IngestionDeadLetterQueue", text)
        self.assertIn("IngestionQueue", text)
        self.assertIn("AWS::Glue::Database", text)
        self.assertIn("AWS::Athena::WorkGroup", text)
        self.assertNotIn("Bedrock", text)
        self.assertNotIn("Planar", text)


if __name__ == "__main__":
    unittest.main()
