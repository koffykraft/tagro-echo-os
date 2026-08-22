param(
    [string]$RuntimeRoot = 'T:\TAGRO_AWS_RUNTIME',
    [string]$RepositoryRef = 'wo-0012-nonprod-shared-runtime'
)

$ErrorActionPreference = 'Stop'
$source = Join-Path $RuntimeRoot 'data\canonical\tagro-data-platform\partitions\tagro_evidence_locked_to_2026-03-31.sqlite'
$canonical = Join-Path $RuntimeRoot 'data\canonical\tagro-data-platform\tagro_history.sqlite'
$serviceRoot = Join-Path $RuntimeRoot 'services\echo-historical'
$stateRoot = Join-Path $RuntimeRoot 'state\echo-historical'
$worker = Join-Path $serviceRoot 'process_historical_echo_events.py'
$builder = Join-Path $serviceRoot 'build_sealed_historical_from_canonical.py'
$stdout = Join-Path $stateRoot 'worker.out.log'
$stderr = Join-Path $stateRoot 'worker.err.log'
$pidFile = Join-Path $stateRoot 'worker.pid'

if (!(Test-Path -LiteralPath $RuntimeRoot -PathType Container)) { throw "Runtime root not found: $RuntimeRoot" }
if (!(Test-Path -LiteralPath $canonical -PathType Leaf)) { throw "Canonical history not found: $canonical" }
if (!(Get-Command python -ErrorAction SilentlyContinue)) { throw 'python is unavailable.' }
& python -c "import sqlite3,json,hashlib,pathlib,sys; print(sys.version)" | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Python prerequisite check failed.' }

New-Item -ItemType Directory -Force -Path $serviceRoot,$stateRoot | Out-Null
$base = "https://raw.githubusercontent.com/koffykraft/tagro-echo-os/$RepositoryRef/scripts"
Invoke-WebRequest -UseBasicParsing -Uri "$base/process_historical_echo_events.py" -OutFile $worker
Invoke-WebRequest -UseBasicParsing -Uri "$base/build_sealed_historical_from_canonical.py" -OutFile $builder
foreach ($script in @($worker,$builder)) {
    if (!(Test-Path -LiteralPath $script -PathType Leaf)) { throw "Historical component download failed: $script" }
    & python -m py_compile $script
    if ($LASTEXITCODE -ne 0) { throw "Historical component syntax check failed: $script" }
}

# Avoid duplicate workers before doing expensive bootstrap work.
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

# If the sealed partition was never copied to AWS, rebuild it locally from the verified canonical history.
if (!(Test-Path -LiteralPath $source -PathType Leaf)) {
    Write-Host 'Sealed historical partition absent on AWS runtime; rebuilding locally from canonical history through 2026-03-31.'
    & python $builder --runtime-root $RuntimeRoot
    if ($LASTEXITCODE -ne 0) { throw "Historical sealed-partition bootstrap failed with exit code $LASTEXITCODE" }
}

# Validate the resulting sealed source read-only before background work.
& python -c "import sqlite3,sys; p=sys.argv[1]; c=sqlite3.connect('file:'+p.replace('\\','/')+'?mode=ro&immutable=1',uri=True); q=c.execute('pragma quick_check').fetchone()[0]; n=c.execute('select count(*) from vouchers').fetchone()[0]; mx=c.execute('select max(vch_date) from vouchers').fetchone()[0]; c.close(); print('Historical preflight: quick_check='+str(q)+' vouchers='+str(n)+' max_date='+str(mx)); raise SystemExit(0 if q=='ok' and n>0 and mx<='2026-03-31' else 2)" $source
if ($LASTEXITCODE -ne 0) { throw 'Historical source preflight failed.' }

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
