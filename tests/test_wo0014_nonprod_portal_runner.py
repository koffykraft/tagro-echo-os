from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "DEPLOY_ECHO_NONPROD_PORTAL.ps1"
OWNER_ACCESS = ROOT / "scripts" / "ENABLE_ECHO_OWNER_ACCESS.ps1"
RUNTIME = ROOT / "architecture" / "aws" / "nonprod-runtime-template.yaml"
WEB = ROOT / "architecture" / "aws" / "nonprod-web-template.yaml"


class NonprodPortalRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = RUNNER.read_text(encoding="utf-8")
        cls.owner_access = OWNER_ACCESS.read_text(encoding="utf-8")
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

    def test_runner_checks_cognito_compatibility_before_aws_writes(self):
        self.assertIn("function Test-CognitoBrowserAuthentication", self.runner)
        self.assertIn("ALLOW_USER_PASSWORD_AUTH", self.runner)
        self.assertIn("ALLOW_REFRESH_TOKEN_AUTH", self.runner)
        self.assertIn("ENABLE_ECHO_OWNER_ACCESS.ps1", self.runner)
        self.assertLess(
            self.runner.index("Test-CognitoBrowserAuthentication $RuntimeStack"),
            self.runner.index("=== CREATE/UPDATE DATA FOUNDATION (AWS WRITE) ==="),
        )

    def test_owner_access_requires_confirmation_and_correct_account(self):
        self.assertIn("ENABLE_ECHO_OWNER_ACCESS", self.owner_access)
        self.assertIn("tagro-echo-nonprod", self.owner_access)
        self.assertIn("272037674623", self.owner_access)
        self.assertIn("Wrong AWS account", self.owner_access)
        self.assertIn("$Confirm -ne $RequiredConfirmation", self.owner_access)

    def test_owner_access_preserves_the_existing_client_configuration(self):
        self.assertIn("'cognito-idp','describe-user-pool-client'", self.owner_access)
        self.assertIn("'cognito-idp','update-user-pool-client'", self.owner_access)
        self.assertIn("'--cli-input-json'", self.owner_access)
        self.assertIn("$client.PSObject.Properties[$field]", self.owner_access)
        self.assertIn("$originalFlows + 'ALLOW_USER_PASSWORD_AUTH'", self.owner_access)
        self.assertIn("'PreventUserExistenceErrors'", self.owner_access)
        self.assertIn("'EnableTokenRevocation'", self.owner_access)
        self.assertIn("'RefreshTokenRotation'", self.owner_access)
        self.assertIn("Existing authentication flow was not preserved", self.owner_access)

    def test_owner_access_uses_existing_confirmed_owner_without_password(self):
        self.assertIn("info@tagro.in", self.owner_access)
        self.assertIn("'cognito-idp','list-users'", self.owner_access)
        self.assertIn("$owners[0].UserStatus -ne 'CONFIRMED'", self.owner_access)
        self.assertNotIn("admin-create-user", self.owner_access)
        self.assertNotIn("admin-set-user-password", self.owner_access)

    def test_owner_access_writes_temporary_json_outside_dropbox_without_bom(self):
        self.assertIn("[System.IO.Path]::GetTempPath()", self.owner_access)
        self.assertIn("[guid]::NewGuid().ToString('N')", self.owner_access)
        self.assertIn("[System.Text.UTF8Encoding]::new($false)", self.owner_access)
        self.assertIn("Remove-Item -LiteralPath $requestPath -Force", self.owner_access)

    def test_owner_access_does_not_rebuild_or_change_dns(self):
        lowered = self.owner_access.lower()
        self.assertNotIn("'codebuild','start-build'", lowered)
        self.assertNotIn("'cloudformation','deploy'", lowered)
        self.assertNotIn("change-resource-record-sets", lowered)
        self.assertNotIn("create-user-pool", lowered)
        self.assertNotIn("delete-user-pool", lowered)

    def test_owner_access_has_valid_powershell_syntax_when_available(self):
        powershell = shutil.which("pwsh")
        if powershell is None:
            self.skipTest("PowerShell is unavailable in this environment")
        command = (
            "$ErrorActionPreference='Stop'; "
            "[scriptblock]::Create((Get-Content "
            "-LiteralPath 'scripts/ENABLE_ECHO_OWNER_ACCESS.ps1' -Raw)) | Out-Null"
        )
        result = subprocess.run(
            [powershell, "-NoProfile", "-Command", command],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_both_scripts_compare_extracted_cognito_ids_explicitly(self):
        for script in (self.owner_access, self.runner):
            self.assertIn("function Test-BrowserCognitoIdentity", script)
            self.assertIn("$browserPoolId -cne $PoolId", script)
            self.assertIn("$browserClientId -cne $ClientId", script)
            self.assertIn("$poolMatches.Count -ne 1", script)
            self.assertIn("$clientMatches.Count -ne 1", script)
            self.assertIn(
                "Test-BrowserCognitoIdentity -RuntimeConfig $runtimeConfig "
                "-PoolId $poolId -ClientId $clientId",
                script,
            )

    def test_cognito_identity_guard_accepts_real_ids_and_rejects_mismatches(self):
        powershell = shutil.which("pwsh")
        if powershell is None:
            self.skipTest("PowerShell is unavailable in this environment")
        command = r"""
$ErrorActionPreference = 'Stop'
$config = Get-Content -LiteralPath 'web/runtime-config.js' -Raw
$pool = 'ap-south-1_F9AcKBFpl'
$client = '7ctjur525ah5c09pb8dk9ajbgp'
foreach ($path in @('scripts/ENABLE_ECHO_OWNER_ACCESS.ps1','scripts/DEPLOY_ECHO_NONPROD_PORTAL.ps1')) {
  $script = [scriptblock]::Create((Get-Content -LiteralPath $path -Raw))
  $definition = $script.Ast.Find({
    param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
      $node.Name -eq 'Test-BrowserCognitoIdentity'
  },$true)
  if ($null -eq $definition) { throw "Missing identity guard in $path" }
  . ([scriptblock]::Create($definition.Extent.Text))
  Test-BrowserCognitoIdentity -RuntimeConfig $config -PoolId $pool -ClientId $client
  foreach ($invalid in @(
    @{ Pool='incorrect-pool'; Client=$client },
    @{ Pool=$pool; Client='incorrect-client' }
  )) {
    $rejected = $false
    try {
      Test-BrowserCognitoIdentity -RuntimeConfig $config -PoolId $invalid.Pool -ClientId $invalid.Client
    }
    catch { $rejected = $true }
    if (-not $rejected) { throw "Identity mismatch was accepted in $path" }
  }
}
"""
        result = subprocess.run(
            [powershell, "-NoProfile", "-Command", command],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
