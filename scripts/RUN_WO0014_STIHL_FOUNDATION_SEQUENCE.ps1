param(
  [string]$AwsProfile = 'tagro-echo-nonprod',
  [string]$Region = 'ap-south-1',
  [string]$SnapshotId = 'echo-nonprod-pre-catalog-20260823-100906'
)

$ErrorActionPreference='Stop'

throw @'
RETIRED RUNNER — DO NOT DEPLOY FROM THIS FILE.

Reason:
This runner belonged to the earlier STIHL June-price / one-row admission path. WO-0014 now uses the BUSY/TD exact-part identity foundation and reconciliation v3. Reusing the former sequence would make an obsolete commercial source the admission boundary again.

Required path before any deployment:
1. Explicit git pull on wo-0014-database-primary-pages-deploy.
2. Run SCOUT_WO0014_STIHL_FOUNDATION.ps1 (immutable, non-deploying).
3. Review its saved v3 identity reconciliation evidence.
4. Use the replacement identity-foundation deployment runner only after that runner has its own path/dependency gates and has been admitted.

No AWS build, CloudFormation change set, migration, catalogue import, BUSY writeback, or Planar action was attempted by this retired runner.
'@
