param(
    [string]$RuntimeRoot = 'T:\TAGRO_AWS_RUNTIME',
    [string]$RepositoryRef = 'wo-0012-nonprod-shared-runtime',
    [string]$TaskName = 'TAGRO ECHO TD Live Intake'
)

$ErrorActionPreference = 'Stop'

$serviceRoot = Join-Path $RuntimeRoot 'services'
$configRoot = Join-Path $RuntimeRoot 'config'
New-Item -ItemType Directory -Force -Path $serviceRoot,$configRoot | Out-Null

$receiver = Join-Path $serviceRoot 'ingest_td_live_to_aws_runtime.ps1'
$config = Join-Path $configRoot 'td_live_sources.json'
$base = "https://raw.githubusercontent.com/koffykraft/tagro-echo-os/$RepositoryRef"

Invoke-WebRequest -UseBasicParsing -Uri "$base/scripts/ingest_td_live_to_aws_runtime.ps1" -OutFile $receiver
Invoke-WebRequest -UseBasicParsing -Uri "$base/config/td_live_sources.json" -OutFile $config

if (!(Test-Path -LiteralPath $receiver -PathType Leaf)) { throw 'TD live receiver was not installed.' }
if (!(Test-Path -LiteralPath $config -PathType Leaf)) { throw 'TD live source config was not installed.' }

# Prove the downloaded config is parseable before touching Task Scheduler.
$parsed = Get-Content -LiteralPath $config -Raw -Encoding UTF8 | ConvertFrom-Json
if (@($parsed.branches).Count -ne 5) { throw 'TD live source config must contain exactly five branch entries.' }

$credential = Get-Credential -UserName "$env:COMPUTERNAME\Administrator" -Message 'Enter the AWS Windows Administrator password for unattended TD live intake.'
$user = $credential.UserName
$password = $credential.GetNetworkCredential().Password

$ps = "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe"
$arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$receiver`" -RuntimeRoot `"$RuntimeRoot`" -ConfigPath `"$config`""
$action = New-ScheduledTaskAction -Execute $ps -Argument $arguments
$trigger = New-ScheduledTaskTrigger -Once -At ((Get-Date).AddMinutes(1)) -RepetitionInterval (New-TimeSpan -Minutes 5)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 4)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -User $user -Password $password -RunLevel Highest -Force -ErrorAction Stop | Out-Null

$password = $null
$credential = $null

# Run one governed cycle immediately and leave its state file as installation evidence.
& $ps -NoProfile -ExecutionPolicy Bypass -File $receiver -RuntimeRoot $RuntimeRoot -ConfigPath $config
$runExit = $LASTEXITCODE

$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
$info = $task | Get-ScheduledTaskInfo
$statePath = Join-Path $RuntimeRoot 'state\td-live\latest.json'

[pscustomobject]@{
    Task = $task.TaskName
    State = $task.State
    NextRun = $info.NextRunTime
    LastResult = $info.LastTaskResult
    ImmediateRunExit = $runExit
    StateFile = $statePath
    StateFileExists = (Test-Path -LiteralPath $statePath -PathType Leaf)
} | Format-List

if (!(Test-Path -LiteralPath $statePath -PathType Leaf)) {
    throw 'TD receiver installed, but no state file was produced by the immediate verification run.'
}

Write-Host 'TD live receiver installation complete.'
