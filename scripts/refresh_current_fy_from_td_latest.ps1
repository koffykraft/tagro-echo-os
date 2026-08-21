param(
    [string]$RuntimeRoot = 'T:\TAGRO_AWS_RUNTIME',
    [string]$TdConfigPath = '',
    [string]$ThroughDate = ''
)

$ErrorActionPreference = 'Stop'
if (-not $TdConfigPath) { $TdConfigPath = Join-Path $RuntimeRoot 'config\td_live_sources.json' }
if (-not $ThroughDate) { $ThroughDate = (Get-Date).ToString('yyyy-MM-dd') }

$platform = Join-Path $RuntimeRoot 'projects\tagro-data-platform'
$refresh = Join-Path $platform 'scripts\auto_refresh_current_fy.ps1'
if (!(Test-Path -LiteralPath $refresh -PathType Leaf)) { throw "Refresh engine not found: $refresh" }
if (!(Test-Path -LiteralPath $TdConfigPath -PathType Leaf)) { throw "TD config not found: $TdConfigPath" }

$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$bridgeRoot = Join-Path $RuntimeRoot "data\staging\td-latest-refresh\$stamp"
$archiveRoot = Join-Path $bridgeRoot 'archives'
$stateRoot = Join-Path $RuntimeRoot 'state\td-latest-refresh'
New-Item -ItemType Directory -Force -Path $archiveRoot,$stateRoot | Out-Null
$sourcesPath = Join-Path $bridgeRoot 'sources.json'
$selectionPath = Join-Path $stateRoot 'latest-selection.json'

$config = Get-Content -LiteralPath $TdConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
$branches = @($config.branches)
if ($branches.Count -ne 5) { throw "Expected five TD branch sources, found $($branches.Count)." }

$selected = @()
$sources = @()
foreach ($entry in $branches) {
    $branch = ([string]$entry.branch).ToUpperInvariant()
    $outbox = [string]$entry.outbox
    $snapshot = Join-Path $outbox 'latest\db12026.bds'
    $heartbeat = Join-Path $outbox 'heartbeat.json'
    if (!(Test-Path -LiteralPath $snapshot -PathType Leaf)) { throw "Newest TD snapshot missing for $branch: $snapshot" }

    $item = Get-Item -LiteralPath $snapshot
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
    if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
    Compress-Archive -LiteralPath $snapshot -DestinationPath $zip -CompressionLevel Optimal -Force

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

# Keep credentials local to this process. Prefer the existing DPAPI secret; prompt only when unavailable.
$ownsPassword = $false
if (-not $env:TAGRO_BUSY_DB_PASSWORD) {
    $dpapiSecret = Join-Path $env:LOCALAPPDATA 'TAGRO\secrets\busy-db-password.dpapi'
    if (!(Test-Path -LiteralPath $dpapiSecret)) {
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

try {
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
Write-Host "CanonicalState=$canonicalState"
