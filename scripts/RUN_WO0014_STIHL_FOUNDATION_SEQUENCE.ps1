param(
  [string]$AwsProfile = 'tagro-echo-nonprod',
  [string]$Region = 'ap-south-1',
  [string]$SnapshotId = 'echo-nonprod-pre-catalog-20260823-100906'
)

$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest

$Repo = Split-Path -Parent $PSScriptRoot
$DropboxRoot = 'C:\Users\HP\Dropbox\TAGRO_AUTOMATION'
$ReportRoot = Join-Path $DropboxRoot 'TAGRO_AWS_RUNTIME\reports\wo0014-stihl-foundation'
$RunId = Get-Date -Format 'yyyyMMdd-HHmmss'
$ReportDir = Join-Path $ReportRoot $RunId
New-Item -ItemType Directory -Path $ReportDir -Force | Out-Null
$Transcript = Join-Path $ReportDir 'sequence.log'
Start-Transcript -Path $Transcript -Force | Out-Null

function Save-Json([string]$Name,$Value){
  $path=Join-Path $ReportDir $Name
  [System.IO.File]::WriteAllText($path,($Value|ConvertTo-Json -Depth 20),(New-Object System.Text.UTF8Encoding($false)))
  return $path
}
function Save-Text([string]$Name,[string]$Value){
  $path=Join-Path $ReportDir $Name
  [System.IO.File]::WriteAllText($path,$Value,(New-Object System.Text.UTF8Encoding($false)))
  return $path
}
function Require-File([string]$Path){ if(!(Test-Path -LiteralPath $Path -PathType Leaf)){ throw "Missing required file: $Path" } }
function Resolve-Exe([string]$Name,[string[]]$Fallbacks){
  $cmd=Get-Command $Name -ErrorAction SilentlyContinue
  if($cmd){ return $cmd.Source }
  foreach($f in $Fallbacks){ if($f -and (Test-Path -LiteralPath $f -PathType Leaf)){ return $f } }
  throw "Required tool not found: $Name"
}
function Run-External([string]$Exe,[string[]]$ArgumentList,[string]$OutFile){
  $out=& $Exe @ArgumentList 2>&1 | Out-String
  $code=$LASTEXITCODE
  Save-Text $OutFile $out | Out-Null
  if($code -ne 0){ throw "$Exe failed with exit code $code. See $OutFile" }
  return $out
}

try {
  Set-Location $Repo

  $gitFallback = Get-ChildItem 'C:\Users\HP\AppData\Local\GitHubDesktop\app-*\resources\app\git\cmd\git.exe' -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
  $Git = Resolve-Exe 'git' @($gitFallback)
  $Python = Resolve-Exe 'python' @('C:\Program Files\Amazon\AWSSAMCLI\runtime\python.exe')
  if(Test-Path 'C:\Program Files\Amazon\AWSSAMCLI\runtime\python.exe'){ $Python='C:\Program Files\Amazon\AWSSAMCLI\runtime\python.exe' }
  $Aws = Resolve-Exe 'aws' @('C:\Program Files\Amazon\AWSCLIV2\aws.exe')

  $Official = Join-Path $DropboxRoot 'safe_base\master_data\latest\stihl_prices_june_2026.json'
  $Aliases = Join-Path $DropboxRoot 'price_update_2026_27\outputs\TAGRO_STIHL_BUSY_Update_One_Row_Per_Item.csv'
  $BusyMaster = Join-Path $DropboxRoot 'outputs\stihl_kvr_part_match\TAGRO_BUSY_ITEM_MASTER_ALL_BRANCHES_2026-07-10.csv'
  $Importer = Join-Path $Repo 'scripts\sync_stihl_catalog_to_echo_v2.py'
  Require-File $Official; Require-File $Aliases; Require-File $BusyMaster; Require-File $Importer

  $preflight=[ordered]@{
    run_id=$RunId; repo=$Repo; report_dir=$ReportDir
    git_path=$Git; git_version=(& $Git --version | Out-String).Trim()
    python_path=$Python; python_version=(& $Python --version 2>&1 | Out-String).Trim()
    aws_path=$Aws; aws_version=(& $Aws --version 2>&1 | Out-String).Trim()
    official_source=$Official; official_size=(Get-Item $Official).Length
    busy_admission_source=$Aliases; busy_admission_size=(Get-Item $Aliases).Length
    busy_master=$BusyMaster; busy_master_size=(Get-Item $BusyMaster).Length
    importer=$Importer
    snapshot_id=$SnapshotId
  }
  Save-Json '00-preflight.json' $preflight | Out-Null
  Write-Host 'PREFLIGHT PASS'

  Run-External $Git @('pull','--ff-only') '01-git-pull.txt' | Out-Null
  $head=(Run-External $Git @('rev-parse','HEAD') '02-git-head.txt').Trim()
  Write-Host "HEAD $head"

  $dryArgs=@(
    $Importer,'--official-json',$Official,'--tagro-alias-csv',$Aliases,'--busy-item-master',$BusyMaster,
    '--effective-from','2026-06-01','--enterprise-id','ae9dea8e-6021-5833-9d59-7b0613357fbe',
    '--profile',$AwsProfile,'--region',$Region,'--dry-run'
  )
  $dryRaw=Run-External $Python $dryArgs '03-dry-run.json'
  $dry=$dryRaw|ConvertFrom-Json
  Save-Json '03-dry-run-normalized.json' $dry | Out-Null
  if([bool]$dry.stats.new_non_busy_products_allowed){ throw 'Dry-run policy violation: new_non_busy_products_allowed=true' }
  if([bool]$dry.stats.busy_writeback){ throw 'Dry-run policy violation: busy_writeback=true' }
  Write-Host "DRY RUN PASS admitted=$($dry.stats.admitted_existing_busy_products)"

  $identityRaw=Run-External $Aws @('sts','get-caller-identity','--profile',$AwsProfile,'--region',$Region,'--output','json') '04-aws-identity.json'
  $identity=$identityRaw|ConvertFrom-Json
  if([string]$identity.Account -ne '272037674623'){ throw "Wrong AWS account $($identity.Account)" }

  $snapRaw=Run-External $Aws @('rds','describe-db-snapshots','--db-snapshot-identifier',$SnapshotId,'--profile',$AwsProfile,'--region',$Region,'--output','json') '05-snapshot.json'
  $snap=$snapRaw|ConvertFrom-Json
  if([string]$snap.DBSnapshots[0].Status -ne 'available'){ throw "Snapshot not available: $($snap.DBSnapshots[0].Status)" }
  Write-Host 'SNAPSHOT PASS'

  $buildRaw=Run-External $Aws @('codebuild','start-build','--project-name','echo-nonprod-runtime-build','--source-version','refs/heads/wo-0014-database-primary-pages-deploy','--profile',$AwsProfile,'--region',$Region,'--output','json') '06-build-start.json'
  $buildId=($buildRaw|ConvertFrom-Json).build.id
  do {
    Start-Sleep -Seconds 10
    $bRaw=& $Aws codebuild batch-get-builds --ids $buildId --profile $AwsProfile --region $Region --output json 2>&1 | Out-String
    if($LASTEXITCODE -ne 0){ throw 'CodeBuild status query failed' }
    $b=$bRaw|ConvertFrom-Json
    $status=[string]$b.builds[0].buildStatus
    Write-Host "CODEBUILD $status $($b.builds[0].currentPhase)"
  } while($status -eq 'IN_PROGRESS')
  Save-Json '07-build-final.json' $b | Out-Null
  if($status -ne 'SUCCEEDED'){ throw "CodeBuild failed: $status" }
  if([string]$b.builds[0].resolvedSourceVersion -ne $head){ throw "CodeBuild commit mismatch: $($b.builds[0].resolvedSourceVersion) vs $head" }

  $projectRaw=Run-External $Aws @('codebuild','batch-get-projects','--names','echo-nonprod-runtime-build','--profile',$AwsProfile,'--region',$Region,'--output','json') '08-codebuild-project.json'
  $project=$projectRaw|ConvertFrom-Json
  $bucket=($project.projects[0].environment.environmentVariables|Where-Object {$_.name -eq 'ARTIFACT_BUCKET'}).value
  if(!$bucket){ throw 'ARTIFACT_BUCKET missing' }
  $pkg=Join-Path $ReportDir 'packaged-nonprod-runtime.yaml'
  Run-External $Aws @('s3','cp',"s3://$bucket/echo-nonprod/runtime/packaged-nonprod-runtime.yaml",$pkg,'--profile',$AwsProfile,'--region',$Region) '09-package-download.txt' | Out-Null
  Require-File $pkg

  $cs="wo0014-stihl-$RunId"
  Run-External $Aws @(
    'cloudformation','create-change-set','--stack-name','echo-nonprod-runtime','--change-set-name',$cs,'--change-set-type','UPDATE',
    '--template-body',"file://$pkg",'--capabilities','CAPABILITY_IAM',
    '--parameters',
    'ParameterKey=UserPoolId,UsePreviousValue=true','ParameterKey=UserPoolClientId,UsePreviousValue=true',
    'ParameterKey=WebAllowedOrigin,UsePreviousValue=true','ParameterKey=LambdaExecutionRoleArn,UsePreviousValue=true',
    'ParameterKey=DbSecretArn,UsePreviousValue=true','ParameterKey=DbHost,UsePreviousValue=true','ParameterKey=DbName,UsePreviousValue=true',
    'ParameterKey=PrivateSubnetA,UsePreviousValue=true','ParameterKey=PrivateSubnetB,UsePreviousValue=true','ParameterKey=AppSecurityGroup,UsePreviousValue=true',
    '--profile',$AwsProfile,'--region',$Region,'--output','json'
  ) '10-change-set-create.json' | Out-Null
  Run-External $Aws @('cloudformation','wait','change-set-create-complete','--stack-name','echo-nonprod-runtime','--change-set-name',$cs,'--profile',$AwsProfile,'--region',$Region) '11-change-set-wait.txt' | Out-Null
  $csRaw=Run-External $Aws @('cloudformation','describe-change-set','--stack-name','echo-nonprod-runtime','--change-set-name',$cs,'--profile',$AwsProfile,'--region',$Region,'--output','json') '12-change-set.json'
  $csObj=$csRaw|ConvertFrom-Json
  foreach($change in @($csObj.Changes)){
    $r=$change.ResourceChange
    if([string]$r.Replacement -eq 'True'){ throw "REFUSED replacement: $($r.LogicalResourceId) $($r.ResourceType)" }
    if([string]$r.ResourceType -match 'RDS'){ throw "REFUSED RDS change: $($r.LogicalResourceId)" }
  }
  Write-Host 'CHANGE SET PASS'

  Run-External $Aws @('cloudformation','execute-change-set','--stack-name','echo-nonprod-runtime','--change-set-name',$cs,'--profile',$AwsProfile,'--region',$Region) '13-change-set-execute.txt' | Out-Null
  Run-External $Aws @('cloudformation','wait','stack-update-complete','--stack-name','echo-nonprod-runtime','--profile',$AwsProfile,'--region',$Region) '14-stack-wait.txt' | Out-Null
  $stackRaw=Run-External $Aws @('cloudformation','describe-stacks','--stack-name','echo-nonprod-runtime','--profile',$AwsProfile,'--region',$Region,'--output','json') '15-stack.json'
  $stack=$stackRaw|ConvertFrom-Json
  if([string]$stack.Stacks[0].StackStatus -ne 'UPDATE_COMPLETE'){ throw "Stack status $($stack.Stacks[0].StackStatus)" }

  $migPayload=Join-Path $ReportDir 'migration-payload.json'
  [System.IO.File]::WriteAllText($migPayload,'{"confirm":"APPLY_NONPROD_V0_3"}',(New-Object System.Text.UTF8Encoding($false)))
  $migBody=Join-Path $ReportDir '16-migration-body.json'
  Run-External $Aws @('lambda','invoke','--function-name','echo-nonprod-schema-migrate','--payload',"fileb://$migPayload",'--cli-binary-format','raw-in-base64-out',$migBody,'--profile',$AwsProfile,'--region',$Region,'--output','json') '16-migration-invoke.json' | Out-Null
  $mig=Get-Content $migBody -Raw|ConvertFrom-Json
  if([string]$mig.status -ne 'migration_complete'){ throw "Migration failed: $(Get-Content $migBody -Raw)" }

  $liveArgs=@(
    $Importer,'--official-json',$Official,'--tagro-alias-csv',$Aliases,'--busy-item-master',$BusyMaster,
    '--effective-from','2026-06-01','--enterprise-id','ae9dea8e-6021-5833-9d59-7b0613357fbe',
    '--profile',$AwsProfile,'--region',$Region
  )
  $liveRaw=Run-External $Python $liveArgs '17-live-import.json'
  $live=$liveRaw|ConvertFrom-Json
  Save-Json '17-live-import-normalized.json' $live | Out-Null
  $replayRaw=Run-External $Python $liveArgs '18-idempotent-replay.json'
  $replay=$replayRaw|ConvertFrom-Json
  Save-Json '18-idempotent-replay-normalized.json' $replay | Out-Null

  $summary=[ordered]@{
    schema='tagro.echo.wo0014-stihl-foundation-sequence/1'; status='complete'; run_id=$RunId; report_dir=$ReportDir;
    git_head=$head; snapshot=$SnapshotId; admitted_existing_busy_products=$dry.stats.admitted_existing_busy_products;
    busy_matches_missing_official_stihl_row=$dry.stats.busy_matches_missing_official_stihl_row;
    unknown_hsn=$dry.stats.unknown_hsn; unknown_gst=$dry.stats.unknown_gst; prices=$dry.stats.prices;
    live_inserted=$live.inserted; live_updated=$live.updated; live_unchanged=$live.unchanged;
    replay_inserted=$replay.inserted; replay_updated=$replay.updated; replay_unchanged=$replay.unchanged;
    busy_writeback=$false; non_busy_products_admitted=$false
  }
  Save-Json '99-summary.json' $summary | Out-Null
  Write-Host "SEQUENCE COMPLETE REPORT=$ReportDir"
}
catch {
  $failure=[ordered]@{schema='tagro.echo.wo0014-stihl-foundation-sequence/1';status='failed';run_id=$RunId;error=$_.Exception.Message;report_dir=$ReportDir}
  Save-Json '99-failure.json' $failure | Out-Null
  Write-Host "SEQUENCE FAILED REPORT=$ReportDir"
  Write-Error $_
  exit 1
}
finally {
  try { Stop-Transcript | Out-Null } catch {}
}
