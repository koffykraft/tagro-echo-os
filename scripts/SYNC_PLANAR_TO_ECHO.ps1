param(
    [string]$RuntimeRoot = 'T:\TAGRO_AWS_RUNTIME',
    [string]$WarehouseRoot = 'T:\Dropbox\TAGRO_AUTOMATION\TAGRO_AWS_OS_WAREHOUSE',
    [string]$EnterpriseId = 'ae9dea8e-6021-5833-9d59-7b0613357fbe',
    [string]$AwsProfile = 'tagro-echo-nonprod',
    [string]$Region = 'ap-south-1',
    [string]$FunctionName = 'echo-nonprod-observation-import',
    [int]$BatchSize = 500,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$repoScript = Join-Path $PSScriptRoot 'sync_planar_to_echo.py'
$database = Join-Path $WarehouseRoot 'databases\planar.sqlite'
$manifest = Join-Path $WarehouseRoot 'manifests\latest.json'
$checkpoint = Join-Path $RuntimeRoot 'state\echo-planar-sync\latest.json'

if (!(Test-Path -LiteralPath $repoScript -PathType Leaf)) { throw "Sync script missing: $repoScript" }
if (!(Test-Path -LiteralPath $database -PathType Leaf)) { throw "Planar database missing: $database" }
if (!(Test-Path -LiteralPath $manifest -PathType Leaf)) { throw "Warehouse manifest missing: $manifest" }

$python = (Get-Command python.exe -ErrorAction Stop).Source
$args = @(
    $repoScript,
    '--database', $database,
    '--manifest', $manifest,
    '--checkpoint', $checkpoint,
    '--enterprise-id', $EnterpriseId,
    '--profile', $AwsProfile,
    '--region', $Region,
    '--function-name', $FunctionName,
    '--batch-size', "$BatchSize"
)
if ($DryRun) { $args += '--dry-run' }

Write-Host "ECHO PLANAR SYNC database=$database manifest=$manifest"
& $python @args
if ($LASTEXITCODE -ne 0) { throw "ECHO Planar sync failed with exit code $LASTEXITCODE" }
