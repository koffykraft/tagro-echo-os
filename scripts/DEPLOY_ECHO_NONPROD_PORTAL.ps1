param(
  [string]$Profile = 'tagro-echo-nonprod',
  [string]$Region = 'ap-south-1',
  [string]$ExpectedAccount = '272037674623',
  [string]$Branch = 'wo-0014-database-primary-pages-deploy',
  [string]$RuntimeBuildProject = 'echo-nonprod-runtime-build',
  [string]$RuntimeStack = 'echo-nonprod-runtime',
  [string]$DataStack = 'echo-nonprod-data-foundation',
  [string]$WebStack = 'echo-nonprod-web',
  [string]$StableWebOrigin = 'https://os.tagro.in',
  [string]$Confirm = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RequiredConfirmation = 'DEPLOY_ECHO_NONPROD_PORTAL'
if ($Confirm -ne $RequiredConfirmation) {
  throw "Explicit confirmation required: -Confirm $RequiredConfirmation"
}

function Resolve-Executable {
  param([string]$Name, [string[]]$Candidates)
  foreach ($candidate in $Candidates) {
    if ($candidate -and (Test-Path -LiteralPath $candidate)) { return $candidate }
  }
  $cmd = Get-Command $Name -ErrorAction SilentlyContinue
  if ($cmd -and $cmd.Source) { return $cmd.Source }
  throw "$Name executable not found"
}

$Aws = Resolve-Executable 'aws' @('C:\Program Files\Amazon\AWSCLIV2\aws.exe')
$Python = Resolve-Executable 'python' @('C:\Program Files\Amazon\AWSSAMCLI\runtime\python.exe')
$gitCandidates = @()
if ($env:LOCALAPPDATA) {
  $desktop = Join-Path $env:LOCALAPPDATA 'GitHubDesktop'
  if (Test-Path -LiteralPath $desktop) {
    $gitCandidates += Get-ChildItem -LiteralPath $desktop -Directory -Filter 'app-*' -ErrorAction SilentlyContinue |
      Sort-Object Name -Descending |
      ForEach-Object { Join-Path $_.FullName 'resources\app\git\cmd\git.exe' }
  }
}
$Git = Resolve-Executable 'git' $gitCandidates

$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$DeployWork = Join-Path $Repo 'build\portal-deploy'
New-Item -ItemType Directory -Force -Path $DeployWork | Out-Null

function Invoke-Checked {
  param([string]$Exe, [string[]]$Arguments, [switch]$Show)
  $output = & $Exe @Arguments 2>&1
  $code = $LASTEXITCODE
  if ($Show -and $output) { $output | ForEach-Object { Write-Host $_ } }
  if ($code -ne 0) {
    throw "Command failed ($code): $Exe $($Arguments -join ' ')`n$($output -join "`n")"
  }
  return (($output | ForEach-Object { "$_" }) -join "`n").Trim()
}

function Aws {
  param([string[]]$Arguments, [switch]$Show)
  $args = @($Arguments) + @('--profile',$Profile,'--region',$Region)
  return Invoke-Checked $Aws $args -Show:$Show
}

function Get-StackOutput {
  param([string]$StackName,[string]$OutputKey)
  return (Aws @('cloudformation','describe-stacks','--stack-name',$StackName,'--query',"Stacks[0].Outputs[?OutputKey=='$OutputKey'].OutputValue | [0]",'--output','text')).Trim()
}

function Wait-CodeBuild {
  param([string]$BuildId)
  $terminal = @('SUCCEEDED','FAILED','FAULT','STOPPED','TIMED_OUT')
  for ($i=0; $i -lt 240; $i++) {
    $status = (Aws @('codebuild','batch-get-builds','--ids',$BuildId,'--query','builds[0].buildStatus','--output','text')).Trim()
    Write-Host "CodeBuild: $status"
    if ($terminal -contains $status) {
      if ($status -ne 'SUCCEEDED') { throw "Runtime CodeBuild ended $status ($BuildId)" }
      return
    }
    Start-Sleep -Seconds 5
  }
  throw "Runtime CodeBuild did not finish within 20 minutes ($BuildId)"
}

function Test-UrlStatus {
  param([string]$Url,[int[]]$Allowed=@(200))
  try {
    $r = Invoke-WebRequest $Url -UseBasicParsing -MaximumRedirection 5 -TimeoutSec 30
    $status = [int]$r.StatusCode
  } catch {
    $status = $null
    if ($_.Exception.Response -and $_.Exception.Response.StatusCode) { $status = [int]$_.Exception.Response.StatusCode }
    if ($null -eq $status) { throw "HTTP smoke failed for $Url : $($_.Exception.Message)" }
  }
  if ($Allowed -notcontains $status) { throw "HTTP smoke failed for $Url : status $status" }
  Write-Host "HTTP $status $Url"
  return $status
}

function Test-ProtectedPostRoute {
  param([string]$Url)
  try {
    $r = Invoke-WebRequest $Url -Method Post -ContentType 'application/json' -Body '{}' -UseBasicParsing -TimeoutSec 30
    $status = [int]$r.StatusCode
  } catch {
    $status = $null
    if ($_.Exception.Response -and $_.Exception.Response.StatusCode) { $status = [int]$_.Exception.Response.StatusCode }
    if ($null -eq $status) { throw "Protected-route smoke failed for $Url : $($_.Exception.Message)" }
  }
  if (@(401,403) -notcontains $status) {
    throw "Protected-route smoke failed for $Url : expected JWT rejection 401/403, got $status"
  }
  Write-Host "PROTECTED $status $Url"
}

function Test-CorsOrigin {
  param([string]$Api,[string]$Origin)
  $headers = @{ Origin=$Origin; 'Access-Control-Request-Method'='GET'; 'Access-Control-Request-Headers'='authorization,content-type' }
  try {
    $r = Invoke-WebRequest "$Api/health" -Method Options -Headers $headers -UseBasicParsing -TimeoutSec 30
  } catch {
    if ($_.Exception.Response) { $r = $_.Exception.Response } else { throw }
  }
  $allowed = $r.Headers['access-control-allow-origin']
  if (-not $allowed) { $allowed = $r.Headers['Access-Control-Allow-Origin'] }
  if ($allowed -ne $Origin) { throw "CORS readback failed for $Origin (returned '$allowed')" }
  Write-Host "CORS OK $Origin"
}

Push-Location $Repo
try {
  Write-Host "=== ECHO NONPROD PORTAL PREFLIGHT ==="
  $dirty = Invoke-Checked $Git @('status','--porcelain')
  if ($dirty) { throw "Git worktree is not clean. Commit/stash before deployment.`n$dirty" }
  Invoke-Checked $Git @('fetch','origin',$Branch) -Show | Out-Null
  $head = (Invoke-Checked $Git @('rev-parse','HEAD')).Trim()
  $remote = (Invoke-Checked $Git @('rev-parse',"origin/$Branch")).Trim()
  if ($head -ne $remote) { throw "Local HEAD $head does not equal origin/$Branch $remote" }
  Write-Host "Git head: $head"

  $identity = Aws @('sts','get-caller-identity','--output','json') | ConvertFrom-Json
  if ([string]$identity.Account -ne $ExpectedAccount) { throw "Wrong AWS account: $($identity.Account), expected $ExpectedAccount" }
  Write-Host "AWS account: $($identity.Account)"

  Write-Host "=== AWS TEMPLATE VALIDATION (READ ONLY) ==="
  Aws @('cloudformation','validate-template','--template-body','file://architecture/aws/nonprod-web-template.yaml','--output','json') | Out-Null
  Aws @('cloudformation','validate-template','--template-body','file://architecture/aws/nonprod-data-foundation-template.yaml','--output','json') | Out-Null
  Write-Host 'CloudFormation templates validated.'

  Write-Host "=== CREATE/UPDATE DATA FOUNDATION (AWS WRITE) ==="
  Aws @('cloudformation','deploy','--stack-name',$DataStack,'--template-file','architecture/aws/nonprod-data-foundation-template.yaml','--parameter-overrides','EnvironmentName=nonprod','--no-fail-on-empty-changeset') -Show | Out-Null

  Write-Host "=== CREATE/UPDATE WEB HOSTING (AWS WRITE) ==="
  Aws @('cloudformation','deploy','--stack-name',$WebStack,'--template-file','architecture/aws/nonprod-web-template.yaml','--parameter-overrides','EnvironmentName=nonprod','--no-fail-on-empty-changeset') -Show | Out-Null
  $webBucket = Get-StackOutput $WebStack 'WebBucketName'
  $distributionId = Get-StackOutput $WebStack 'WebDistributionId'
  $webUrl = Get-StackOutput $WebStack 'WebUrl'
  if (-not $webBucket -or -not $distributionId -or -not $webUrl) { throw 'Web stack outputs are incomplete' }
  Write-Host "Smoke URL: $webUrl"

  Write-Host "=== PACKAGE EXACT RUNTIME HEAD IN CODEBUILD (AWS WRITE TO ARTIFACT BUCKET) ==="
  $buildId = (Aws @('codebuild','start-build','--project-name',$RuntimeBuildProject,'--source-version',$head,'--query','build.id','--output','text')).Trim()
  if (-not $buildId) { throw 'CodeBuild did not return a build id' }
  Write-Host "Build: $buildId"
  Wait-CodeBuild $buildId

  $artifactBucket = "echo-nonprod-artifacts-$ExpectedAccount"
  $packagedRel = 'build/portal-deploy/packaged-nonprod-runtime.yaml'
  Aws @('s3','cp',"s3://$artifactBucket/echo-nonprod/runtime/packaged-nonprod-runtime.yaml",$packagedRel) -Show | Out-Null

  Write-Host "=== RUNTIME CHANGE SET (AWS WRITE; REVIEW BEFORE EXECUTION) ==="
  $currentParams = (Aws @('cloudformation','describe-stacks','--stack-name',$RuntimeStack,'--query','Stacks[0].Parameters','--output','json') | ConvertFrom-Json)
  $params = @()
  $webOriginSeen = $false
  foreach ($p in $currentParams) {
    if ($p.ParameterKey -eq 'WebAllowedOrigin') {
      $params += [ordered]@{ParameterKey='WebAllowedOrigin';ParameterValue=$webUrl}
      $webOriginSeen = $true
    } else {
      $params += [ordered]@{ParameterKey=$p.ParameterKey;UsePreviousValue=$true}
    }
  }
  if (-not $webOriginSeen) { $params += [ordered]@{ParameterKey='WebAllowedOrigin';ParameterValue=$webUrl} }
  $paramsFile = Join-Path $DeployWork 'runtime-params.json'
  $params | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $paramsFile -Encoding UTF8

  $changeSet = "portal-$($head.Substring(0,7))-$(Get-Date -Format yyyyMMddHHmmss)"
  Aws @('cloudformation','create-change-set','--stack-name',$RuntimeStack,'--change-set-name',$changeSet,'--change-set-type','UPDATE','--template-body','file://build/portal-deploy/packaged-nonprod-runtime.yaml','--parameters','file://build/portal-deploy/runtime-params.json','--description',"ECHO nonprod portal runtime $head",'--output','json') | Out-Null

  & $Aws cloudformation wait change-set-create-complete --stack-name $RuntimeStack --change-set-name $changeSet --profile $Profile --region $Region
  if ($LASTEXITCODE -ne 0) {
    $reason = (Aws @('cloudformation','describe-change-set','--stack-name',$RuntimeStack,'--change-set-name',$changeSet,'--query','StatusReason','--output','text')).Trim()
    if ($reason -match "didn't contain changes|No updates") {
      Write-Host "Runtime change set has no changes."
    } else {
      throw "Runtime change set failed: $reason"
    }
  } else {
    $changesJson = Aws @('cloudformation','describe-change-set','--stack-name',$RuntimeStack,'--change-set-name',$changeSet,'--query','Changes[].ResourceChange.{Action:Action,LogicalResourceId:LogicalResourceId,ResourceType:ResourceType,Replacement:Replacement}','--output','json')
    $changes = @($changesJson | ConvertFrom-Json)
    $changes | Format-Table Action,LogicalResourceId,ResourceType,Replacement -AutoSize
    $unsafe = @($changes | Where-Object { $_.Action -eq 'Remove' -or $_.Replacement -eq 'True' -or $_.Replacement -eq 'Conditional' })
    if ($unsafe.Count -gt 0) { throw 'Runtime change set contains a removal or replacement. Execution refused.' }
    Aws @('cloudformation','execute-change-set','--stack-name',$RuntimeStack,'--change-set-name',$changeSet) | Out-Null
    & $Aws cloudformation wait stack-update-complete --stack-name $RuntimeStack --profile $Profile --region $Region
    if ($LASTEXITCODE -ne 0) { throw 'Runtime stack update did not complete successfully' }
  }

  $apiUrl = Get-StackOutput $RuntimeStack 'HttpApiEndpoint'
  if (-not $apiUrl) { throw 'Runtime API output missing after update' }

  Write-Host "=== BUILD & PUBLISH ADMITTED WEB RELEASE (AWS WRITE) ==="
  & $Python 'scripts/build_web_release.py' '--web-root' 'web' '--manifest' 'web/deploy-manifest.txt' '--output' 'build/web-release'
  if ($LASTEXITCODE -ne 0) { throw 'Admitted web release build failed' }
  Aws @('s3','sync','build/web-release/',"s3://$webBucket/",'--delete','--cache-control','no-cache, no-store, must-revalidate') -Show | Out-Null
  $invalidationId = (Aws @('cloudfront','create-invalidation','--distribution-id',$distributionId,'--paths','/*','--query','Invalidation.Id','--output','text')).Trim()
  & $Aws cloudfront wait invalidation-completed --distribution-id $distributionId --id $invalidationId --profile $Profile
  if ($LASTEXITCODE -ne 0) { throw 'CloudFront invalidation did not complete' }

  Write-Host "=== SMOKE READBACK ==="
  Test-UrlStatus $webUrl @(200) | Out-Null
  Test-UrlStatus "$webUrl/login.html" @(200) | Out-Null
  Test-UrlStatus "$webUrl/billing.html" @(200) | Out-Null
  Test-UrlStatus "$apiUrl/health" @(200) | Out-Null
  Test-CorsOrigin $apiUrl $webUrl
  Test-CorsOrigin $apiUrl $StableWebOrigin
  Test-ProtectedPostRoute "$apiUrl/customers"

  $reportRoot = Join-Path $Repo 'build\deploy-reports'
  $dropboxRoot = Join-Path $env:USERPROFILE 'Dropbox\TAGRO_AUTOMATION\TAGRO_AWS_RUNTIME\reports\wo0014-portal-deploy'
  if (Test-Path -LiteralPath (Split-Path $dropboxRoot -Parent)) { $reportRoot = $dropboxRoot }
  $reportDir = Join-Path $reportRoot (Get-Date -Format 'yyyyMMdd-HHmmss')
  New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
  $report = [ordered]@{
    schema='tagro.echo.nonprod-portal-deploy/1'
    deployed_at=(Get-Date).ToString('o')
    git_head=$head
    aws_account=$ExpectedAccount
    region=$Region
    profile=$Profile
    stacks=[ordered]@{runtime=$RuntimeStack;data_foundation=$DataStack;web=$WebStack}
    web=[ordered]@{url=$webUrl;bucket=$webBucket;distribution_id=$distributionId;invalidation_id=$invalidationId}
    api_url=$apiUrl
    stable_web_origin=$StableWebOrigin
    runtime_build_id=$buildId
    live_dns_changed=$false
    result='PASS'
  }
  $reportPath = Join-Path $reportDir 'deploy-result.json'
  $report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $reportPath -Encoding UTF8

  Write-Host "`n=== ECHO NONPROD PORTAL DEPLOYED ==="
  Write-Host "Web:    $webUrl"
  Write-Host "API:    $apiUrl"
  Write-Host "Report: $reportPath"
  Write-Host 'Live DNS changed: NO'
}
finally {
  Pop-Location
}
