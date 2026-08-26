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

function Copy-StableSnapshot {
    param(
        [Parameter(Mandatory=$true)][string]$Source,
        [Parameter(Mandatory=$true)][string]$Destination,
        [Parameter(Mandatory=$true)][string]$Branch,
        [int]$Attempts = 30,
        [int]$DelayMilliseconds = 2000
    )

    $parent = Split-Path -Parent $Destination
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $lastError = $null

    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            Assert-File $Source "Newest TD snapshot for $Branch"
            $before = Get-Item -LiteralPath $Source
            if ($before.Length -le 0) { throw "Newest TD snapshot is empty for $($Branch): $Source" }

            Start-Sleep -Milliseconds 750
            $stableCheck = Get-Item -LiteralPath $Source
            if ($stableCheck.Length -ne $before.Length -or $stableCheck.LastWriteTimeUtc -ne $before.LastWriteTimeUtc) {
                throw 'TD snapshot is still changing.'
            }

            $incoming = "$Destination.incoming"
            Remove-Item -LiteralPath $incoming -Force -ErrorAction SilentlyContinue
            $sourceStream = $null
            $destStream = $null
            try {
                # Share ReadWrite/Delete so the connector may continue its normal replacement cycle.
                # If another process temporarily denies all sharing, the retry loop waits for it.
                $sourceStream = New-Object System.IO.FileStream(
                    $Source,
                    [System.IO.FileMode]::Open,
                    [System.IO.FileAccess]::Read,
                    ([System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete)
                )
                $destStream = New-Object System.IO.FileStream(
                    $incoming,
                    [System.IO.FileMode]::CreateNew,
                    [System.IO.FileAccess]::Write,
                    [System.IO.FileShare]::None
                )
                $sourceStream.CopyTo($destStream, 1048576)
                $destStream.Flush()
            } finally {
                if ($destStream) { $destStream.Dispose() }
                if ($sourceStream) { $sourceStream.Dispose() }
            }

            $after = Get-Item -LiteralPath $Source
            $copied = Get-Item -LiteralPath $incoming
            if ($before.Length -ne $after.Length -or $before.LastWriteTimeUtc -ne $after.LastWriteTimeUtc) {
                throw 'TD snapshot changed during staging copy.'
            }
            if ($copied.Length -ne $before.Length) {
                throw "Staged copy byte count mismatch for $Branch."
            }

            $copySha = (Get-FileHash -Algorithm SHA256 -LiteralPath $incoming).Hash.ToLowerInvariant()
            Move-Item -LiteralPath $incoming -Destination $Destination -Force
            return [ordered]@{
                path = $Destination
                bytes = $before.Length
                source_modified_utc = $before.LastWriteTimeUtc.ToString('o')
                sha256 = $copySha
                attempts = $attempt
            }
        } catch {
            $lastError = $_.Exception.Message
            Remove-Item -LiteralPath "$Destination.incoming" -Force -ErrorAction SilentlyContinue
            if ($attempt -lt $Attempts) { Start-Sleep -Milliseconds $DelayMilliseconds }
        }
    }

    throw "Unable to obtain a stable TD snapshot for $($Branch) after $Attempts attempts. Last error: $lastError"
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
$stableRoot = Join-Path $bridgeRoot 'stable-snapshots'
$preflightStage = Join-Path $bridgeRoot 'preflight-stage'
$preflightJsonl = Join-Path $bridgeRoot 'preflight-export.jsonl'
$stateRoot = Join-Path $RuntimeRoot 'state\td-latest-refresh'
New-Item -ItemType Directory -Force -Path $archiveRoot,$stableRoot,$stateRoot | Out-Null
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

    $stableCopy = Join-Path (Join-Path $stableRoot $branch) 'db12026.bds'
    $staged = Copy-StableSnapshot -Source $snapshot -Destination $stableCopy -Branch $branch

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
    Compress-Archive -LiteralPath $stableCopy -DestinationPath $zip -CompressionLevel Optimal -Force
    Assert-File $zip "Refresh archive for $branch"
    & tar.exe -tf $zip | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Archive validation failed for $branch." }

    $sources += [ordered]@{ branch = $branch; archive = $zip; kind = 'zip' }
    $selected += [ordered]@{
        branch = $branch
        source_snapshot = $snapshot
        stable_snapshot = $stableCopy
        source_bytes = $staged.bytes
        source_modified_utc = $staged.source_modified_utc
        source_sha256 = $staged.sha256
        stable_copy_attempts = $staged.attempts
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
    selection_rule = 'newest_available_td_snapshot_per_branch_stable_copy'
    branches = $selected
    sources_path = $sourcesPath
} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $selectionPath -Encoding UTF8

$env:TAGRO_AWS_RUNTIME_ROOT = $RuntimeRoot

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
        stable_snapshot_copy_verified = $true
    } | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $preflightPath -Encoding UTF8

    Write-Host ''
    Write-Host 'FULL PREFLIGHT PASSED - no canonical write has occurred.'
    $selected | Select-Object branch,source_modified_utc,source_bytes,stable_copy_attempts,heartbeat_state | Format-Table -AutoSize
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
$selected | Select-Object branch,source_modified_utc,source_bytes,stable_copy_attempts,heartbeat_state | Format-Table -AutoSize
Write-Host "SelectionState=$selectionPath"
Write-Host "PreflightState=$preflightPath"
Write-Host "CanonicalState=$canonicalState"
