# WO-0014 — STIHL Product Foundation NonProd Runbook

Purpose: admit the complete STIHL catalogue into the existing ECHO PostgreSQL operational foundation, enrich it with TAGRO/BUSY aliases, preserve HSN/GST unknowns honestly, and verify normal authenticated lookup before Billing proof. Planar is not involved in this runbook.

## Invariants

- Source of canonical STIHL identity: `TAGRO_AUTOMATION/safe_base/master_data/latest/stihl_prices_june_2026.json`.
- TAGRO/BUSY alias enrichment: `TAGRO_AUTOMATION/price_update_2026_27/outputs/TAGRO_STIHL_BUSY_Update_One_Row_Per_Item.csv`.
- BUSY unit enrichment: `TAGRO_AUTOMATION/outputs/stihl_kvr_part_match/TAGRO_BUSY_ITEM_MASTER_ALL_BRANCHES_2026-07-10.csv`.
- Missing HSN/GST is allowed and remains unknown.
- Unknown GST does not hide a product from reference lookup; Billing rejects only that line until GST is populated.
- Aliases may never silently move from one product to another.
- Prices are not written unless an independently defensible `effective_from` date is supplied.
- The current June-named source has no authoritative effective-date field; identity admission therefore runs first with no prices.
- The raw BUSY foundation already loaded into AWS is not rewritten by this path.

## 0. PowerShell session setup

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

## 1. Pull exact branch and prove source files

```powershell
git pull
git --no-pager log -1 --oneline

@($OFFICIAL,$ALIASES,$BUSYMASTER) | ForEach-Object {
  if(!(Test-Path -LiteralPath $_ -PathType Leaf)){ throw "Missing source: $_" }
  Get-Item -LiteralPath $_ | Select-Object FullName,Length,LastWriteTime
}
```

STOP if any source is missing.

## 2. Run the complete local test suite

```powershell
& $PY -m unittest discover -s tests -p "test_*.py" -v
```

STOP unless all tests pass. GitHub Runtime Gate and Governance Gate must also be green for the same head commit.

## 3. Dry-run the full catalogue — no prices

Do not supply `--effective-from` here.

```powershell
& $PY ".\scripts\sync_stihl_catalog_to_echo.py" `
  --official-json "$OFFICIAL" `
  --tagro-alias-csv "$ALIASES" `
  --busy-item-master "$BUSYMASTER" `
  --enterprise-id "$ENTERPRISE" `
  --profile "$PROFILE" `
  --region "$REGION" `
  --dry-run
```

Review `stats` only. Required conditions:

- `unique_products > 0`
- `prices_included = false`
- `prices = 0`
- no alias-collision exception
- review `unknown_hsn` and `unknown_gst` as honest incompleteness, not errors
- `unit_conflicts` must be reviewed before live admission; do not silently accept conflicting BUSY units

## 4. Authenticate AWS and prove account

```powershell
aws sso login --profile $PROFILE
aws sts get-caller-identity --profile $PROFILE --region $REGION
```

Required account: `272037674623`. STOP on any other account.

## 5. Create a pre-deploy RDS snapshot

```powershell
$SNAP="echo-nonprod-pre-catalog-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
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

STOP unless snapshot status is `available`.

## 6. Build/package in AWS CodeBuild

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
  $B = (aws codebuild batch-get-builds `
    --ids $BUILDID `
    --profile $PROFILE `
    --region $REGION `
    --output json | ConvertFrom-Json).builds[0]
  Write-Host $B.buildStatus $B.currentPhase
} while($B.buildStatus -eq "IN_PROGRESS")

if($B.buildStatus -ne "SUCCEEDED"){ throw "CodeBuild failed: $($B.buildStatus)" }
$B | Select-Object id,buildStatus,resolvedSourceVersion,startTime,endTime
```

STOP unless `SUCCEEDED` and `resolvedSourceVersion` is the intended branch head.

## 7. Download the packaged SAM template

```powershell
$PROJECT = (aws codebuild batch-get-projects `
  --names echo-nonprod-runtime-build `
  --profile $PROFILE `
  --region $REGION `
  --output json | ConvertFrom-Json).projects[0]

$ARTIFACT_BUCKET = ($PROJECT.environment.environmentVariables | Where-Object {$_.name -eq "ARTIFACT_BUCKET"}).value
if([string]::IsNullOrWhiteSpace($ARTIFACT_BUCKET)){ throw "ARTIFACT_BUCKET not found" }

$PKG = Join-Path $env:TEMP "echo-packaged-nonprod-runtime.yaml"
aws s3 cp `
  "s3://$ARTIFACT_BUCKET/echo-nonprod/runtime/packaged-nonprod-runtime.yaml" `
  "$PKG" `
  --profile $PROFILE `
  --region $REGION

if(!(Test-Path $PKG)){ throw "Packaged template missing" }
```

## 8. Create and inspect the CloudFormation change set

```powershell
$CS="wo0014-catalog-$(Get-Date -Format 'yyyyMMdd-HHmmss')"

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

Expected: runtime Lambda code/template changes, no database replacement, no RDS replacement, no destructive infrastructure replacement. STOP if anything unexpected appears.

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

## 10. Apply migrations 0014/0015

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

Required response includes:

```json
{"status":"migration_complete","migration_set":"nonprod_v0_3"}
```

This applies only unapplied migrations. Existing 0001-0013 remain ledger-protected and are skipped when already present.

## 11. Live full-catalogue admission — still no prices

Do not add `--effective-from` yet.

```powershell
& $PY ".\scripts\sync_stihl_catalog_to_echo.py" `
  --official-json "$OFFICIAL" `
  --tagro-alias-csv "$ALIASES" `
  --busy-item-master "$BUSYMASTER" `
  --enterprise-id "$ENTERPRISE" `
  --profile "$PROFILE" `
  --region "$REGION"
```

Required:

- schema `tagro.echo.stihl-catalog-sync-summary/1`
- `dry_run = false`
- `planar_projection = false`
- no refused batch
- `inserted + updated + unchanged` reconciles with `stats.unique_products`
- `prices_upserted = 0`

## 12. Idempotent replay proof

Run the exact command in step 11 again. The same source/batches must not create duplicate products or aliases. Record the final summary.

## 13. Authenticated product readback

Use a fresh Cognito JWT. If `$JWT` is already valid, reuse it.

```powershell
$BASE="https://3n1lhlcush.execute-api.ap-south-1.amazonaws.com"
$H=@{Authorization="Bearer $JWT"}

Invoke-RestMethod "$BASE/reference-data?kind=products&q=11192000261&limit=5" -Headers $H |
  ConvertTo-Json -Depth 8
```

Verify the MS 382 record contains canonical product identity, HSN `84678100`, GST `18`, manufacturer part number, and `gst_known=true`.

Then prove TAGRO/BUSY alias lookup with an alias returned by the dry-run/source:

```powershell
Invoke-RestMethod "$BASE/reference-data?kind=products&q=MS382&limit=10" -Headers $H |
  ConvertTo-Json -Depth 8
```

The alias lookup must resolve to the same canonical product identity where that alias is admitted for the enterprise.

## 14. Controlled Billing proof

Fetch a known product first:

```powershell
$P=(Invoke-RestMethod "$BASE/reference-data?kind=products&q=11192000261&limit=5" -Headers $H).items | Select-Object -First 1
$P | ConvertTo-Json -Depth 6
```

STOP if `gst_known` is not true.

For NonProd proof only, use a unique idempotency key and the reviewed source price explicitly; this does not claim that the price table is yet authoritative:

```powershell
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

$BILL=Invoke-RestMethod `
  "$BASE/billing/issue" `
  -Method Post `
  -Headers $H `
  -ContentType "application/json" `
  -Body $BODY

$BILL | ConvertTo-Json -Depth 8
```

Replay the exact same request:

```powershell
$REPLAY=Invoke-RestMethod `
  "$BASE/billing/issue" `
  -Method Post `
  -Headers $H `
  -ContentType "application/json" `
  -Body $BODY

$REPLAY | ConvertTo-Json -Depth 8
```

Required: same `bill_id`, and replay reports `idempotent_replay=true`.

Do not claim BUSY booking from this proof; ECHO correctly returns `busy_status=not_booked_not_confirmed` until the BUSY dock path is separately proven.

## 15. Price admission — later, only after date authority is resolved

When a defensible effective date is established, rerun the same canonical catalogue source with that date:

```powershell
$PRICE_EFFECTIVE="YYYY-MM-DD"

& $PY ".\scripts\sync_stihl_catalog_to_echo.py" `
  --official-json "$OFFICIAL" `
  --tagro-alias-csv "$ALIASES" `
  --busy-item-master "$BUSYMASTER" `
  --effective-from "$PRICE_EFFECTIVE" `
  --enterprise-id "$ENTERPRISE" `
  --profile "$PROFILE" `
  --region "$REGION"
```

This creates effective-dated price rows without redesigning or reimporting the raw BUSY foundation.

## 16. After STIHL foundation proof

Proceed one normal operational flow at a time:

1. Billing
2. Stock Count
3. Service
4. Purchase
5. Closing Cash
6. parts/diagram/callout admission using `data/templates/catalog_parts_import.csv`
7. Jain canonical catalogue/price admission using the same manufacturer-neutral product/parts structures
8. ECHO brand catalogue later using the same structures

Planar/intelligence remains a separate higher plane and is not a dependency for these foundation flows.
