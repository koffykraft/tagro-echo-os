param(
    [string]$RuntimeRoot = 'T:\TAGRO_AWS_RUNTIME',
    [string]$RepositoryRef = 'wo-0012-nonprod-shared-runtime'
)

$ErrorActionPreference = 'Stop'
$source = Join-Path $RuntimeRoot 'data\canonical\tagro-data-platform\partitions\tagro_evidence_locked_to_2026-03-31.sqlite'
$serviceRoot = Join-Path $RuntimeRoot 'services\echo-historical'
$stateRoot = Join-Path $RuntimeRoot 'state\echo-historical'
$worker = Join-Path $serviceRoot 'process_historical_echo_events.py'
$stdout = Join-Path $stateRoot 'worker.out.log'
$stderr = Join-Path $stateRoot 'worker.err.log'
$pidFile = Join-Path $stateRoot 'worker.pid'

if (!(Test-Path -LiteralPath $RuntimeRoot -PathType Container)) { throw "Runtime root not found: $RuntimeRoot" }
if (!(Test-Path -LiteralPath $source -PathType Leaf)) { throw "Sealed historical partition not found: $source" }
if (!(Get-Command python -ErrorAction SilentlyContinue)) { throw 'python is unavailable.' }
& python -c "import sqlite3,json,hashlib,pathlib,sys; print(sys.version)" | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Python prerequisite check failed.' }

New-Item -ItemType Directory -Force -Path $serviceRoot,$stateRoot | Out-Null
$url = "https://raw.githubusercontent.com/koffykraft/tagro-echo-os/$RepositoryRef/scripts/process_historical_echo_events.py"
Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $worker
if (!(Test-Path -LiteralPath $worker -PathType Leaf)) { throw 'Historical worker download failed.' }
& python -m py_compile $worker
if ($LASTEXITCODE -ne 0) { throw 'Historical worker syntax check failed.' }

# Validate source read-only before starting background work.
& python -c "import sqlite3,sys; p=sys.argv[1]; c=sqlite3.connect('file:'+p.replace('\\','/')+'?mode=ro&immutable=1',uri=True); q=c.execute('pragma quick_check').fetchone()[0]; n=c.execute('select count(*) from vouchers').fetchone()[0]; c.close(); print('Historical preflight: quick_check='+str(q)+' vouchers='+str(n)); raise SystemExit(0 if q=='ok' and n>0 else 2)" $source
if ($LASTEXITCODE -ne 0) { throw 'Historical source preflight failed.' }

# Avoid duplicate workers.
if (Test-Path -LiteralPath $pidFile) {
    $oldPid = (Get-Content -LiteralPath $pidFile -Raw).Trim()
    if ($oldPid -match '^\d+$') {
        $existing = Get-Process -Id ([int]$oldPid) -ErrorAction SilentlyContinue
        if ($existing) {
            Write-Host "Historical ECHO sweep already running. PID=$oldPid"
            exit 0
        }
    }
}

$proc = Start-Process -FilePath 'python' `
    -ArgumentList @($worker,'--runtime-root',$RuntimeRoot) `
    -RedirectStandardOutput $stdout `
    -RedirectStandardError $stderr `
    -WindowStyle Hidden `
    -PassThru
$proc.Id | Set-Content -LiteralPath $pidFile -Encoding ASCII
Start-Sleep -Seconds 2
if ($proc.HasExited) {
    throw "Historical worker exited immediately with code $($proc.ExitCode). See $stderr"
}

Write-Host ''
Write-Host 'Historical ECHO sweep started in background.'
Write-Host "PID=$($proc.Id)"
Write-Host "Source=$source"
Write-Host "Checkpoint=$(Join-Path $stateRoot 'checkpoint.json')"
Write-Host "Status=$(Join-Path $stateRoot 'status.json')"
Write-Host "Log=$stdout"
Write-Host "Errors=$stderr"
Write-Host 'CanonicalWrite=False'
