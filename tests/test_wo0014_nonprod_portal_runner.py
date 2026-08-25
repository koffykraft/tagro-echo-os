from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "DEPLOY_ECHO_NONPROD_PORTAL.ps1"
RUNTIME = ROOT / "architecture" / "aws" / "nonprod-runtime-template.yaml"
WEB = ROOT / "architecture" / "aws" / "nonprod-web-template.yaml"


class NonprodPortalRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = RUNNER.read_text(encoding="utf-8")
        cls.runtime = RUNTIME.read_text(encoding="utf-8")
        cls.web = WEB.read_text(encoding="utf-8")

    def test_runner_is_explicitly_nonprod_and_account_pinned(self):
        self.assertIn("272037674623", self.runner)
        self.assertIn("tagro-echo-nonprod", self.runner)
        self.assertIn("DEPLOY_ECHO_NONPROD_PORTAL", self.runner)
        self.assertIn("Wrong AWS account", self.runner)

    def test_native_stderr_is_not_mistaken_for_native_failure(self):
        self.assertIn("$priorErrorAction = $ErrorActionPreference", self.runner)
        self.assertIn("$ErrorActionPreference = 'Continue'", self.runner)
        self.assertIn("$ErrorActionPreference = $priorErrorAction", self.runner)
        self.assertIn("$code = $LASTEXITCODE", self.runner)
        self.assertIn("if ($code -ne 0)", self.runner)

    def test_windows_json_files_are_utf8_without_bom(self):
        self.assertIn("function Write-Utf8NoBom", self.runner)
        self.assertIn("[System.Text.UTF8Encoding]::new($false)", self.runner)
        self.assertIn("Write-Utf8NoBom $paramsFile", self.runner)
        self.assertIn("Write-Utf8NoBom $reportPath", self.runner)
        self.assertNotIn("Set-Content -LiteralPath $paramsFile -Encoding UTF8", self.runner)

    def test_runner_refuses_runtime_removal_or_replacement(self):
        self.assertIn("$_.Action -eq 'Remove'", self.runner)
        self.assertIn("$_.Replacement -eq 'True'", self.runner)
        self.assertIn("$_.Replacement -eq 'Conditional'", self.runner)
        self.assertIn("Execution refused", self.runner)

    def test_live_dns_is_not_mutated(self):
        lowered = self.runner.lower()
        self.assertNotIn("route53 change-resource-record-sets", lowered)
        self.assertNotIn("cloudflare", lowered)
        self.assertIn("live_dns_changed=$false", lowered)

    def test_stable_and_smoke_origins_are_both_admitted(self):
        self.assertIn("StableWebAllowedOrigin", self.runtime)
        self.assertIn("Default: https://os.tagro.in", self.runtime)
        self.assertGreaterEqual(self.runtime.count("!Ref WebAllowedOrigin"), 1)
        self.assertGreaterEqual(self.runtime.count("!Ref StableWebAllowedOrigin"), 1)
        self.assertIn("Test-CorsOrigin $apiUrl $StableWebOrigin", self.runner)
        self.assertIn("Test-CorsOrigin $apiUrl $webUrl", self.runner)

    def test_web_origin_is_private_tls_only_cloudfront(self):
        self.assertIn("BlockPublicPolicy: true", self.web)
        self.assertIn("OriginAccessControl", self.web)
        self.assertIn("DenyInsecureTransport", self.web)
        self.assertIn("aws:SecureTransport: false", self.web)

    def test_customer_route_smoke_requires_jwt_rejection_not_404(self):
        self.assertIn("Test-ProtectedPostRoute", self.runner)
        self.assertIn("@(401,403)", self.runner)
        self.assertIn('Test-ProtectedPostRoute "$apiUrl/customers"', self.runner)

    def test_runner_smokes_every_admitted_html_page(self):
        self.assertIn("web/deploy-manifest.txt", self.runner)
        self.assertIn("EndsWith('.html')", self.runner)
        self.assertIn('Test-UrlStatus "$webUrl/$relativePath" @(200)', self.runner)

    def test_runner_builds_each_release_outside_dropbox(self):
        self.assertIn("[System.IO.Path]::GetTempPath()", self.runner)
        self.assertIn("[guid]::NewGuid()", self.runner)
        self.assertIn("'--output' $webRelease", self.runner)
        self.assertIn("'s3','sync',$webRelease", self.runner)
        self.assertNotIn("'--output' 'build/web-release'", self.runner)

    def test_runner_writes_dropbox_report_without_claiming_dns_cutover(self):
        self.assertIn("wo0014-portal-deploy", self.runner)
        self.assertIn("tagro.echo.nonprod-portal-deploy/1", self.runner)
        self.assertIn("live_dns_changed=$false", self.runner)


if __name__ == "__main__":
    unittest.main()
