param(
  [Parameter(Mandatory=$true)][string]$ExportDir,
  [Parameter(Mandatory=$true)][string]$EnterpriseId,
  [string]$Profile = 'tagro-echo-nonprod',
  [string]$Region = 'ap-south-1',
  [string]$FunctionName = 'echo-nonprod-observation-import',
  [string]$ExpectedAccount = '272037674623'
)

$ErrorActionPreference = 'Stop'
$Confirmation = 'IMPORT_NONPROD_OBSERVATIONS_V0_1'

function Fail([string]$Message) { throw $Message }
function Invoke-Aws([string[]]$Args) {
  $output = & aws @Args 2>&1
  if ($LASTEXITCODE -ne 0) { Fail ("AWS command failed: " + ($output -join "`n")) }
  return $output
}

# Preflight everything before the first observation write.
if (-not (Get-Command aws -ErrorAction SilentlyContinue)) { Fail 'AWS CLI is not available.' }
$dir = (Resolve-Path -LiteralPath $ExportDir).Path
$reportPath = Join-Path $dir 'export-report.json'
$manifestPackagePath = Join-Path $dir 'manifest-package.json'
if (-not (Test-Path -LiteralPath $reportPath -PathType Leaf)) { Fail "Missing export report: $reportPath" }
if (-not (Test-Path -LiteralPath $manifestPackagePath -PathType Leaf)) { Fail "Missing manifest package: $manifestPackagePath" }

$report = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
if ($report.canonical_write -ne $false) { Fail 'Export report does not declare canonical_write=false.' }
if (-not $report.run_hash) { Fail 'Export report has no run_hash.' }
$chunks = @($report.chunk_files)
if ($chunks.Count -ne [int]$report.chunk_count) { Fail 'Chunk list/count mismatch in export report.' }
foreach ($name in $chunks) {
  if (-not (Test-Path -LiteralPath (Join-Path $dir $name) -PathType Leaf)) { Fail "Missing chunk: $name" }
}

$identityRaw = Invoke-Aws @('sts','get-caller-identity','--profile',$Profile,'--region',$Region,'--output','json')
$identity = ($identityRaw -join "`n") | ConvertFrom-Json
if ([string]$identity.Account -ne $ExpectedAccount) { Fail "Refusing AWS account $($identity.Account); expected NonProd $ExpectedAccount." }
Invoke-Aws @('lambda','get-function','--function-name',$FunctionName,'--profile',$Profile,'--region',$Region,'--output','json') | Out-Null

$temp = Join-Path $env:TEMP ("echo-financial-import-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $temp | Out-Null
$totalImported = 0
try {
  function Import-Package([string]$PackagePath, [string]$Label) {
    $package = Get-Content -LiteralPath $PackagePath -Raw | ConvertFrom-Json
    if ([string]$package.immutable_ref -ne [string]$report.run_hash) { Fail "$Label immutable_ref differs from export run_hash." }
    $wrapper = [ordered]@{
      confirm = $Confirmation
      enterprise_id = $EnterpriseId
      package = $package
    }
    $payloadFile = Join-Path $temp ($Label + '-payload.json')
    $resultFile = Join-Path $temp ($Label + '-result.json')
    $wrapper | ConvertTo-Json -Depth 100 -Compress | Set-Content -LiteralPath $payloadFile -Encoding utf8
    & aws lambda invoke --function-name $FunctionName --payload ("fileb://" + $payloadFile) --cli-binary-format raw-in-base64-out --profile $Profile --region $Region --output json $resultFile | Out-Null
    if ($LASTEXITCODE -ne 0) { Fail "$Label Lambda invocation failed." }
    $result = Get-Content -LiteralPath $resultFile -Raw | ConvertFrom-Json
    if ($result.status -ne 'observation_import_complete') { Fail "$Label was not accepted: $($result | ConvertTo-Json -Compress)" }
    if ($result.canonical_write -ne $false) { Fail "$Label unexpectedly claimed canonical write." }
    $script:totalImported += [int]$result.observation_count
    Write-Host ("Imported {0}: observations={1} source={2} canonical_write=False" -f $Label,$result.observation_count,$result.source_id)
  }

  # The completion manifest is deliberately last. ON CALL ignores this run until
  # this final package exists, so an interrupted upload cannot produce partial P&L.
  $i = 0
  foreach ($name in $chunks) {
    $i++
    Import-Package (Join-Path $dir $name) ("chunk-{0:D4}" -f $i)
  }
  Import-Package $manifestPackagePath 'manifest-final'

  $expected = [int]$report.sale_line_observations + 1
  if ($totalImported -ne $expected) { Fail "Imported observation count $totalImported differs from expected $expected." }
  Write-Host 'Financial projection observation import complete.'
  Write-Host ("RunHash={0}" -f $report.run_hash)
  Write-Host ("SaleLines={0}" -f $report.sale_line_observations)
  Write-Host 'CanonicalWrite=False'
  Write-Host 'The final manifest is present; this evidence run is now eligible for read-only ON CALL projection.'
}
finally {
  Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue
}
