# WO-0014 Integration Continuation — 2026-08-22

## Preflight completed
Read and reconciled the active Constitution, Historical Continuity Amendment, Foundation Manifest, Current State, Decision Ledger, History Memory, History Index, TAGRO vertical deployment directive, WO-0014, latest deployment evidence, PR history and current branch/runtime files before changing code.

## Earlier continuation reconciliation
The branch had advanced 13 commits beyond the state record. Most changes were useful and retained: PowerShell UTF-8 compatibility, `typing_extensions` packaging validation, the authenticated verification harness, Planar source-integrity hardening, checkpointed sync improvements and deployment evidence.

One duplicate approach was not admissible: `src/aws_runtime/open_handler.py`, `scripts/DEPLOY_TAGRO_RUNTIME.ps1`, and the modified SAM template removed Cognito protection and resolved every request as a server-selected OWNER actor. This contradicted Constitution §19, DEC-0013, the History Index preference `authenticated_api_lambda`, the deployment directive's protected server-side authority invariant and WO-0014 success criteria requiring authenticated readback/write.

Repair performed:
- restored `architecture/aws/nonprod-runtime-template.yaml` to the Cognito JWT default-authorizer boundary;
- retained `/health` as the only explicitly unauthenticated endpoint;
- restored `src.aws_runtime.handler.lambda_handler` and `src.aws_runtime.twin_read_handler.lambda_handler`;
- deleted `src/aws_runtime/open_handler.py`;
- deleted `scripts/DEPLOY_TAGRO_RUNTIME.ps1`;
- preserved the successful `DEPLOY_WO0014_NONPROD.ps1`, packaging and Planar-sync fixes.

No engine, PostgreSQL schema, Planar source structure or admitted data semantics were changed.

## Proven deployment evidence carried forward
Owner-run NonProd execution proved:
- CloudFormation stack `echo-nonprod-runtime` created/updated in `ap-south-1`;
- endpoint `https://3n1lhlcush.execute-api.ap-south-1.amazonaws.com`;
- `nonprod_v0_3` migration confirmed;
- health PASS with `database_configured=True`;
- functions `echo-nonprod-runtime`, `echo-nonprod-twin-read`, `echo-nonprod-observation-import` present;
- terminal marker `WO-0014 NONPROD RUNTIME DEPLOYMENT COMPLETE`.

The governed Planar sync also passed AWS/file preflight and started against account `272037674623`; process `4776` was alive at last owner observation. This is **start evidence only**. Completion, target counts and `/twin-history` reconciliation remain unproven.

## Branding verification
Direct file inspection verified:
- `web/index.html` title is `TAGRO STIHL`;
- Home uses responsive `assets/brand/tagro-stihl-mobile.png` and `tagro-stihl-desktop.png` with alt `TAGRO STIHL`;
- ECHO appears as operational platform/context (`ECHO OPERATIONAL TWIN · DATABASE PRIMARY`), not as the TAGRO dealership brand;
- `web/manifest.webmanifest` name/short_name are `TAGRO STIHL`, describing the app as TAGRO STIHL on the ECHO platform.

This matches the active vertical directive: TAGRO STIHL is the current TAGRO dealership identity; ECHO remains separate platform/vertical context.

## PostgreSQL-primary and offline semantics verification
`web/runtime-client.js` confirms:
- authenticated Cognito session is required before scoped local operational work;
- server requests carry the Cognito bearer token;
- offline queue keys are scoped by principal + enterprise + device;
- mutation payloads carry idempotency keys;
- reuse of an idempotency key with changed payload is rejected locally;
- retryable/network errors remain `pending`;
- deterministic rejection moves work to `review`;
- only server-confirmed operations enter the acknowledgement journal;
- local queue state is not treated as database acknowledgement.

The canonical Home explicitly labels network and synchronization as separate states and exposes PostgreSQL history as business memory.

## Gate evidence
Before this repair, the then-head `c8b5e21ca03efeb8b307731c3410a445cdb69669` had:
- Governance Gate #551: PASS;
- Runtime Gate #532: PASS.

Those gates did not detect the constitutional authentication regression, so their success was insufficient evidence for admission of the open-runtime change. The repaired head requires fresh Governance/Runtime gate proof before further deployment claims.

## Actually proven now
- NonProd WO-0014 runtime deployment: proven.
- `nonprod_v0_3`: proven applied.
- PostgreSQL-primary design/runtime path: proven deployed; prior authenticated DB path proven historically; current authenticated endpoint proof still needs rerun.
- TAGRO STIHL Home/PWA branding: directly verified in current files.
- offline queue semantics: directly verified in current runtime client.
- Planar checkpointed sync: started, not completed.

## Still unexecuted / unproven
- fresh CI gates on the repaired authenticated head;
- Planar completion and source/target count reconciliation;
- `/twin-history` readback against populated Planar data;
- current authenticated `/whoami`, `/db-health`, `/tenant-context`, `/reference-data` proof;
- one controlled idempotent operational write with PostgreSQL readback of the same identifier;
- authorised TAGRO web/PWA hosting smoke;
- BUSY handoff plus BUSY readback;
- backup/recovery drill;
- production admission.

## Next safe action
First confirm fresh Governance and Runtime gates on the repaired head. Then collect the already-running Planar sync checkpoint/log and reconcile target counts plus `/twin-history`. Only after that run `scripts/VERIFY_WO0014_AUTHENTICATED_NONPROD.ps1` with a valid staff JWT for identity/database/tenant/reference and one controlled write/readback. Do not redesign engines or database structures for these proofs.
