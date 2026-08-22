param(
    [string]$AwsProfile = 'tagro-echo-nonprod',
    [string]$Region = 'ap-south-1',
    [string]$WebAllowedOrigin
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if ([string]::IsNullOrWhiteSpace($WebAllowedOrigin)) {
    throw 'WebAllowedOrigin is required.'
}

$baseDeploy = Join-Path $PSScriptRoot 'DEPLOY_WO0014_NONPROD.ps1'
if (!(Test-Path -LiteralPath $baseDeploy -PathType Leaf)) {
    throw "Base deploy script missing: $baseDeploy"
}

# Reuse the proven AWS account/RDS/SAM/migration deployment path, but skip its
# obsolete Cognito-specific smoke because this runtime is intentionally open.
& $baseDeploy -AwsProfile $AwsProfile -Region $Region -WebAllowedOrigin $WebAllowedOrigin -SkipSmoke
if ($LASTEXITCODE -ne 0) {
    throw "Base runtime deployment failed with exit code $LASTEXITCODE"
}

$stackRaw = & aws cloudformation describe-stacks --stack-name echo-nonprod-runtime --profile $AwsProfile --region $Region --output json
if ($LASTEXITCODE -ne 0) { throw 'Could not read deployed runtime stack.' }
$stack = $stackRaw | ConvertFrom-Json
$outputs = @{}
foreach ($o in $stack.Stacks[0].Outputs) { $outputs[$o.OutputKey] = $o.OutputValue }
$endpoint = [string]$outputs.HttpApiEndpoint
if ([string]::IsNullOrWhiteSpace($endpoint)) { throw 'HttpApiEndpoint is missing.' }
$endpoint = $endpoint.TrimEnd('/')

$health = Invoke-RestMethod -Method Get -Uri "$endpoint/health"
if ($health.status -ne 'ok' -or $health.access -ne 'open_internal' -or $health.database_configured -ne $true) {
    throw "Runtime health did not confirm open database-backed operation: $($health | ConvertTo-Json -Compress)"
}

$whoami = Invoke-RestMethod -Method Get -Uri "$endpoint/whoami"
if ($whoami.access -ne 'open_internal' -or $whoami.enterprise_code -ne 'TAGRO') {
    throw "Open access identity check failed: $($whoami | ConvertTo-Json -Compress)"
}

$dbHealth = Invoke-RestMethod -Method Get -Uri "$endpoint/db-health"
if ($dbHealth.status -ne 'database_reachable') {
    throw "Database readback failed: $($dbHealth | ConvertTo-Json -Compress)"
}

$tenant = Invoke-RestMethod -Method Get -Uri "$endpoint/tenant-context"
if ($tenant.status -ne 'tenant_context_resolved' -or $tenant.access -ne 'open_internal') {
    throw "TAGRO runtime context check failed: $($tenant | ConvertTo-Json -Compress)"
}

Write-Host ''
Write-Host 'TAGRO RUNTIME DEPLOYED AND OPEN'
Write-Host "Runtime: $endpoint"
Write-Host 'No Cognito token is required.'
Write-Host 'Branch may be supplied as branch_code, ?branch=, or X-Tagro-Branch.'
Write-Host 'Single-letter branch alpha is accepted when it resolves uniquely (for example K or P).'
