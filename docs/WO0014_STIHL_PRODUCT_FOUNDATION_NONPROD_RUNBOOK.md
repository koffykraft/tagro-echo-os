# WO-0014 — STIHL BUSY-Existing Product Foundation NonProd Runbook

Purpose: admit only STIHL items that already exist in TAGRO/BUSY, preserve every BUSY item name/code/unit unchanged at source, enrich safe matches with STIHL part/name/HSN/GST and the Owner-authorised June 2026 STIHL price base, and verify normal authenticated lookup/Billing. No new STIHL catalogue item is introduced by this path. Planar is not involved.

## Invariants

- Admission boundary: `TAGRO_AUTOMATION/price_update_2026_27/outputs/TAGRO_STIHL_BUSY_Update_One_Row_Per_Item.csv`.
- Full STIHL reference/pricing source: `TAGRO_AUTOMATION/safe_base/master_data/latest/stihl_prices_june_2026.json`.
- Existing BUSY item/unit evidence: `TAGRO_AUTOMATION/outputs/stihl_kvr_part_match/TAGRO_BUSY_ITEM_MASTER_ALL_BRANCHES_2026-07-10.csv`.
- An official STIHL item absent from the BUSY-existing admission file is NOT admitted.
- Existing BUSY names/codes/aliases are preserved as aliases and are never written back, renamed or replaced.
- Safe part-number match is required for STIHL enrichment. Missing/unsafe match is skipped or refused; never guessed.
- BUSY unit is the operational unit. Equivalent labels such as `Nos`/`Pcs` may normalize to one arithmetic unit inside ECHO, while the original BUSY identity remains preserved.
- Non-equivalent unit conflicts stop admission.
- Pack/reel conversions require an explicit multiplier. ECHO never infers a conversion from words such as `reel`, `roll` or `links`.
- Chain items already stored by BUSY in `Links` remain `Links`; no reel conversion is invented.
- Missing HSN/GST is allowed and remains unknown.
- Unknown GST does not hide a product from lookup; Billing rejects only that sale line until GST is populated.
- Aliases may never silently move from one product to another.
- Owner has authorised the STIHL June 2026 list as the current price base where a safe official match exists. ECHO records this as `stihl_june_*` price types with base date `2026-06-01` and provenance identifying the June 2026 source.
- The raw BUSY foundation already loaded into AWS is not rewritten by this path.

## 0. PowerShell setup

```powershell
cd "C:\Users\HP\Dropbox\TAGRO_AUTOMATION\projects\tagro-echo-os-git"
$env:Path += ";C:\Users\HP\AppData\Local\GitHubDesktop\app-3.6.3\resources\app\git\cmd"
$PY="C:\Program Files\Amazon\AWSSAMCLI\runtime\python.exe"
$PROFILE="tagro-echo-nonprod"
$REGION="ap-south-1"
$ENTERPRISE="ae9dea8e-6021-5833-9d59-7b0613357fbe"
$BRANCH="wo-0014-database-primary-pages-deploy"
$OFFICIAL="C:\Users\HP\Dropbox\TAGRO_AUTOMATION\safe_base\master_data\latest\stihl_prices_june_2026.json"
$ALIASES="C:\Users\HP\Dropbox\TAGRO_AUTOMATION\price_update_2026_27\outputs\TAGRO_STIHL_BUSY_Update_One_Row_Per_Item.csv"
$BUSYMASTER="C:\Users\HP\Dropbox\TAGRO_AUTOMATION\outputs\stihl_kvr_part_match\TAGRO_BUSY_ITEM_MASTER_ALL_BRANCHES_2026-07-10.csv"
```

## 1. Pull and prove sources

```powershell
git pull
git --no-pager log -1 --oneline

@($OFFICIAL,$ALIASES,$BUSYMASTER) | ForEach-Object {
  if(!(Test-Path -LiteralPath $_ -PathType Leaf)){ throw "Missing source: $_" }
  Get-Item -LiteralPath $_ | Select-Object FullName,Length,LastWriteTime
}
```

STOP if any source is missing.

## 2. Full test gate

```powershell
& $PY -m unittest discover -s tests -p "test_*.py" -v
```

STOP unless all tests pass. GitHub Runtime Gate and Governance Gate must also be green for the same head.

## 3. BUSY-existing-only dry run

This does not call AWS.

```powershell
& $PY ".\scripts\sync_stihl_catalog_to_echo.py" `
  --official-json "$OFFICIAL" `
  --tagro-alias-csv "$ALIASES" `
  --busy-item-master "$BUSYMASTER" `
  --effective-from "2026-06-01" `
  --enterprise-id "$ENTERPRISE" `
  --profile "$PROFILE" `
  --region "$REGION" `
  --dry-run
```

Review only the final `stats`. Required truths:

- `admitted_existing_busy_products > 0`
- `new_non_busy_products_allowed = false`
- `busy_writeback = false`
- `not_introduced_from_full_stihl_catalogue` is expected to be greater than zero
- `price_base = STIHL June 2026`
- `price_effective_from = 2026-06-01`
- no unsafe alias-collision exception
- no non-equivalent BUSY unit conflict
- `unknown_hsn`/`unknown_gst` are allowed incompleteness
- `unit_conversion_candidates` are review items only; no multiplier is invented

STOP on any unit conflict or alias collision.

## 4. AWS authentication and account proof

```powershell
aws sso login --profile $PROFILE
aws sts get-caller-identity --profile $PROFILE --region $REGION
```

Required NonProd account: `272037674623`.

## 5. RDS recovery snapshot

```powershell
$SNAP="echo-nonprod-pre-busy-stihl-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
aws rds create-db-snapshot `
  --db-instance-identifier echo-nonprod-postgres `
  --db-snapshot-identifier $SNAP `
  --profile $PROFILE `
  --region $REGION | Out-Null

aws rds wait db-snapshot-completed `
  --db-snapshot-identifier $SNAP `
  --profile $PROFILE `
  --region $REGION

aws rds describe-db-snapshots `
  --db-snapshot-identifier $SNAP `
  --profile $PROFILE `
  --region $REGION `
  --query "DBSnapshots[0].[DBSnapshotIdentifier,Status,SnapshotCreateTime]" `
  --output table
```

STOP unless status is `available`.

## 6. CodeBuild exact branch

```powershell
$BUILD = aws codebuild start-build `
  --project-name echo-nonprod-runtime-build `
  --source-version "refs/heads/$BRANCH" `
  --profile $PROFILE `
  --region $REGION `
  --output json | ConvertFrom-Json

$BUILDID=$BUILD.build.id
Write-Host "BUILD: $BUILDID"

do {
  Start-Sleep -Seconds 10
  $B=(aws codebuild batch-get-builds `
    --ids $BUILDID `
    --profile $PROFILE `
    --region $REGION `
    --output json | ConvertFrom-Json).builds[0]
  Write-Host $B.buildStatus $B.currentPhase
} while($B.buildStatus -eq "IN_PROGRESS")

if($B.buildStatus -ne "SUCCEEDED"){ throw "CodeBuild failed: $($B.buildStatus)" }
$B | Select-Object id,buildStatus,resolvedSourceVersion,startTime,endTime
```

STOP unless `SUCCEEDED` and resolved source is the intended head.

## 7. Download packaged SAM template

```powershell
$PROJECT=(aws codebuild batch-get-projects `
  --names echo-nonprod-runtime-build `
  --profile $PROFILE `
  --region $REGION `
  --output json | ConvertFrom-Json).projects[0]

$ARTIFACT_BUCKET=($PROJECT.environment.environmentVariables | Where-Object {$_.name -eq "ARTIFACT_BUCKET"}).value
if([string]::IsNullOrWhiteSpace($ARTIFACT_BUCKET)){ throw "ARTIFACT_BUCKET not found" }

$PKG=Join-Path $env:TEMP "echo-packaged-nonprod-runtime.yaml"
aws s3 cp `
  "s3://$ARTIFACT_BUCKET/echo-nonprod/runtime/packaged-nonprod-runtime.yaml" `
  "$PKG" `
  --profile $PROFILE `
  --region $REGION
```

## 8. Create and inspect change set

```powershell
$CS="wo0014-busy-stihl-$(Get-Date -Format 'yyyyMMdd-HHmmss')"

aws cloudformation create-change-set `
  --stack-name echo-nonprod-runtime `
  --change-set-name $CS `
  --change-set-type UPDATE `
  --template-body "file://$PKG" `
  --capabilities CAPABILITY_IAM `
  --parameters `
    ParameterKey=UserPoolId,UsePreviousValue=true `
    ParameterKey=UserPoolClientId,UsePreviousValue=true `
    ParameterKey=WebAllowedOrigin,UsePreviousValue=true `
    ParameterKey=LambdaExecutionRoleArn,UsePreviousValue=true `
    ParameterKey=DbSecretArn,UsePreviousValue=true `
    ParameterKey=DbHost,UsePreviousValue=true `
    ParameterKey=DbName,UsePreviousValue=true `
    ParameterKey=PrivateSubnetA,UsePreviousValue=true `
    ParameterKey=PrivateSubnetB,UsePreviousValue=true `
    ParameterKey=AppSecurityGroup,UsePreviousValue=true `
  --profile $PROFILE `
  --region $REGION | Out-Null

aws cloudformation wait change-set-create-complete `
  --stack-name echo-nonprod-runtime `
  --change-set-name $CS `
  --profile $PROFILE `
  --region $REGION

aws cloudformation describe-change-set `
  --stack-name echo-nonprod-runtime `
  --change-set-name $CS `
  --profile $PROFILE `
  --region $REGION `
  --query "Changes[].ResourceChange.[Action,LogicalResourceId,Replacement,ResourceType]" `
  --output table
```

STOP on database/RDS replacement or any unexpected destructive replacement.

## 9. Execute stack update

```powershell
aws cloudformation execute-change-set `
  --stack-name echo-nonprod-runtime `
  --change-set-name $CS `
  --profile $PROFILE `
  --region $REGION

aws cloudformation wait stack-update-complete `
  --stack-name echo-nonprod-runtime `
  --profile $PROFILE `
  --region $REGION

aws cloudformation describe-stacks `
  --stack-name echo-nonprod-runtime `
  --profile $PROFILE `
  --region $REGION `
  --query "Stacks[0].StackStatus" `
  --output text
```

Required: `UPDATE_COMPLETE`.

## 10. Apply migrations 0014/0015/0016

0016 adds explicit product unit conversions. It does not alter any BUSY source record or infer conversion factors.

```powershell
$MIGPAY=Join-Path $env:TEMP "echo-migration-payload.json"
$MIGOUT=Join-Path $env:TEMP "echo-migration-result.json"
[System.IO.File]::WriteAllText($MIGPAY,'{"confirm":"APPLY_NONPROD_V0_3"}',(New-Object System.Text.UTF8Encoding($false)))

aws lambda invoke `
  --function-name echo-nonprod-schema-migrate `
  --payload "fileb://$MIGPAY" `
  --cli-binary-format raw-in-base64-out `
  "$MIGOUT" `
  --profile $PROFILE `
  --region $REGION `
  --output json

Get-Content $MIGOUT -Raw
```

Required: `migration_complete / nonprod_v0_3`.

## 11. Live BUSY-existing STIHL admission

```powershell
& $PY ".\scripts\sync_stihl_catalog_to_echo.py" `
  --official-json "$OFFICIAL" `
  --tagro-alias-csv "$ALIASES" `
  --busy-item-master "$BUSYMASTER" `
  --effective-from "2026-06-01" `
  --enterprise-id "$ENTERPRISE" `
  --profile "$PROFILE" `
  --region "$REGION"
```

Required:

- schema `tagro.echo.stihl-busy-existing-sync-summary/1`
- `busy_writeback = false`
- `new_non_busy_products_allowed = false`
- `planar_projection = false`
- no refused batch
- only BUSY-existing matched products are inserted/updated
- STIHL June prices are attached only to safe official matches where values exist

## 12. Idempotent replay

Run step 11 unchanged a second time. Same payload must not create duplicate products, aliases or prices.

## 13. Authenticated lookup proof

Use a fresh `$JWT`.

```powershell
$BASE="https://3n1lhlcush.execute-api.ap-south-1.amazonaws.com"
$H=@{Authorization="Bearer $JWT"}

Invoke-RestMethod "$BASE/reference-data?kind=products&q=11192000261&limit=5" -Headers $H |
  ConvertTo-Json -Depth 8
```

Then search by an existing BUSY name/alias, not a newly invented ECHO name:

```powershell
Invoke-RestMethod "$BASE/reference-data?kind=products&q=MS382&limit=10" -Headers $H |
  ConvertTo-Json -Depth 8
```

Both routes must resolve to the same canonical product where the safe alias exists.

## 14. Billing proof using June base

```powershell
$P=(Invoke-RestMethod "$BASE/reference-data?kind=products&q=11192000261&limit=5" -Headers $H).items | Select-Object -First 1
if(!$P){ throw "Product not found" }
if($P.gst_known -ne $true){ throw "GST still unknown; do not bill this item" }

$IDEMP="wo0014-billing-proof-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
$BODY=@{
  enterprise_id=$ENTERPRISE
  branch_code="KVR"
  idempotency_key=$IDEMP
  customer_name="WO0014 NONPROD BILLING PROOF"
  payment_mode="credit"
  lines=@(
    @{
      product_id=$P.product_id
      quantity=1
      unit_price_before_tax=52260
      discount_before_tax=0
      gst_rate=[decimal]$P.gst_rate
    }
  )
} | ConvertTo-Json -Depth 8

$BILL=Invoke-RestMethod "$BASE/billing/issue" -Method Post -Headers $H -ContentType "application/json" -Body $BODY
$BILL | ConvertTo-Json -Depth 8
```

Replay exact same body and require same `bill_id` with `idempotent_replay=true`.

Do not claim BUSY booking until BUSY dock/write/readback is separately proven.

## 15. Unit-conversion admission later

BUSY operational unit remains unchanged. Where a supplier purchase unit differs from the retail/stock unit, first establish the actual manufacturer/supplier conversion factor. Then admit it explicitly to `product_unit_conversions` through a reviewed master-data package/template. Example meaning only:

`1 purchase reel -> N stock Links`

`N` must come from an actual source; never derive it from the word `reel` or a part-number suffix.

## 16. Normal operational sequence

1. Billing
2. Stock Count
3. Service
4. Purchase — including reviewed purchase-pack conversion where needed
5. Closing Cash
6. parts/diagram/callout admission
7. Jain matched-to-existing-BUSY products using the same principle
8. ECHO brand later using the same structures

Planar/intelligence remains a separate higher plane and is not a dependency for foundation operations.
