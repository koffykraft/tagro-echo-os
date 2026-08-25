param(
  [string]$Profile = 'tagro-echo-nonprod',
  [string]$Region = 'ap-south-1',
  [string]$ExpectedAccount = '272037674623',
  [string]$RuntimeStack = 'echo-nonprod-runtime',
  [string]$WebStack = 'echo-nonprod-web',
  [string]$OwnerEmail = 'info@tagro.in',
  [string]$Confirm = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RequiredConfirmation = 'ENABLE_ECHO_OWNER_ACCESS'
if ($Confirm -ne $RequiredConfirmation) {
  throw "Explicit confirmation required: -Confirm $RequiredConfirmation"
}

$AwsExe = 'C:\Program Files\Amazon\AWSCLIV2\aws.exe'
if (-not (Test-Path -LiteralPath $AwsExe)) {
  $command = Get-Command aws -ErrorAction SilentlyContinue
  if (-not $command -or -not $command.Source) { throw 'AWS CLI executable not found' }
  $AwsExe = $command.Source
}

function Invoke-Aws {
  param([string[]]$Arguments)
  $priorErrorAction = $ErrorActionPreference
  try {
    $ErrorActionPreference = 'Continue'
    $output = @(& $AwsExe @Arguments --profile $Profile --region $Region 2>&1)
    $code = $LASTEXITCODE
  }
  finally {
    $ErrorActionPreference = $priorErrorAction
  }
  if ($code -ne 0) {
    throw "AWS command failed ($code): $($Arguments -join ' ')`n$($output -join "`n")"
  }
  return (($output | ForEach-Object { "$_" }) -join "`n").Trim()
}

function Get-StackParameter {
  param([object[]]$Parameters,[string]$Name)
  $matches = @($Parameters | Where-Object { $_.ParameterKey -eq $Name })
  if ($matches.Count -ne 1 -or -not $matches[0].ParameterValue) {
    throw "Existing runtime stack does not expose exactly one $Name parameter"
  }
  return [string]$matches[0].ParameterValue
}

function Test-BrowserCognitoIdentity {
  param([string]$RuntimeConfig,[string]$PoolId,[string]$ClientId)
  $poolMatches = [regex]::Matches($RuntimeConfig,"(?m)^\s*userPoolId\s*:\s*'([^']+)'")
  $clientMatches = [regex]::Matches($RuntimeConfig,"(?m)^\s*userPoolClientId\s*:\s*'([^']+)'")
  if ($poolMatches.Count -ne 1 -or $clientMatches.Count -ne 1) {
    throw 'The admitted browser configuration does not expose exactly one Cognito pool and client'
  }
  $browserPoolId = [string]$poolMatches[0].Groups[1].Value
  $browserClientId = [string]$clientMatches[0].Groups[1].Value
  if ($browserPoolId -cne $PoolId -or $browserClientId -cne $ClientId) {
    throw "The admitted browser identity does not match the existing runtime stack (browser pool=$browserPoolId, stack pool=$PoolId, browser client=$browserClientId, stack client=$ClientId)"
  }
}

Write-Host '=== ECHO OWNER ACCESS PREFLIGHT (READ ONLY) ==='
$identity = Invoke-Aws @('sts','get-caller-identity','--output','json') | ConvertFrom-Json
if ([string]$identity.Account -ne $ExpectedAccount) {
  throw "Wrong AWS account: $($identity.Account), expected $ExpectedAccount"
}
Write-Host "AWS account: $($identity.Account)"

$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runtimeClient = Get-Content -LiteralPath (Join-Path $repo 'web\runtime-client.js') -Raw
$runtimeConfig = Get-Content -LiteralPath (Join-Path $repo 'web\runtime-config.js') -Raw
if ($runtimeClient -notmatch "AuthFlow\s*:\s*'USER_PASSWORD_AUTH'") {
  throw 'The admitted browser does not declare the expected USER_PASSWORD_AUTH contract'
}

$parameters = @(Invoke-Aws @('cloudformation','describe-stacks','--stack-name',$RuntimeStack,'--query','Stacks[0].Parameters','--output','json') | ConvertFrom-Json)
$poolId = Get-StackParameter $parameters 'UserPoolId'
$clientId = Get-StackParameter $parameters 'UserPoolClientId'
Test-BrowserCognitoIdentity -RuntimeConfig $runtimeConfig -PoolId $poolId -ClientId $clientId

$client = Invoke-Aws @('cognito-idp','describe-user-pool-client','--user-pool-id',$poolId,'--client-id',$clientId,'--query','UserPoolClient','--output','json') | ConvertFrom-Json
$usersResult = Invoke-Aws @('cognito-idp','list-users','--user-pool-id',$poolId,'--output','json') | ConvertFrom-Json
$owners = @($usersResult.Users | Where-Object {
  @($_.Attributes | Where-Object { $_.Name -eq 'email' -and $_.Value -eq $OwnerEmail }).Count -eq 1
})
if ($owners.Count -ne 1) { throw "Expected exactly one existing Cognito owner for $OwnerEmail" }
if (-not $owners[0].Enabled -or $owners[0].UserStatus -ne 'CONFIRMED') {
  throw "Existing owner $OwnerEmail is not enabled and confirmed"
}
Write-Host "Owner: $OwnerEmail (CONFIRMED)"
Write-Host "Existing Cognito client: $($client.ClientName) ($clientId)"

$originalFlows = @($client.ExplicitAuthFlows)
if ($originalFlows.Count -eq 0) { throw 'Existing Cognito client has no explicit authentication flows' }
if ($originalFlows -notcontains 'ALLOW_REFRESH_TOKEN_AUTH') {
  throw 'Existing Cognito client does not allow refresh-token authentication'
}

if ($originalFlows -contains 'ALLOW_USER_PASSWORD_AUTH') {
  Write-Host 'Browser password authentication is already enabled; no AWS write required.'
}
else {
  $mutableFields = @(
    'ClientName',
    'RefreshTokenValidity',
    'AccessTokenValidity',
    'IdTokenValidity',
    'TokenValidityUnits',
    'ReadAttributes',
    'WriteAttributes',
    'ExplicitAuthFlows',
    'SupportedIdentityProviders',
    'CallbackURLs',
    'LogoutURLs',
    'DefaultRedirectURI',
    'AllowedOAuthFlows',
    'AllowedOAuthScopes',
    'AllowedOAuthFlowsUserPoolClient',
    'AnalyticsConfiguration',
    'PreventUserExistenceErrors',
    'EnableTokenRevocation',
    'EnablePropagateAdditionalUserContextData',
    'AuthSessionValidity',
    'RefreshTokenRotation'
  )
  $request = [ordered]@{ UserPoolId=$poolId; ClientId=$clientId }
  foreach ($field in $mutableFields) {
    $property = $client.PSObject.Properties[$field]
    if ($property -and $null -ne $property.Value) { $request[$field] = $property.Value }
  }
  $request['ExplicitAuthFlows'] = @($originalFlows + 'ALLOW_USER_PASSWORD_AUTH')

  $requestPath = Join-Path ([System.IO.Path]::GetTempPath()) ("echo-cognito-client-" + [guid]::NewGuid().ToString('N') + '.json')
  $encoding = [System.Text.UTF8Encoding]::new($false)
  [System.IO.File]::WriteAllText($requestPath,($request | ConvertTo-Json -Depth 12),$encoding)
  try {
    Write-Host '=== ENABLE BROWSER PASSWORD AUTH (AWS WRITE; PRESERVE EXISTING CLIENT) ==='
    Invoke-Aws @('cognito-idp','update-user-pool-client','--cli-input-json',"file://$requestPath",'--output','json') | Out-Null
  }
  finally {
    if (Test-Path -LiteralPath $requestPath) { Remove-Item -LiteralPath $requestPath -Force }
  }
}

$verifiedClient = Invoke-Aws @('cognito-idp','describe-user-pool-client','--user-pool-id',$poolId,'--client-id',$clientId,'--query','UserPoolClient','--output','json') | ConvertFrom-Json
$verifiedFlows = @($verifiedClient.ExplicitAuthFlows)
foreach ($flow in $originalFlows) {
  if ($verifiedFlows -notcontains $flow) { throw "Existing authentication flow was not preserved: $flow" }
}
if ($verifiedFlows -notcontains 'ALLOW_USER_PASSWORD_AUTH') {
  throw 'Cognito readback did not confirm the browser password authentication flow'
}
foreach ($field in @('ClientName','PreventUserExistenceErrors','EnableTokenRevocation','RefreshTokenValidity','AccessTokenValidity','IdTokenValidity')) {
  $before = $client.PSObject.Properties[$field]
  if ($before -and $null -ne $before.Value) {
    $after = $verifiedClient.PSObject.Properties[$field]
    if (-not $after -or [string]$after.Value -ne [string]$before.Value) {
      throw "Existing Cognito client setting was not preserved: $field"
    }
  }
}

$webUrl = Invoke-Aws @('cloudformation','describe-stacks','--stack-name',$WebStack,'--query',"Stacks[0].Outputs[?OutputKey=='WebUrl'].OutputValue | [0]",'--output','text')
if (-not $webUrl -or $webUrl -eq 'None') { throw 'Existing web stack does not expose its portal URL' }
Write-Host 'LOGIN FLOW OK ALLOW_USER_PASSWORD_AUTH'
Write-Host "Owner sign-in: $webUrl/login.html"
Write-Host 'Existing infrastructure preserved. No runtime rebuild or DNS change required.'
