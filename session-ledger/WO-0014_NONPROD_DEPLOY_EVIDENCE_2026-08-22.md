# WO-0014 NonProd deployment evidence — 2026-08-22

## Scope

This ledger entry records only evidence actually observed during the owner-run NonProd deployment continuation. It does not promote any production, BUSY-booked, web-hosted, or fully reconciled claim.

## Proven deployment evidence

Owner-run PowerShell reported:

- `Successfully created/updated stack - echo-nonprod-runtime in ap-south-1`
- runtime endpoint: `https://3n1lhlcush.execute-api.ap-south-1.amazonaws.com`
- schema migration: `Schema migration confirmed: nonprod_v0_3`
- health: `Health PASS: database_configured=True`
- required deployed functions reported present: `echo-nonprod-runtime`, `echo-nonprod-twin-read`, `echo-nonprod-observation-import`
- terminal deployment marker: `WO-0014 NONPROD RUNTIME DEPLOYMENT COMPLETE`

The deployment initially exposed two packaging/host-compatibility defects before succeeding:

1. Windows PowerShell did not support `Set-Content -Encoding utf8NoBOM`; the deployment path now uses `System.IO.File.WriteAllText(... UTF8Encoding(false))`.
2. The migration Lambda package lacked `typing_extensions`, causing `psycopg` import failure. The governed deploy script now refuses deployment if either `psycopg` or `typing_extensions` is missing from each built function package.

## Planar population state

The owner started the governed checkpointed Planar sync through `scripts/SYNC_PLANAR_TO_ECHO.ps1` against:

- AWS account `272037674623`
- profile `tagro-echo-nonprod`
- database `T:\Dropbox\TAGRO_AUTOMATION\TAGRO_AWS_OS_WAREHOUSE\databases\planar.sqlite`
- manifest `T:\Dropbox\TAGRO_AUTOMATION\TAGRO_AWS_OS_WAREHOUSE\manifests\latest.json`

Observed start evidence:

- `AWS account confirmed: 272037674623`
- assumed-role ARN ended in `/thomas`
- required files confirmed
- `Beginning checkpointed Planar sync...`
- `ECHO PLANAR SYNC database=...planar.sqlite manifest=...latest.json`
- PowerShell process `4776` remained alive at the last observation.

This proves only that the sync passed its local/AWS identity preflight and started. It does **not** prove population completion, counts, or `/twin-history` reconciliation.

## Remaining proof boundary

The following remain explicitly unproven until readback evidence exists:

- authenticated `/whoami` on the current WO-0014 deployment;
- authenticated `/db-health` on the current deployment;
- authenticated `/tenant-context` and `/reference-data` readback;
- a controlled consequential NonProd operational write followed by database-backed readback of the same identifier;
- Planar PostgreSQL population completion and source/target count reconciliation;
- `/twin-history` readback against populated data;
- authorised web/PWA hosting origin deployment and browser smoke;
- BUSY handoff plus BUSY readback; no BUSY booked/live claim is admitted;
- backup/recovery proof and any production admission.

## Deployment evidence improvement

`scripts/VERIFY_WO0014_AUTHENTICATED_NONPROD.ps1` was added after this deployment. It is deliberately separate from the infrastructure deploy script. It hard-stops on the wrong AWS account or wrong API endpoint, proves authenticated identity/database/tenant/reference reads, and can optionally create an idempotent NonProd cash-day proof record and verify that exact returned session id through database-backed `/cash-days` readback. It emits JSON evidence and explicitly excludes Planar/BUSY/web/production claims.

## Current execution blocker for autonomous continuation

The engineering session that recorded this ledger can inspect and modify GitHub but does not have a live AWS execution connector/session or the owner's Cognito JWT. Therefore it cannot independently execute the authenticated proof harness or inspect the running Planar process. The next autonomous-safe action on the AWS host is to collect the Planar checkpoint/log, reconcile `/twin-history`, then run the authenticated proof harness with a valid staff JWT. No redesign is required.
