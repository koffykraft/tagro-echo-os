param(
  [string]$AwsProfile = 'tagro-echo-nonprod',
  [string]$Region = 'ap-south-1',
  [string]$SnapshotId = 'echo-nonprod-pre-catalog-20260823-100906'
)

$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest

$Repo = Split-Path -Parent $PSScriptRoot
$DropboxRoot = 'C:\Users\HP\Dropbox\TAGRO_AUTOMATION'
$ReportRoot = Join-Path $DropboxRoot 'TAGRO_AWS_RUNTIME\reports\wo0014-stihl-scout'
$RunId = Get-Date -Format 'yyyyMMdd-HHmmss'
$ReportDir = Join-Path $ReportRoot $RunId
New-Item -ItemType Directory -Path $ReportDir -Force | Out-Null

function Save-Text([string]$Name,[string]$Value){
  $path=Join-Path $ReportDir $Name
  [System.IO.File]::WriteAllText($path,$Value,(New-Object System.Text.UTF8Encoding($false)))
  return $path
}
function Save-Json([string]$Name,$Value){
  return Save-Text $Name ($Value|ConvertTo-Json -Depth 20)
}
function Require-File([string]$Path){ if(!(Test-Path -LiteralPath $Path -PathType Leaf)){ throw "Missing required file: $Path" } }
function Resolve-Exe([string]$Name,[string[]]$Fallbacks){
  $cmd=Get-Command $Name -ErrorAction SilentlyContinue
  if($cmd){ return $cmd.Source }
  foreach($f in $Fallbacks){ if($f -and (Test-Path -LiteralPath $f -PathType Leaf)){ return $f } }
  throw "Required tool not found: $Name"
}
function Run-External([string]$Exe,[string[]]$ArgumentList,[string]$OutFile){
  $old=$ErrorActionPreference
  try {
    $ErrorActionPreference='Continue'
    $out=& $Exe @ArgumentList 2>&1 | Out-String
    $code=$LASTEXITCODE
  } finally { $ErrorActionPreference=$old }
  Save-Text $OutFile $out | Out-Null
  if($code -ne 0){ throw "$Exe failed with exit code $code. See $OutFile" }
  return $out
}
function File-Proof([string]$Path){
  Require-File $Path
  $f=Get-Item -LiteralPath $Path
  return [ordered]@{path=$f.FullName;size=$f.Length;modified=$f.LastWriteTime.ToString('o');sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLower()}
}

try {
  Set-Location $Repo
  $gitFallback=Get-ChildItem 'C:\Users\HP\AppData\Local\GitHubDesktop\app-*\resources\app\git\cmd\git.exe' -ErrorAction SilentlyContinue|Sort-Object FullName -Descending|Select-Object -First 1 -ExpandProperty FullName
  $Git=Resolve-Exe 'git' @($gitFallback)
  $Aws=Resolve-Exe 'aws' @('C:\Program Files\Amazon\AWSCLIV2\aws.exe')
  $Python='C:\Program Files\Amazon\AWSSAMCLI\runtime\python.exe'
  Require-File $Python

  $Official=Join-Path $DropboxRoot 'safe_base\master_data\latest\stihl_prices_june_2026.json'
  $Aliases=Join-Path $DropboxRoot 'price_update_2026_27\outputs\TAGRO_STIHL_BUSY_Update_One_Row_Per_Item.csv'
  $BusyMaster=Join-Path $DropboxRoot 'outputs\stihl_kvr_part_match\TAGRO_BUSY_ITEM_MASTER_ALL_BRANCHES_2026-07-10.csv'
  $Importer=Join-Path $Repo 'scripts\sync_stihl_catalog_to_echo_v2.py'
  $BaseImporter=Join-Path $Repo 'scripts\sync_stihl_catalog_to_echo.py'
  $Manifest=Join-Path $Repo 'schemas\migrations\nonprod_v0_3_manifest.json'
  $Migration0014=Join-Path $Repo 'schemas\business\catalog_parts_lookup_v0_7.sql'
  $Migration0015=Join-Path $Repo 'schemas\business\product_tax_completeness_v0_8.sql'
  $Migration0016=Join-Path $Repo 'schemas\business\product_unit_conversions_v0_9.sql'
  $Template=Join-Path $Repo 'architecture\aws\nonprod-runtime-template.yaml'

  Run-External $Git @('pull','--ff-only') '01-git-pull.txt'|Out-Null
  $head=(Run-External $Git @('rev-parse','HEAD') '02-git-head.txt').Trim()

  $proof=[ordered]@{
    schema='tagro.echo.wo0014-stihl-scout/1';run_id=$RunId;report_dir=$ReportDir;git_head=$head
    tools=[ordered]@{
      git=[ordered]@{path=$Git;version=(& $Git --version|Out-String).Trim()}
      aws=[ordered]@{path=$Aws;version=(& $Aws --version 2>&1|Out-String).Trim()}
      python=[ordered]@{path=$Python;version=(& $Python --version 2>&1|Out-String).Trim()}
      powershell=[ordered]@{path=(Get-Command powershell).Source;version=$PSVersionTable.PSVersion.ToString()}
    }
    files=[ordered]@{
      official=File-Proof $Official;busy_admission=File-Proof $Aliases;busy_master=File-Proof $BusyMaster
      importer=File-Proof $Importer;base_importer=File-Proof $BaseImporter;manifest=File-Proof $Manifest
      migration_0014=File-Proof $Migration0014;migration_0015=File-Proof $Migration0015;migration_0016=File-Proof $Migration0016;template=File-Proof $Template
    }
  }
  Save-Json '00-preflight.json' $proof|Out-Null
  Write-Host 'PREFLIGHT PASS'

  $dryArgs=@($Importer,'--official-json',$Official,'--tagro-alias-csv',$Aliases,'--busy-item-master',$BusyMaster,'--effective-from','2026-06-01','--enterprise-id','ae9dea8e-6021-5833-9d59-7b0613357fbe','--profile',$AwsProfile,'--region',$Region,'--dry-run')
  $dryRaw=Run-External $Python $dryArgs '03-dry-run.txt'
  $dry=$dryRaw|ConvertFrom-Json
  Save-Json '03-dry-run.json' $dry|Out-Null
  if([bool]$dry.stats.new_non_busy_products_allowed){throw 'Policy failure: new non-BUSY products allowed'}
  if([bool]$dry.stats.busy_writeback){throw 'Policy failure: BUSY writeback enabled'}
  Write-Host "DRY RUN PASS admitted=$($dry.stats.admitted_existing_busy_products)"

  $identityRaw=Run-External $Aws @('sts','get-caller-identity','--profile',$AwsProfile,'--region',$Region,'--output','json') '04-aws-identity.json'
  $identity=$identityRaw|ConvertFrom-Json
  if([string]$identity.Account -ne '272037674623'){throw "Wrong AWS account $($identity.Account)"}

  $snapRaw=Run-External $Aws @('rds','describe-db-snapshots','--db-snapshot-identifier',$SnapshotId,'--profile',$AwsProfile,'--region',$Region,'--output','json') '05-snapshot.json'
  $snap=$snapRaw|ConvertFrom-Json
  if([string]$snap.DBSnapshots[0].Status -ne 'available'){throw "Snapshot not available: $($snap.DBSnapshots[0].Status)"}

  $projectRaw=Run-External $Aws @('codebuild','batch-get-projects','--names','echo-nonprod-runtime-build','--profile',$AwsProfile,'--region',$Region,'--output','json') '06-codebuild-project.json'
  $project=$projectRaw|ConvertFrom-Json
  if(!$project.projects -or !$project.projects[0]){throw 'CodeBuild project missing'}

  $stackRaw=Run-External $Aws @('cloudformation','describe-stacks','--stack-name','echo-nonprod-runtime','--profile',$AwsProfile,'--region',$Region,'--output','json') '07-current-stack.json'
  $stack=$stackRaw|ConvertFrom-Json
  if([string]$stack.Stacks[0].StackStatus -notmatch '_COMPLETE$'){throw "Current stack not stable: $($stack.Stacks[0].StackStatus)"}

  $manifestObj=Get-Content -LiteralPath $Manifest -Raw|ConvertFrom-Json
  $ids=@($manifestObj.migrations.id)
  foreach($needed in @('0014-catalog-parts-lookup-v0.7','0015-product-tax-completeness-v0.8','0016-product-unit-conversions-v0.9')){if($ids -notcontains $needed){throw "Migration missing from manifest: $needed"}}

  $summary=[ordered]@{
    schema='tagro.echo.wo0014-stihl-scout/1';status='scout_complete';run_id=$RunId;report_dir=$ReportDir;git_head=$head
    admitted_existing_busy_products=$dry.stats.admitted_existing_busy_products
    busy_matches_missing_official_stihl_row=$dry.stats.busy_matches_missing_official_stihl_row
    unknown_hsn=$dry.stats.unknown_hsn;unknown_gst=$dry.stats.unknown_gst;prices=$dry.stats.prices
    unit_conversion_candidates=$dry.stats.unit_conversion_candidates
    aws_account=[string]$identity.Account;snapshot_status=[string]$snap.DBSnapshots[0].Status
    current_stack_status=[string]$stack.Stacks[0].StackStatus
    codebuild_project='echo-nonprod-runtime-build';deploy_executed=$false;migration_executed=$false;live_import_executed=$false
  }
  Save-Json '99-scout-summary.json' $summary|Out-Null
  Write-Host "SCOUT COMPLETE REPORT=$ReportDir"
}
catch{
  Save-Json '99-scout-failure.json' ([ordered]@{schema='tagro.echo.wo0014-stihl-scout/1';status='failed';run_id=$RunId;error=$_.Exception.Message;report_dir=$ReportDir})|Out-Null
  Write-Host "SCOUT FAILED REPORT=$ReportDir"
  exit 1
}
