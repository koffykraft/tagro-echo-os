param(
    [string]$RuntimeRoot = 'T:\TAGRO_AWS_RUNTIME',
    [string]$TdConfigPath = '',
    [string]$ThroughDate = '',
    [switch]$PreflightOnly
)

$ErrorActionPreference = 'Stop'
if (-not $TdConfigPath) { $TdConfigPath = Join-Path $RuntimeRoot 'config\td_live_sources.json' }
if (-not $ThroughDate) { $ThroughDate = (Get-Date).ToString('yyyy-MM-dd') }

function Assert-File([string]$Path, [string]$Label) {
    if (!(Test-Path -LiteralPath $Path -PathType Leaf)) { throw "$Label not found: $Path" }
}

function Assert-Command([string]$Name) {
    if (!(Get-Command $Name -ErrorAction SilentlyContinue)) { throw "Required command is unavailable: $Name" }
}

function Assert-PowerShellParses([string]$Path) {
    $tokens = $null
    $errors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($Path, [ref]$tokens, [ref]$errors)
    if (@($errors).Count -gt 0) {
        $messages = @($errors | ForEach-Object { $_.Message }) -join '; '
        throw "PowerShell parser rejected $Path : $messages"
    }
}

if (!(Test-Path -LiteralPath $RuntimeRoot -PathType Container)) { throw "AWS runtime root not found: $RuntimeRoot" }
$platform = Join-Path $RuntimeRoot 'projects\tagro-data-platform'
$scriptRoot = Join-Path $platform 'scripts'
$refresh = Join-Path $scriptRoot 'auto_refresh_current_fy.ps1'
$stageScript = Join-Path $scriptRoot 'stage_busy_fy.ps1'
$exportScript = Join-Path $scriptRoot 'export_busy_fy.ps1'
$completeScript = Join-Path $scriptRoot 'complete_canonical_refresh.ps1'
$historyBuilder = Join-Path $scriptRoot 'build_history_db.py'
$fluidBuilder = Join-Path $scriptRoot 'build_fluid_partition.py'
$costBuilder = Join-Path $scriptRoot 'build_purchase_cost_evidence.py'
$canonicalDb = Join-Path $RuntimeRoot 'data\canonical\tagro-data-platform\tagro_history.sqlite'

Assert-File $TdConfigPath 'TD config'
Assert-File $refresh 'Refresh engine'
Assert-File $stageScript 'BUSY stage script'
Assert-File $exportScript 'BUSY export script'
Assert-File $completeScript 'Canonical completion script'
Assert-File $historyBuilder 'History database builder'
Assert-File $fluidBuilder 'Fluid partition builder'
Assert-File $costBuilder 'Purchase-cost builder'
Assert-File $canonicalDb 'Canonical history database'

Assert-Command 'Compress-Archive'
Assert-Command 'Get-FileHash'
Assert-Command 'tar.exe'
Assert-Command 'python'

foreach ($psScript in @($MyInvocation.MyCommand.Path,$refresh,$stageScript,$exportScript,$completeScript)) {
    Assert-PowerShellParses $psScript
}

& python -c "import sys,sqlite3,json,hashlib,pathlib; print(sys.version)" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Python prerequisite check failed with exit code $LASTEXITCODE" }

$hasAceOrJet = $false
$providerRegistryPaths = @(
    'HKLM:\SOFTWARE\Classes\Microsoft.ACE.OLEDB.12.0',
    'HKLM:\SOFTWARE\Classes\Microsoft.ACE.OLEDB.16.0',
    'HKLM:\SOFTWARE\WOW6432Node\Classes\Microsoft.ACE.OLEDB.12.0',
    'HKLM:\SOFTWARE\WOW6432Node\Classes\Microsoft.ACE.OLEDB.16.0',
    'HKLM:\SOFTWARE\Classes\Microsoft.Jet.OLEDB.4.0',
    'HKLM:\SOFTWARE\WOW6432Node\Classes\Microsoft.Jet.OLEDB.4.0'
)
foreach ($providerPath in $providerRegistryPaths) {
    if (Test-Path $providerPath) { $hasAceOrJet = $true; break }
}
if (-not $hasAceOrJet) {
    # The existing exporter also recognizes Office Access Connectivity Engine installations.
    $office32 = @(Get-ChildItem 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Office' -ErrorAction SilentlyContinue | Where-Object { Test-Path (Join-Path $_.PSPath 'Access Connectivity Engine') })
    $office64 = @(Get-ChildItem 'HKLM:\SOFTWARE\Microsoft\Office' -ErrorAction SilentlyContinue | Where-Object { Test-Path (Join-Path $_.PSPath 'Access Connectivity Engine') })
    $hasAceOrJet = ($office32.Count -gt 0 -or $office64.Count -gt 0)
}
if (-not $hasAceOrJet) { throw 'No Microsoft ACE/Jet OLE DB provider installation was detected.' }

$config = Get-Content -LiteralPath $TdConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
$branches = @($config.branches)
if ($branches.Count -ne 5) { throw "Expected five TD branch sources, found $($branches.Count)." }
$expectedBranches = @('KVR','PKM','NDD','MDM','SKT')
$actualBranches = @($branches | ForEach-Object { ([string]$_.branch).ToUpperInvariant() } | Sort-Object)
$expectedSorted = @($expectedBranches | Sort-Object)
if (($actualBranches -join ',') -ne ($expectedSorted -join ',')) {
    throw "TD config branch set is invalid. Expected $($expectedSorted -join ','), found $($actualBranches -join ',')."
}

$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$bridgeRoot = Join-Path $RuntimeRoot "data\staging\td-latest-refresh\$stamp"
$archiveRoot = Join-Path $bridgeRoot 'archives'
$preflightStage = Join-Path $bridgeRoot 'preflight-stage'
$preflightJsonl = Join-Path $bridgeRoot 'preflight-export.jsonl'
$stateRoot = Join-Path $RuntimeRoot 'state\td-latest-refresh'
New-Item -ItemType Directory -Force -Path $archiveRoot,$stateRoot | Out-Null
$sourcesPath = Join-Path $bridgeRoot 'sources.json'
$selectionPath = Join-Path $stateRoot 'latest-selection.json'
$preflightPath = Join-Path $stateRoot 'latest-preflight.json'

$selected = @()
$sources = @()
foreach ($entry in $branches) {
    $branch = ([string]$entry.branch).ToUpperInvariant()
    $outbox = [string]$entry.outbox
    if ([string]::IsNullOrWhiteSpace($outbox)) { throw "TD outbox path is empty for $branch." }
    $snapshot = Join-Path $outbox 'latest\db12026.bds'
    $heartbeat = Join-Path $outbox 'heartbeat.json'
    if (!(Test-Path -LiteralPath $snapshot -PathType Leaf)) { throw "Newest TD snapshot missing for $($branch): $snapshot" }

    $item = Get-Item -LiteralPath $snapshot
    if ($item.Length -le 0) { throw "Newest TD snapshot is empty for $($branch): $snapshot" }
    $sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $snapshot).Hash.ToLowerInvariant()
    $heartbeatState = 'missing'
    $heartbeatCheckedAt = $null
    if (Test-Path -LiteralPath $heartbeat -PathType Leaf) {
        try {
            $hb = Get-Content -LiteralPath $heartbeat -Raw -Encoding UTF8 | ConvertFrom-Json
            $heartbeatState = [string]$hb.status
            $heartbeatCheckedAt = [string]$hb.checked_at
        } catch {
            $heartbeatState = 'invalid'
        }
    }

    $branchArchiveRoot = Join-Path $archiveRoot $branch
    New-Item -ItemType Directory -Force -Path $branchArchiveRoot | Out-Null
    $zip = Join-Path $branchArchiveRoot ("${branch}_db12026.zip")
    Compress-Archive -LiteralPath $snapshot -DestinationPath $zip -CompressionLevel Optimal -Force
    Assert-File $zip "Refresh archive for $branch"
    & tar.exe -tf $zip | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Archive validation failed for $branch." }

    $sources += [ordered]@{ branch = $branch; archive = $zip; kind = 'zip' }
    $selected += [ordered]@{
        branch = $branch
        source_snapshot = $snapshot
        source_bytes = $item.Length
        source_modified_utc = $item.LastWriteTimeUtc.ToString('o')
        source_sha256 = $sha
        heartbeat_state = $heartbeatState
        heartbeat_checked_at = $heartbeatCheckedAt
        refresh_archive = $zip
    }
}

$sources | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $sourcesPath -Encoding UTF8
[ordered]@{
    schema = 'tagro.echo-os.td-latest-refresh-selection/1'
    selected_at = (Get-Date).ToString('o')
    through_date = $ThroughDate
    canonical_write = $false
    selection_rule = 'newest_available_td_snapshot_per_branch'
    branches = $selected
    sources_path = $sourcesPath
} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $selectionPath -Encoding UTF8

# Make every downstream Python builder resolve the AWS runtime, never the old laptop default.
$env:TAGRO_AWS_RUNTIME_ROOT = $RuntimeRoot

# Keep credentials local to this process. Load the existing Windows-encrypted secret when available;
# otherwise prompt locally. Nothing is printed or persisted by this bridge.
$ownsPassword = $false
if (-not $env:TAGRO_BUSY_DB_PASSWORD) {
    $dpapiSecret = Join-Path $env:LOCALAPPDATA 'TAGRO\secrets\busy-db-password.dpapi'
    if (Test-Path -LiteralPath $dpapiSecret -PathType Leaf) {
        try {
            $secure = Get-Content -LiteralPath $dpapiSecret -Raw | ConvertTo-SecureString
            $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
            try {
                $env:TAGRO_BUSY_DB_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
                $ownsPassword = $true
            } finally {
                [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
            }
        } catch {
            throw 'Windows-encrypted BUSY credential exists but could not be opened by this user.'
        }
    } else {
        $secure = Read-Host 'Enter the BUSY database password (input is hidden)' -AsSecureString
        $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        try {
            $env:TAGRO_BUSY_DB_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
            $ownsPassword = $true
        } finally {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
        }
    }
}
if (-not $env:TAGRO_BUSY_DB_PASSWORD) { throw 'BUSY database credential is unavailable.' }

try {
    # FULL READ-ONLY DATA PREFLIGHT: extraction + OLEDB open + expected BUSY schema + FY export for all five.
    # This deliberately happens before auto_refresh_current_fy can copy or mutate the canonical SQLite database.
    & $stageScript -SourcesPath $sourcesPath -StageRoot $preflightStage -FiscalYearStart 2026
    if ($LASTEXITCODE -ne 0) { throw "Preflight stage failed with exit code $LASTEXITCODE" }
    $manifest = Get-Content -LiteralPath (Join-Path $preflightStage 'FY2026-27\staging_manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $badStage = @($manifest | Where-Object { $_.status -ne 'staged' })
    if ($badStage.Count -gt 0) { throw "Preflight could not stage: $($badStage.branch -join ', ')" }

    & $exportScript -StageRoot $preflightStage -OutputPath $preflightJsonl -FiscalYearStart 2026 -ThroughDate $ThroughDate
    if ($LASTEXITCODE -ne 0) { throw "Preflight BUSY export failed with exit code $LASTEXITCODE" }
    Assert-File $preflightJsonl 'Preflight BUSY export'
    $preflightBytes = (Get-Item -LiteralPath $preflightJsonl).Length
    if ($preflightBytes -le 0) { throw 'Preflight BUSY export was empty.' }
    $sourceRecordCount = @([System.IO.File]::ReadLines($preflightJsonl) | Where-Object { $_ -match '"record_type":"source"' }).Count
    if ($sourceRecordCount -ne 5) { throw "Preflight export expected five BUSY source records, found $sourceRecordCount." }

    [ordered]@{
        schema = 'tagro.echo-os.td-latest-refresh-preflight/1'
        checked_at = (Get-Date).ToString('o')
        status = 'passed'
        canonical_write = $false
        branches = $expectedBranches
        source_records = $sourceRecordCount
        export_bytes = $preflightBytes
        selection_state = $selectionPath
        preflight_export = $preflightJsonl
        python = (& python --version 2>&1 | Out-String).Trim()
        oledb_provider_detected = $true
        powershell_scripts_parsed = $true
    } | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $preflightPath -Encoding UTF8

    Write-Host ''
    Write-Host 'FULL PREFLIGHT PASSED - no canonical write has occurred.'
    $selected | Select-Object branch,source_modified_utc,source_bytes,heartbeat_state | Format-Table -AutoSize
    Write-Host "PreflightState=$preflightPath"

    if ($PreflightOnly) {
        Write-Host 'PreflightOnly requested; stopping before canonical refresh.'
        exit 0
    }

    & $refresh -Root $RuntimeRoot -SourcesPath $sourcesPath -ThroughDate $ThroughDate -Force
    if ($LASTEXITCODE -ne 0) { throw "Current-FY refresh failed with exit code $LASTEXITCODE" }
} finally {
    if ($ownsPassword) { Remove-Item Env:\TAGRO_BUSY_DB_PASSWORD -ErrorAction SilentlyContinue }
}

$canonicalState = Join-Path $RuntimeRoot 'data\canonical\tagro-data-platform\state\current_fy_refresh_state.json'
if (!(Test-Path -LiteralPath $canonicalState -PathType Leaf)) { throw 'Canonical refresh state file was not produced.' }
$state = Get-Content -LiteralPath $canonicalState -Raw -Encoding UTF8 | ConvertFrom-Json
if ($state.status -ne 'complete') { throw "Canonical refresh did not complete: $($state.status)" }

Write-Host ''
Write-Host 'TD newest-snapshot refresh complete.'
$selected | Select-Object branch,source_modified_utc,source_bytes,heartbeat_state | Format-Table -AutoSize
Write-Host "SelectionState=$selectionPath"
Write-Host "PreflightState=$preflightPath"
Write-Host "CanonicalState=$canonicalState"
