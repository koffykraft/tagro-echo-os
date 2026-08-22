param(
    [string]$RuntimeRoot = 'T:\TAGRO_AWS_RUNTIME',
    [string]$ConfigPath = '',
    [int]$StaleMinutes = 15
)

$ErrorActionPreference = 'Stop'
if (!$ConfigPath) {
    $ConfigPath = Join-Path (Split-Path -Parent $PSScriptRoot) 'config\td_live_sources.json'
}
if (!(Test-Path -LiteralPath $ConfigPath -PathType Leaf)) { throw "TD live config missing: $ConfigPath" }

$config = Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
$intakeRoot = Join-Path $RuntimeRoot 'intake\td-live'
$archiveRoot = Join-Path $RuntimeRoot 'archive\td-live'
$stateRoot = Join-Path $RuntimeRoot 'state\td-live'
$statePath = Join-Path $stateRoot 'latest.json'
New-Item -ItemType Directory -Force -Path $intakeRoot,$archiveRoot,$stateRoot | Out-Null

function Sha256([string]$Path) {
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
}

$now = (Get-Date).ToUniversalTime()
$results = @()
foreach ($row in @($config.branches)) {
    $branch = ([string]$row.branch).ToUpperInvariant()
    $outbox = [string]$row.outbox
    $heartbeatPath = Join-Path $outbox 'heartbeat.json'
    $snapshotPath = Join-Path $outbox 'latest\db12026.bds'
    $result = [ordered]@{branch=$branch;status='unknown';checked_at=$now.ToString('o');source_outbox=$outbox}
    try {
        if (!(Test-Path -LiteralPath $heartbeatPath -PathType Leaf)) { throw 'heartbeat_missing' }
        $heartbeat = Get-Content -LiteralPath $heartbeatPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ([string]$heartbeat.branch -ne $branch) { throw 'heartbeat_branch_mismatch' }
        if ([string]$heartbeat.status -ne 'READY') { throw 'heartbeat_not_ready' }
        if (!(Test-Path -LiteralPath $snapshotPath -PathType Leaf)) { throw 'snapshot_missing' }
        $checkedAt = [datetimeoffset]::Parse([string]$heartbeat.checked_at).ToUniversalTime()
        $ageMinutes = ($now - $checkedAt.UtcDateTime).TotalMinutes
        $result.heartbeat_checked_at = $checkedAt.ToString('o')
        $result.age_minutes = [math]::Round($ageMinutes,2)
        if ($ageMinutes -gt $StaleMinutes) {
            $result.status = 'stale'
            $result.reason = 'heartbeat_stale'
            $results += [pscustomobject]$result
            continue
        }
        $actualSha = Sha256 $snapshotPath
        $expectedSha = ([string]$heartbeat.sha256).ToLowerInvariant()
        if (!$expectedSha -or $actualSha -ne $expectedSha) { throw 'snapshot_hash_mismatch' }
        $branchRoot = Join-Path $intakeRoot $branch
        $archiveBranch = Join-Path $archiveRoot $branch
        New-Item -ItemType Directory -Force -Path $branchRoot,$archiveBranch | Out-Null
        $targetSnapshot = Join-Path $branchRoot 'db12026.bds'
        $targetHeartbeat = Join-Path $branchRoot 'heartbeat.json'
        if (Test-Path -LiteralPath $targetSnapshot -PathType Leaf) {
            $existingSha = Sha256 $targetSnapshot
            if ($existingSha -ne $actualSha) {
                $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
                Copy-Item -LiteralPath $targetSnapshot -Destination (Join-Path $archiveBranch "$stamp-db12026.bds") -Force
            }
        }
        $tmpSnapshot = "$targetSnapshot.incoming"
        Copy-Item -LiteralPath $snapshotPath -Destination $tmpSnapshot -Force
        if ((Sha256 $tmpSnapshot) -ne $actualSha) { throw 'aws_intake_copy_hash_mismatch' }
        Move-Item -LiteralPath $tmpSnapshot -Destination $targetSnapshot -Force
        Copy-Item -LiteralPath $heartbeatPath -Destination $targetHeartbeat -Force
        $result.status = 'verified_current'
        $result.sha256 = $actualSha
        $result.source_last_modified = [string]$heartbeat.source_last_modified
        $result.source_size = [int64]$heartbeat.source_size
    } catch {
        $result.status = 'unavailable_or_invalid'
        $result.reason = $_.Exception.Message
    }
    $results += [pscustomobject]$result
}

$payload = [ordered]@{
    schema = 'tagro.echo-os.td-live-intake-state/1'
    checked_at = $now.ToString('o')
    stale_after_minutes = $StaleMinutes
    canonical_write = $false
    results = $results
}
$payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $statePath -Encoding UTF8
$results | Format-Table branch,status,heartbeat_checked_at,age_minutes,reason -AutoSize

if (@($results | Where-Object {$_.status -eq 'verified_current'}).Count -eq 0) { exit 2 }
exit 0
