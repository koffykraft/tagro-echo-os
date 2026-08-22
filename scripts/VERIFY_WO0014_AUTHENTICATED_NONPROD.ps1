param(
    [Parameter(Mandatory=$true)][string]$Jwt,
    [string]$AwsProfile = 'tagro-echo-nonprod',
    [string]$Region = 'ap-south-1',
    [string]$Endpoint = 'https://3n1lhlcush.execute-api.ap-south-1.amazonaws.com',
    [string]$EnterpriseId,
    [string]$ReferenceKind = 'products',
    [string]$ReferenceQuery = '',
    [string]$BranchCode,
    [string]$BusinessDate = (Get-Date -Format 'yyyy-MM-dd'),
    [string]$EvidenceRoot = (Join-Path $env:TEMP 'tagro-echo-deploy-evidence\wo0014'),
    [switch]$RunWriteReadback
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$ExpectedAccount = '272037674623'
$ExpectedEndpoint = 'https://3n1lhlcush.execute-api.ap-south-1.amazonaws.com'

function AwsJson([string[]]$Arguments) {
    $raw = & aws @Arguments --profile $AwsProfile --region $Region --output json
    if ($LASTEXITCODE -ne 0) { throw "AWS command failed: aws $($Arguments -join ' ')" }
    return ($raw | ConvertFrom-Json)
}

function Write-Utf8NoBom([string]$Path, [string]$Content) {
    [System.IO.File]::WriteAllText($Path, $Content, (New-Object System.Text.UTF8Encoding($false)))
}

function Invoke-EchoGet([string]$Path, [hashtable]$Query = @{}) {
    $uri = $Endpoint.TrimEnd('/') + $Path
    if ($Query.Count -gt 0) {
        $pairs = foreach ($key in $Query.Keys) {
            if ($null -ne $Query[$key] -and [string]$Query[$key] -ne '') {
                [System.Uri]::EscapeDataString([string]$key) + '=' + [System.Uri]::EscapeDataString([string]$Query[$key])
            }
        }
        if ($pairs) { $uri += '?' + ($pairs -join '&') }
    }
    return Invoke-RestMethod -Method Get -Uri $uri -Headers @{ Authorization = "Bearer $Jwt" }
}

function Invoke-EchoPost([string]$Path, [hashtable]$Body) {
    $uri = $Endpoint.TrimEnd('/') + $Path
    $json = $Body | ConvertTo-Json -Depth 10 -Compress
    return Invoke-RestMethod -Method Post -Uri $uri -Headers @{ Authorization = "Bearer $Jwt" } -ContentType 'application/json' -Body $json
}

if ($Endpoint.TrimEnd('/') -ne $ExpectedEndpoint) {
    throw "REFUSED: endpoint $Endpoint does not match governed NonProd endpoint $ExpectedEndpoint"
}
if ([string]::IsNullOrWhiteSpace($Jwt)) { throw 'JWT is required.' }

$identity = AwsJson @('sts','get-caller-identity')
if ([string]$identity.Account -ne $ExpectedAccount) {
    throw "REFUSED: profile $AwsProfile is account $($identity.Account), expected NonProd account $ExpectedAccount."
}

$whoami = Invoke-EchoGet '/whoami'
if ([string]::IsNullOrWhiteSpace([string]$whoami.subject)) { throw 'Authenticated /whoami did not return a subject.' }

$dbHealth = Invoke-EchoGet '/db-health'
if ([string]$dbHealth.status -ne 'database_reachable') { throw "Database proof failed: $($dbHealth | ConvertTo-Json -Compress)" }

$tenant = Invoke-EchoGet '/tenant-context'
$memberships = @($tenant.enterprises)
if ($memberships.Count -lt 1) { throw 'Authenticated principal has no enterprise membership.' }

if ([string]::IsNullOrWhiteSpace($EnterpriseId)) {
    if ($memberships.Count -ne 1) { throw 'EnterpriseId is required because the authenticated principal has multiple enterprise memberships.' }
    $EnterpriseId = [string]$memberships[0].enterprise_id
}
$membership = @($memberships | Where-Object { [string]$_.enterprise_id -eq $EnterpriseId })
if ($membership.Count -ne 1) { throw "EnterpriseId $EnterpriseId is not an admitted membership for this principal." }

$reference = Invoke-EchoGet '/reference-data' @{ enterprise_id=$EnterpriseId; kind=$ReferenceKind; q=$ReferenceQuery; limit='5' }

$write = $null
$readback = $null
if ($RunWriteReadback) {
    if ([string]::IsNullOrWhiteSpace($BranchCode)) { throw 'BranchCode is required with -RunWriteReadback.' }
    $caps = @($membership[0].capabilities | ForEach-Object { ([string]$_).ToUpperInvariant() })
    if ('CASH' -notin $caps) { throw 'Authenticated membership lacks CASH capability; refusing write/readback proof.' }

    $proofKey = 'wo0014-proof-' + [guid]::NewGuid().ToString('N')
    $write = Invoke-EchoPost '/cash-days/open' @{
        enterprise_id = $EnterpriseId
        branch_code = $BranchCode.ToUpperInvariant()
        business_date = $BusinessDate
        opening_cash = 0
        idempotency_key = $proofKey
        note = 'WO-0014 NonProd deployment proof only'
    }
    if ([string]::IsNullOrWhiteSpace([string]$write.data.session_id)) { throw 'Cash-day write did not return a session_id.' }

    $readback = Invoke-EchoGet '/cash-days' @{
        enterprise_id = $EnterpriseId
        branch = $BranchCode.ToUpperInvariant()
        business_date = $BusinessDate
        limit = '10'
    }
    $sessionId = [string]$write.data.session_id
    $readbackJson = $readback | ConvertTo-Json -Depth 12 -Compress
    if ($readbackJson -notmatch [regex]::Escape($sessionId)) {
        throw "Write/readback proof failed: session_id $sessionId was not found in database-backed /cash-days readback."
    }
}

New-Item -ItemType Directory -Path $EvidenceRoot -Force | Out-Null
$timestamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$evidencePath = Join-Path $EvidenceRoot ("wo0014-auth-proof-$timestamp.json")
$evidence = [ordered]@{
    schema = 'tagro.echo.wo0014-authenticated-nonprod-proof/1'
    recorded_at_utc = (Get-Date).ToUniversalTime().ToString('o')
    aws_profile = $AwsProfile
    region = $Region
    caller_account = [string]$identity.Account
    caller_arn = [string]$identity.Arn
    endpoint = $Endpoint
    whoami = $whoami
    db_health = $dbHealth
    tenant_context = $tenant
    enterprise_id = $EnterpriseId
    reference_kind = $ReferenceKind
    reference_query = $ReferenceQuery
    reference_result = $reference
    write_readback_requested = [bool]$RunWriteReadback
    operational_write = $write
    operational_readback = $readback
    claims_not_proven = @(
        'Planar population reconciliation unless separately evidenced',
        'BUSY booked/live state',
        'web/PWA hosting smoke',
        'production deployment or admission'
    )
}
Write-Utf8NoBom -Path $evidencePath -Content ($evidence | ConvertTo-Json -Depth 20)

Write-Host 'AUTHENTICATED NONPROD REFERENCE PROOF PASS'
if ($RunWriteReadback) { Write-Host 'CONTROLLED NONPROD WRITE/READBACK PROOF PASS' }
Write-Host "Evidence: $evidencePath"
