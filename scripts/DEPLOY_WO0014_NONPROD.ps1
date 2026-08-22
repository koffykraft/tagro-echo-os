param(
    [string]$AwsProfile = 'tagro-echo-nonprod',
    [string]$Region = 'ap-south-1',
    [string]$WebAllowedOrigin,
    [string]$EvidenceRoot = (Join-Path $env:TEMP 'tagro-echo-deploy-evidence\wo0014'),
    [switch]$SkipBuild,
    [switch]$SkipMigration,
    [switch]$SkipSmoke
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$ExpectedAccount = '272037674623'
$StackName = 'echo-nonprod-runtime'
$Template = Join-Path $PSScriptRoot '..\architecture\aws\nonprod-runtime-template.yaml'
$BuiltTemplate = Join-Path $PSScriptRoot '..\.aws-sam\build\template.yaml'
$BuildRoot = Join-Path $PSScriptRoot '..\.aws-sam\build'
$UserPoolId = 'ap-south-1_F9AcKBFpl'
$UserPoolClientId = '7ctjur525ah5c09pb8dk9ajbgp'
$LambdaExecutionRoleArn = 'arn:aws:iam::272037674623:role/echo-nonprod-runtime-role'
$DbIdentifier = 'echo-nonprod-postgres'
$DbHost = 'echo-nonprod-postgres.ch6ciowm8fzs.ap-south-1.rds.amazonaws.com'
$DbName = 'echoos'
$PrivateSubnetA = 'subnet-0120b92ce4c054c06'
$PrivateSubnetB = 'subnet-0bc49cd8240da5922'
$AppSecurityGroup = 'sg-09231e827f3723d1e'
$MigrationFunction = 'echo-nonprod-schema-migrate'
$RequiredFunctions = @(
    'echo-nonprod-runtime',
    'echo-nonprod-twin-read',
    'echo-nonprod-schema-migrate',
    'echo-nonprod-enterprise-bootstrap',
    'echo-nonprod-observation-import'
)
$BuildFunctions = @(
    'EchoRuntimeFunction',
    'EchoTwinReadFunction',
    'EchoSchemaMigrationFunction',
    'EchoEnterpriseBootstrapFunction',
    'EchoObservationImportFunction'
)

function AwsJson([string[]]$Arguments) {
    $raw = & aws @Arguments --profile $AwsProfile --region $Region --output json
    if ($LASTEXITCODE -ne 0) { throw "AWS command failed: aws $($Arguments -join ' ')" }
    return ($raw | ConvertFrom-Json)
}

function Write-Utf8NoBom([string]$Path, [string]$Content) {
    [System.IO.File]::WriteAllText($Path, $Content, (New-Object System.Text.UTF8Encoding($false)))
}

function Assert-BuiltDependencies {
    foreach ($functionDir in $BuildFunctions) {
        $root = Join-Path $BuildRoot $functionDir
        if (!(Test-Path -LiteralPath $root -PathType Container)) {
            throw "Built function directory missing: $root. Run without -SkipBuild or rebuild the SAM application."
        }
        if (!(Test-Path -LiteralPath (Join-Path $root 'psycopg') -PathType Container)) {
            throw "Built package missing psycopg for $functionDir. Refusing deploy."
        }
        $typingModule = Join-Path $root 'typing_extensions.py'
        $typingPackage = Join-Path $root 'typing_extensions'
        if (!(Test-Path -LiteralPath $typingModule -PathType Leaf) -and !(Test-Path -LiteralPath $typingPackage -PathType Container)) {
            throw "Built package missing typing_extensions for $functionDir. Refusing deploy. Rebuild from src/aws_runtime/requirements.txt."
        }
    }
}

function Get-UnauthenticatedStatusCode([string]$Uri) {
    try {
        $response = Invoke-WebRequest -Method Get -Uri $Uri -UseBasicParsing
        return [int]$response.StatusCode
    }
    catch {
        if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
            return [int]$_.Exception.Response.StatusCode
        }
        throw
    }
}

if (!(Test-Path -LiteralPath $Template -PathType Leaf)) { throw "Template missing: $Template" }
if ([string]::IsNullOrWhiteSpace($WebAllowedOrigin)) {
    throw 'WebAllowedOrigin is required and must be the exact HTTPS origin that will host the TAGRO STIHL PWA.'
}
if ($WebAllowedOrigin -notmatch '^https://[^/]+(?::\d+)?$') {
    throw "WebAllowedOrigin must be an exact HTTPS origin without a path: $WebAllowedOrigin"
}

$identity = AwsJson @('sts','get-caller-identity')
if ([string]$identity.Account -ne $ExpectedAccount) {
    throw "REFUSED: profile $AwsProfile is account $($identity.Account), expected NonProd account $ExpectedAccount. No deployment attempted."
}
Write-Host "AWS identity confirmed: account=$($identity.Account) arn=$($identity.Arn)"

$db = AwsJson @('rds','describe-db-instances','--db-instance-identifier',$DbIdentifier)
$dbInstance = $db.DBInstances | Select-Object -First 1
if (!$dbInstance) { throw "RDS instance not found: $DbIdentifier" }
if ([string]$dbInstance.Endpoint.Address -ne $DbHost) {
    throw "REFUSED: RDS endpoint drift. Expected $DbHost, found $($dbInstance.Endpoint.Address)"
}
if ($dbInstance.PubliclyAccessible) { throw 'REFUSED: NonProd database unexpectedly reports PubliclyAccessible=true.' }
if ([string]$dbInstance.DBInstanceStatus -ne 'available') { throw "REFUSED: RDS status is $($dbInstance.DBInstanceStatus), expected available." }
$DbSecretArn = [string]$dbInstance.MasterUserSecret.SecretArn
if ([string]::IsNullOrWhiteSpace($DbSecretArn)) { throw 'RDS master SecretArn could not be resolved.' }
Write-Host "RDS confirmed private/available: $DbIdentifier / $DbHost"

if (!$SkipBuild) {
    Write-Host 'Building SAM application...'
    & sam build --template-file $Template
    if ($LASTEXITCODE -ne 0) { throw "sam build failed with exit code $LASTEXITCODE" }
}
if (!(Test-Path -LiteralPath $BuiltTemplate -PathType Leaf)) { throw "Built SAM template missing: $BuiltTemplate" }
Assert-BuiltDependencies

Write-Host "Deploying $StackName to $ExpectedAccount / $Region..."
& sam deploy `
    --template-file $BuiltTemplate `
    --stack-name $StackName `
    --region $Region `
    --profile $AwsProfile `
    --capabilities CAPABILITY_IAM `
    --resolve-s3 `
    --no-confirm-changeset `
    --no-fail-on-empty-changeset `
    --parameter-overrides `
        "UserPoolId=$UserPoolId" `
        "UserPoolClientId=$UserPoolClientId" `
        "WebAllowedOrigin=$WebAllowedOrigin" `
        "LambdaExecutionRoleArn=$LambdaExecutionRoleArn" `
        "DbSecretArn=$DbSecretArn" `
        "DbHost=$DbHost" `
        "DbName=$DbName" `
        "PrivateSubnetA=$PrivateSubnetA" `
        "PrivateSubnetB=$PrivateSubnetB" `
        "AppSecurityGroup=$AppSecurityGroup"
if ($LASTEXITCODE -ne 0) { throw "sam deploy failed with exit code $LASTEXITCODE" }

$stack = AwsJson @('cloudformation','describe-stacks','--stack-name',$StackName)
$stackRecord = $stack.Stacks[0]
if ([string]$stackRecord.StackStatus -notmatch '^(CREATE|UPDATE)_COMPLETE$') {
    throw "CloudFormation stack is not complete: $($stackRecord.StackStatus)"
}
$outputs = @{}
foreach ($o in ($stackRecord.Outputs | ForEach-Object { $_ })) { $outputs[$o.OutputKey] = $o.OutputValue }
if (!$outputs.HttpApiEndpoint) { throw 'Deployment completed but HttpApiEndpoint output is missing.' }
Write-Host "Runtime endpoint: $($outputs.HttpApiEndpoint)"

$migration = $null
$migrationInvoke = $null
if (!$SkipMigration) {
    $payloadFile = Join-Path $env:TEMP 'echo-wo0014-migration-payload.json'
    $responseFile = Join-Path $env:TEMP 'echo-wo0014-migration-response.json'
    Write-Utf8NoBom -Path $payloadFile -Content '{"confirm":"APPLY_NONPROD_V0_3"}'

    $invokeRaw = & aws lambda invoke --function-name $MigrationFunction --payload ("fileb://" + $payloadFile) $responseFile --profile $AwsProfile --region $Region --cli-binary-format raw-in-base64-out --output json
    if ($LASTEXITCODE -ne 0) { throw 'Schema migration Lambda invocation failed.' }
    $migrationInvoke = $invokeRaw | ConvertFrom-Json
    $migrationBodyRaw = Get-Content -LiteralPath $responseFile -Raw
    $migration = $migrationBodyRaw | ConvertFrom-Json
    if ($migrationInvoke.FunctionError) {
        throw "Schema migration Lambda returned FunctionError=$($migrationInvoke.FunctionError): $migrationBodyRaw"
    }
    if ($migration.status -ne 'migration_complete' -or $migration.migration_set -ne 'nonprod_v0_3') {
        throw "Migration was not confirmed complete: $migrationBodyRaw"
    }
    Write-Host 'Schema migration confirmed: nonprod_v0_3'
}

$health = $null
$unauthWhoAmIStatus = $null
$functionEvidence = @()
if (!$SkipSmoke) {
    $health = Invoke-RestMethod -Method Get -Uri ($outputs.HttpApiEndpoint.TrimEnd('/') + '/health')
    if ($health.status -ne 'ok') { throw "Health smoke failed: $($health | ConvertTo-Json -Compress)" }
    if ($health.database_configured -ne $true) { throw "Health smoke reports database_configured=$($health.database_configured), expected true." }
    Write-Host "Health PASS: database_configured=$($health.database_configured)"

    $unauthWhoAmIStatus = Get-UnauthenticatedStatusCode ($outputs.HttpApiEndpoint.TrimEnd('/') + '/whoami')
    if ($unauthWhoAmIStatus -ne 401) { throw "Auth boundary smoke failed: unauthenticated /whoami returned HTTP $unauthWhoAmIStatus, expected 401." }
    Write-Host 'Auth boundary PASS: unauthenticated /whoami = HTTP 401'

    foreach ($functionName in $RequiredFunctions) {
        $fn = AwsJson @('lambda','get-function','--function-name',$functionName)
        if ([string]$fn.Configuration.State -ne 'Active') { throw "$functionName state=$($fn.Configuration.State), expected Active." }
        if ($fn.Configuration.LastUpdateStatus -and [string]$fn.Configuration.LastUpdateStatus -ne 'Successful') {
            throw "$functionName LastUpdateStatus=$($fn.Configuration.LastUpdateStatus), expected Successful."
        }
        $functionEvidence += [ordered]@{
            function_name = [string]$fn.Configuration.FunctionName
            state = [string]$fn.Configuration.State
            last_update_status = [string]$fn.Configuration.LastUpdateStatus
            runtime = [string]$fn.Configuration.Runtime
            architecture = @($fn.Configuration.Architectures)
            code_sha256 = [string]$fn.Configuration.CodeSha256
            last_modified = [string]$fn.Configuration.LastModified
        }
    }
    Write-Host "Functions active: $($RequiredFunctions -join ', ')"
}

New-Item -ItemType Directory -Path $EvidenceRoot -Force | Out-Null
$timestamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$evidencePath = Join-Path $EvidenceRoot ("wo0014-nonprod-deploy-$timestamp.json")
$evidence = [ordered]@{
    schema = 'tagro.echo.wo0014-nonprod-deploy-evidence/1'
    recorded_at_utc = (Get-Date).ToUniversalTime().ToString('o')
    aws_profile = $AwsProfile
    region = $Region
    expected_account = $ExpectedAccount
    caller_account = [string]$identity.Account
    caller_arn = [string]$identity.Arn
    stack_name = $StackName
    stack_status = [string]$stackRecord.StackStatus
    stack_id = [string]$stackRecord.StackId
    runtime_endpoint = [string]$outputs.HttpApiEndpoint
    web_allowed_origin = $WebAllowedOrigin
    database = [ordered]@{
        identifier = $DbIdentifier
        host = $DbHost
        name = $DbName
        status = [string]$dbInstance.DBInstanceStatus
        publicly_accessible = [bool]$dbInstance.PubliclyAccessible
        secret_arn = $DbSecretArn
    }
    migration_skipped = [bool]$SkipMigration
    migration_invoke = $migrationInvoke
    migration_result = $migration
    smoke_skipped = [bool]$SkipSmoke
    health = $health
    unauthenticated_whoami_http_status = $unauthWhoAmIStatus
    functions = $functionEvidence
    claims_not_proven_by_this_script = @(
        'authenticated staff reference-data readback',
        'authenticated consequential operational write plus PostgreSQL readback',
        'Planar population count/history reconciliation',
        'BUSY booked/live state',
        'authorised web/PWA hosting smoke',
        'production deployment or production admission'
    )
}
Write-Utf8NoBom -Path $evidencePath -Content ($evidence | ConvertTo-Json -Depth 12)

Write-Host 'WO-0014 NONPROD RUNTIME DEPLOYMENT COMPLETE'
Write-Host "Evidence: $evidencePath"
Write-Host 'Next proof: authenticated reference/write/readback, then scripts/SYNC_PLANAR_TO_ECHO.ps1 and /twin-history reconciliation.'
