param(
    [string]$AwsProfile = 'tagro-echo-nonprod',
    [string]$Region = 'ap-south-1',
    [string]$WebAllowedOrigin,
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

function AwsJson([string[]]$Arguments) {
    $raw = & aws @Arguments --profile $AwsProfile --region $Region --output json
    if ($LASTEXITCODE -ne 0) { throw "AWS command failed: aws $($Arguments -join ' ')" }
    return ($raw | ConvertFrom-Json)
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
$DbSecretArn = [string]$dbInstance.MasterUserSecret.SecretArn
if ([string]::IsNullOrWhiteSpace($DbSecretArn)) { throw 'RDS master SecretArn could not be resolved.' }
Write-Host "RDS confirmed private: $DbIdentifier / $DbHost"

if (!$SkipBuild) {
    Write-Host 'Building SAM application...'
    & sam build --template-file $Template
    if ($LASTEXITCODE -ne 0) { throw "sam build failed with exit code $LASTEXITCODE" }
}
if (!(Test-Path -LiteralPath $BuiltTemplate -PathType Leaf)) { throw "Built SAM template missing: $BuiltTemplate" }

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
$outputs = @{}
foreach ($o in ($stack.Stacks[0].Outputs | ForEach-Object { $_ })) { $outputs[$o.OutputKey] = $o.OutputValue }
if (!$outputs.HttpApiEndpoint) { throw 'Deployment completed but HttpApiEndpoint output is missing.' }
Write-Host "Runtime endpoint: $($outputs.HttpApiEndpoint)"

if (!$SkipMigration) {
    $payloadFile = Join-Path $env:TEMP 'echo-wo0014-migration-payload.json'
    $responseFile = Join-Path $env:TEMP 'echo-wo0014-migration-response.json'
    '{"confirm":"APPLY_NONPROD_V0_3"}' | Set-Content -LiteralPath $payloadFile -Encoding utf8NoBOM
    & aws lambda invoke --function-name $MigrationFunction --payload ("fileb://" + $payloadFile) $responseFile --profile $AwsProfile --region $Region --cli-binary-format raw-in-base64-out | Out-Host
    if ($LASTEXITCODE -ne 0) { throw 'Schema migration Lambda invocation failed.' }
    $migration = Get-Content -LiteralPath $responseFile -Raw | ConvertFrom-Json
    if ($migration.status -ne 'migration_complete' -or $migration.migration_set -ne 'nonprod_v0_3') {
        throw "Migration was not confirmed complete: $(Get-Content -LiteralPath $responseFile -Raw)"
    }
    Write-Host 'Schema migration confirmed: nonprod_v0_3'
}

if (!$SkipSmoke) {
    $health = Invoke-RestMethod -Method Get -Uri ($outputs.HttpApiEndpoint.TrimEnd('/') + '/health')
    if ($health.status -ne 'ok') { throw "Health smoke failed: $($health | ConvertTo-Json -Compress)" }
    Write-Host "Health PASS: database_configured=$($health.database_configured)"

    $runtime = AwsJson @('lambda','get-function','--function-name','echo-nonprod-runtime')
    $twin = AwsJson @('lambda','get-function','--function-name','echo-nonprod-twin-read')
    $import = AwsJson @('lambda','get-function','--function-name','echo-nonprod-observation-import')
    Write-Host "Functions present: $($runtime.Configuration.FunctionName), $($twin.Configuration.FunctionName), $($import.Configuration.FunctionName)"
}

Write-Host 'WO-0014 NONPROD RUNTIME DEPLOYMENT COMPLETE'
Write-Host 'Next proof: authenticated reference/write/readback, then scripts/SYNC_PLANAR_TO_ECHO.ps1 and /twin-history reconciliation.'
