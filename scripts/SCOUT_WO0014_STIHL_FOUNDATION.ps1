param(
  [string]$AwsProfile = 'tagro-echo-nonprod',
  [string]$Region = 'ap-south-1',
  [string]$SnapshotId = 'echo-nonprod-pre-catalog-20260823-100906'
)

$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest

$ExpectedBranch = 'wo-0014-database-primary-pages-deploy'
$Repo = Split-Path -Parent $PSScriptRoot
$DropboxRoot = 'C:\Users\HP\Dropbox\TAGRO_AUTOMATION'
$ReportRoot = Join-Path $DropboxRoot 'TAGRO_AWS_RUNTIME\reports\wo0014-stihl-scout'
$RunId = Get-Date -Format 'yyyyMMdd-HHmmss'
$ReportDir = Join-Path $ReportRoot $RunId
$IdentityDir = Join-Path $ReportDir 'identity-reconciliation'
New-Item -ItemType Directory -Path $IdentityDir -Force | Out-Null

function Save-Text([string]$Name,[string]$Value){
  $path=Join-Path $ReportDir $Name
  [System.IO.File]::WriteAllText($path,$Value,(New-Object System.Text.UTF8Encoding($false)))
  return $path
}
function Save-Json([string]$Name,$Value){
  return Save-Text $Name ($Value|ConvertTo-Json -Depth 40)
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
  return [ordered]@{
    path=$f.FullName
    size=$f.Length
    modified=$f.LastWriteTime.ToString('o')
    sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLower()
  }
}
function Parse-IsoDate([string]$Value){
  if([string]::IsNullOrWhiteSpace($Value)){ return $null }
  $parsed=[datetime]::MinValue
  if([datetime]::TryParse($Value,[ref]$parsed)){ return $parsed.Date }
  return $null
}
function Normalized-Path([string]$Path){
  return [System.IO.Path]::GetFullPath($Path).TrimEnd('\','/').ToLowerInvariant()
}

try {
  Set-Location $Repo
  $gitFallback=Get-ChildItem 'C:\Users\HP\AppData\Local\GitHubDesktop\app-*\resources\app\git\cmd\git.exe' -ErrorAction SilentlyContinue|Sort-Object FullName -Descending|Select-Object -First 1 -ExpandProperty FullName
  $Git=Resolve-Exe 'git' @($gitFallback)
  $Aws=Resolve-Exe 'aws' @('C:\Program Files\Amazon\AWSCLIV2\aws.exe')
  $Python='C:\Program Files\Amazon\AWSSAMCLI\runtime\python.exe'
  Require-File $Python

  # Identity sources. Prices/catalogues are deliberately not identity prerequisites.
  $TdMatch=Join-Path $DropboxRoot 'td\data\busy_stihl_price_match.csv'
  $TdMatcher=Join-Path $DropboxRoot 'td\engine\build_price_match.py'
  $BusyMaster=Join-Path $DropboxRoot 'outputs\stihl_kvr_part_match\TAGRO_BUSY_ITEM_MASTER_ALL_BRANCHES_2026-07-10.csv'
  $ExistingAdmission=Join-Path $DropboxRoot 'price_update_2026_27\outputs\TAGRO_STIHL_BUSY_Update_One_Row_Per_Item.csv'
  $WarehouseOverview=Join-Path $DropboxRoot 'projects\tagro-data-import\warehouse_builder\reports\warehouse_overview_for_architect.json'
  $WarehouseReadme=Join-Path $DropboxRoot 'projects\tagro-data-import\warehouse_builder\README.txt'
  $ReconcilerBase=Join-Path $Repo 'scripts\reconcile_stihl_busy_identity_v2.py'
  $Reconciler=Join-Path $Repo 'scripts\reconcile_stihl_busy_identity_v3.py'
  $ReconcilerTest=Join-Path $Repo 'tests\test_stihl_identity_reconciliation_v3.py'

  # Freshness evidence. These are reported, not silently treated as equivalent snapshots.
  $DataPlatformShipManifest=Join-Path $DropboxRoot 'data\products\tagro-data-platform\ship-packs\FY2023_to_current_active_v1\manifest.json'
  $DataPlatformRefreshState=Join-Path $DropboxRoot 'data\canonical\tagro-data-platform\state\current_fy_refresh_state.json'
  $RawWarehouseManifest=Join-Path $DropboxRoot 'TAGRO_AWS_OS_WAREHOUSE\manifests\latest.json'

  $Manifest=Join-Path $Repo 'schemas\migrations\nonprod_v0_3_manifest.json'
  $Migration0014=Join-Path $Repo 'schemas\business\catalog_parts_lookup_v0_7.sql'
  $Migration0015=Join-Path $Repo 'schemas\business\product_tax_completeness_v0_8.sql'
  $Migration0016=Join-Path $Repo 'schemas\business\product_unit_conversions_v0_9.sql'
  $Template=Join-Path $Repo 'architecture\aws\nonprod-runtime-template.yaml'

  # Immutable checkout gate: this scout never changes code while it is running.
  $repoTop=(Run-External $Git @('rev-parse','--show-toplevel') '01-git-root.txt').Trim()
  if((Normalized-Path $repoTop) -ne (Normalized-Path $Repo)){ throw "Wrong repository root. Expected $Repo but git reports $repoTop" }
  $branch=(Run-External $Git @('rev-parse','--abbrev-ref','HEAD') '02-git-branch.txt').Trim()
  if($branch -ne $ExpectedBranch){ throw "Wrong git branch. Expected $ExpectedBranch but found $branch" }
  $dirty=Run-External $Git @('status','--porcelain') '03-git-status.txt'
  if(-not [string]::IsNullOrWhiteSpace($dirty)){ throw 'Git worktree is not clean; scout refuses to mix local edits with evidence generation' }
  $head=(Run-External $Git @('rev-parse','HEAD') '04-git-head.txt').Trim()

  foreach($required in @(
    $TdMatch,$TdMatcher,$BusyMaster,$ExistingAdmission,$WarehouseOverview,$WarehouseReadme,
    $ReconcilerBase,$Reconciler,$ReconcilerTest,$DataPlatformShipManifest,$DataPlatformRefreshState,
    $RawWarehouseManifest,$Manifest,$Migration0014,$Migration0015,$Migration0016,$Template
  )){ Require-File $required }

  # Verify the exact Python dependency chain before running real data.
  Run-External $Python @('-m','py_compile',$ReconcilerBase,$Reconciler,$ReconcilerTest) '05-python-compile.txt'|Out-Null
  Run-External $Python @('-m','unittest','discover','-s','tests','-p','test_stihl_identity_reconciliation_v3.py') '06-v3-regression-test.txt'|Out-Null

  $sourceProof=[ordered]@{
    td_match=File-Proof $TdMatch
    td_match_builder=File-Proof $TdMatcher
    busy_master=File-Proof $BusyMaster
    existing_admission=File-Proof $ExistingAdmission
    data_import_warehouse_overview=File-Proof $WarehouseOverview
    data_import_warehouse_readme=File-Proof $WarehouseReadme
    data_platform_ship_manifest=File-Proof $DataPlatformShipManifest
    data_platform_refresh_state=File-Proof $DataPlatformRefreshState
    raw_busy_warehouse_manifest=File-Proof $RawWarehouseManifest
    reconciler_base_v2=File-Proof $ReconcilerBase
    reconciler_v3=File-Proof $Reconciler
    reconciler_v3_test=File-Proof $ReconcilerTest
  }

  $proof=[ordered]@{
    schema='tagro.echo.wo0014-stihl-scout/4'
    run_id=$RunId
    report_dir=$ReportDir
    repo_root=$Repo
    expected_branch=$ExpectedBranch
    actual_branch=$branch
    git_head=$head
    checkout_mutated_by_scout=$false
    policy=[ordered]@{
      foundation='prove STIHL part identity; expand exact BUSY aliases across all branches; normalize labels without erasing source evidence; commercially enrich later'
      exact_identity_only=$true
      name_matches_auto_admitted=$false
      corrected_part_numbers_auto_admitted=$false
      unit_conversion_inferred=$false
      prices_required_for_identity=$false
      busy_writeback=$false
      deploy_enabled=$false
    }
    tools=[ordered]@{
      git=[ordered]@{path=$Git;version=(& $Git --version|Out-String).Trim()}
      aws=[ordered]@{path=$Aws;version=(& $Aws --version 2>&1|Out-String).Trim()}
      python=[ordered]@{path=$Python;version=(& $Python --version 2>&1|Out-String).Trim()}
      powershell=[ordered]@{path=(Get-Command powershell).Source;version=$PSVersionTable.PSVersion.ToString()}
    }
    identity_sources=$sourceProof
    runtime_files=[ordered]@{
      manifest=File-Proof $Manifest
      migration_0014=File-Proof $Migration0014
      migration_0015=File-Proof $Migration0015
      migration_0016=File-Proof $Migration0016
      template=File-Proof $Template
    }
  }
  Save-Json '00-preflight.json' $proof|Out-Null
  Write-Host 'PREFLIGHT PASS'

  $shipManifest=Get-Content -LiteralPath $DataPlatformShipManifest -Raw|ConvertFrom-Json
  $refreshState=Get-Content -LiteralPath $DataPlatformRefreshState -Raw|ConvertFrom-Json
  $rawWarehouse=Get-Content -LiteralPath $RawWarehouseManifest -Raw|ConvertFrom-Json

  $fullMasterDate='2026-07-10'
  $shipDataAsOf=[string]$shipManifest.dataAsOf
  $rawBusyThrough=[string]$rawWarehouse.stats.busy.base_through
  $refreshStatus=[string]$refreshState.status
  $refreshThrough=[string]$refreshState.through_date
  $fullMasterDt=Parse-IsoDate $fullMasterDate
  $rawBusyDt=Parse-IsoDate $rawBusyThrough
  $shipDt=Parse-IsoDate $shipDataAsOf
  $freshnessWarning=(
    ($null -ne $rawBusyDt -and $null -ne $fullMasterDt -and $rawBusyDt -gt $fullMasterDt) -or
    ($null -ne $rawBusyDt -and $null -ne $shipDt -and $rawBusyDt -gt $shipDt) -or
    ($refreshStatus -notmatch '^(complete|completed|ok|success)$')
  )

  $freshness=[ordered]@{
    full_busy_item_master_snapshot=$fullMasterDate
    data_platform_ship_data_as_of=$shipDataAsOf
    raw_busy_movement_warehouse_through=$rawBusyThrough
    data_platform_refresh_status=$refreshStatus
    data_platform_refresh_requested_through=$refreshThrough
    warning=[bool]$freshnessWarning
    meaning='Exact identity can be reconciled from admitted evidence, but the July full item master must not be represented as an August-current complete item master.'
    consequence='Scout may proceed. Any exact accepted alias is evidence-backed; absence from the July master is not proof that an item/alias does not exist in a newer branch backup.'
  }
  Save-Json '00-source-freshness.json' $freshness|Out-Null
  if($freshnessWarning){ Write-Host "FRESHNESS WARNING full_master=$fullMasterDate raw_busy_through=$rawBusyThrough refresh=$refreshStatus" }

  $reconArgs=@(
    $Reconciler,
    '--td-match-csv',$TdMatch,
    '--busy-master-csv',$BusyMaster,
    '--existing-admission-csv',$ExistingAdmission,
    '--out-dir',$IdentityDir
  )
  Run-External $Python $reconArgs '07-identity-reconciliation-v3.txt'|Out-Null
  $reconSummaryPath=Join-Path $IdentityDir '00-summary.json'
  Require-File $reconSummaryPath
  $recon=Get-Content -LiteralPath $reconSummaryPath -Raw|ConvertFrom-Json
  if([string]$recon.schema -ne 'tagro.echo.stihl-identity-reconciliation/3'){throw "Unexpected reconciler schema: $($recon.schema)"}
  if([bool]$recon.policy.prices_required_for_identity){throw 'Policy failure: prices became an identity prerequisite'}
  if([bool]$recon.policy.busy_writeback){throw 'Policy failure: BUSY writeback enabled'}
  if([bool]$recon.policy.aws_write){throw 'Policy failure: reconciliation attempted AWS write'}
  if([string]$recon.policy.name_logic -ne 'candidate generation only; no fuzzy/name match is auto-admitted'){throw 'Policy failure: unexpected name-admission policy'}
  if(-not [bool]$recon.validation.source_branch_preserved){throw 'Policy failure: raw source branch is not preserved'}
  if(-not [bool]$recon.validation.operational_branch_segments_collapsed){throw 'Policy failure: source branch segments were not operationally canonicalized'}
  if([bool]$recon.validation.unit_conversion_inferred){throw 'Policy failure: unit conversion was inferred'}
  if([bool]$recon.validation.corrected_part_numbers_auto_admitted){throw 'Policy failure: corrected part numbers were auto-admitted'}
  if([bool]$recon.validation.name_candidates_auto_admitted){throw 'Policy failure: name candidates were auto-admitted'}
  Write-Host "IDENTITY RECON PASS accepted_rows=$($recon.counts.exact_part_accepted_rows) parts=$($recon.counts.exact_part_accepted_unique_parts) branches=$($recon.counts.exact_part_accepted_branches) cross_branch=$($recon.counts.exact_part_cross_branch_expansion_rows)"

  $identityRaw=Run-External $Aws @('sts','get-caller-identity','--profile',$AwsProfile,'--region',$Region,'--output','json') '08-aws-identity.json'
  $identity=$identityRaw|ConvertFrom-Json
  if([string]$identity.Account -ne '272037674623'){throw "Wrong AWS account $($identity.Account)"}

  $snapRaw=Run-External $Aws @('rds','describe-db-snapshots','--db-snapshot-identifier',$SnapshotId,'--profile',$AwsProfile,'--region',$Region,'--output','json') '09-snapshot.json'
  $snap=$snapRaw|ConvertFrom-Json
  if([string]$snap.DBSnapshots[0].Status -ne 'available'){throw "Snapshot not available: $($snap.DBSnapshots[0].Status)"}

  $projectRaw=Run-External $Aws @('codebuild','batch-get-projects','--names','echo-nonprod-runtime-build','--profile',$AwsProfile,'--region',$Region,'--output','json') '10-codebuild-project.json'
  $project=$projectRaw|ConvertFrom-Json
  if(!$project.projects -or !$project.projects[0]){throw 'CodeBuild project missing'}

  $stackRaw=Run-External $Aws @('cloudformation','describe-stacks','--stack-name','echo-nonprod-runtime','--profile',$AwsProfile,'--region',$Region,'--output','json') '11-current-stack.json'
  $stack=$stackRaw|ConvertFrom-Json
  if([string]$stack.Stacks[0].StackStatus -notmatch '_COMPLETE$'){throw "Current stack not stable: $($stack.Stacks[0].StackStatus)"}

  $manifestObj=Get-Content -LiteralPath $Manifest -Raw|ConvertFrom-Json
  $ids=@($manifestObj.migrations.id)
  foreach($needed in @('0014-catalog-parts-lookup-v0.7','0015-product-tax-completeness-v0.8','0016-product-unit-conversions-v0.9')){
    if($ids -notcontains $needed){throw "Migration missing from manifest: $needed"}
  }

  $summary=[ordered]@{
    schema='tagro.echo.wo0014-stihl-scout/4'
    status='scout_complete'
    run_id=$RunId
    report_dir=$ReportDir
    repo_root=$Repo
    branch=$branch
    git_head=$head
    checkout_mutated_by_scout=$false
    freshness=$freshness
    identity=[ordered]@{
      td_rows=$recon.counts.td_rows
      busy_master_rows=$recon.counts.busy_master_rows
      existing_admission_rows=$recon.counts.existing_admission_rows
      exact_seed_evidence_rows=$recon.counts.exact_seed_evidence_rows
      exact_seed_unique_parts=$recon.counts.exact_seed_unique_parts
      exact_part_accepted_rows=$recon.counts.exact_part_accepted_rows
      exact_part_accepted_unique_parts=$recon.counts.exact_part_accepted_unique_parts
      exact_part_accepted_branches=$recon.counts.exact_part_accepted_branches
      exact_part_cross_branch_expansion_rows=$recon.counts.exact_part_cross_branch_expansion_rows
      canonical_parts_with_branch_name_variants=$recon.counts.canonical_parts_with_branch_name_variants
      canonical_parts_with_unit_variants=$recon.counts.canonical_parts_with_unit_variants
      canonical_parts_with_unit_conflicts=$recon.counts.canonical_parts_with_unit_conflicts
      official_part_corrections_review=$recon.counts.official_part_corrections_review
      tagro_master_part_candidates_review=$recon.counts.tagro_master_part_candidates_review
      name_candidates_need_part_evidence=$recon.counts.name_candidates_need_part_evidence
      name_candidates_part_revalidated=$recon.counts.name_candidates_part_revalidated
      name_candidate_part_conflicts=$recon.counts.name_candidate_part_conflicts
      unmatched_stihl_clue_rows=$recon.counts.unmatched_stihl_clue_rows
      by_branch=$recon.by_branch
      validation=$recon.validation
    }
    aws_account=[string]$identity.Account
    snapshot_status=[string]$snap.DBSnapshots[0].Status
    current_stack_status=[string]$stack.Stacks[0].StackStatus
    codebuild_project='echo-nonprod-runtime-build'
    prices_used_as_identity_gate=$false
    deploy_executed=$false
    migration_executed=$false
    live_import_executed=$false
  }
  Save-Json '99-scout-summary.json' $summary|Out-Null
  Write-Host "SCOUT COMPLETE REPORT=$ReportDir"
}
catch{
  Save-Json '99-scout-failure.json' ([ordered]@{
    schema='tagro.echo.wo0014-stihl-scout/4'
    status='failed'
    run_id=$RunId
    error=$_.Exception.Message
    report_dir=$ReportDir
  })|Out-Null
  Write-Host "SCOUT FAILED REPORT=$ReportDir"
  exit 1
}
