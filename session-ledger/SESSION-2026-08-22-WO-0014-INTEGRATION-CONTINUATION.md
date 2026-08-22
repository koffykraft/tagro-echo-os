# WO-0014 Integration Continuation — 2026-08-22

## Preflight completed
Read and reconciled the active Constitution, Historical Continuity Amendment, Foundation Manifest, Current State, Decision Ledger, History Memory, History Index, TAGRO vertical deployment directive, WO-0014, latest deployment evidence, PR history and current branch/runtime files before changing code.

## Earlier continuation reconciliation
The branch had advanced 13 commits beyond the earlier state record. Most changes were useful and retained: PowerShell UTF-8 compatibility, `typing_extensions` packaging validation, the authenticated verification harness, Planar source-integrity hardening, checkpointed sync improvements and deployment evidence.

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

## Branding and canonical-page verification
Direct file inspection verified TAGRO STIHL identity on canonical Home, Billing, Service, Stock Count, Purchase, Closing Cash, Business and Intelligence pages. These surfaces use the admitted responsive `assets/brand/tagro-stihl-mobile.png` and `tagro-stihl-desktop.png` artwork and TAGRO STIHL page titles. `web/manifest.webmanifest` also names the installed app `TAGRO STIHL`.

ECHO is retained as operational platform/runtime context — for example Operational Twin, shared PostgreSQL runtime, ECHO issue/acceptance and Observer vocabulary — rather than being presented as the TAGRO dealership brand. This matches the active TAGRO vertical deployment directive.

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

The canonical Home explicitly labels network and synchronization as separate states and exposes PostgreSQL history as business memory. Billing states that ECHO admission writes sale/lines/stock movement/payment evidence/audit event together in PostgreSQL while BUSY remains unbooked until separate readback. Stock Count preserves COUNT != MOVEMENT semantics. Closing Cash uses the shared PostgreSQL session and does not silently alter a submitted day.

## Gate evidence
Before repair, head `c8b5e21ca03efeb8b307731c3410a445cdb69669` had Governance #551 and Runtime #532 green, but those gates had failed to detect the authentication regression and therefore were insufficient admission evidence.

After the authenticated-boundary repair and this session ledger update, repaired head `0794bbc85a647bee818016b0b89e39107b03697a` completed:
- Governance Gate #558: **PASS**;
- Runtime Gate #539: **PASS**.

`governance/state/CURRENT_STATE.json` was then updated to record the repaired green boundary and the actual remaining proof limits.

## Actually proven now
- repaired authenticated repository boundary: CI-green;
- NonProd WO-0014 runtime deployment: proven from owner-run evidence;
- `nonprod_v0_3`: proven applied;
- PostgreSQL-primary design/runtime path: proven deployed, with earlier authenticated database reachability evidence;
- TAGRO STIHL identity across the inspected canonical operating pages: directly verified;
- ECHO retained as separate platform/runtime identity: directly verified;
- offline queue/idempotency/pending-review-ack semantics: directly verified;
- Planar checkpointed sync: started, not completed.

## Still unexecuted / unproven
- whether the deployed API stack currently matches the repaired authenticated branch if the superseded open-runtime continuation was ever deployed after the owner-run proof;
- Planar completion and source/target count reconciliation;
- `/twin-history` readback against populated Planar data;
- current authenticated `/whoami`, `/db-health`, `/tenant-context`, `/reference-data` proof on the repaired deployed boundary;
- one controlled idempotent operational write with PostgreSQL readback of the same identifier;
- authorised TAGRO web/PWA hosting smoke;
- BUSY handoff plus BUSY readback;
- backup/recovery drill;
- production admission.

## Next safe action
Collect the already-started Planar sync checkpoint/log and reconcile target counts plus `/twin-history`. Then ensure the deployed stack matches the repaired Cognito-authenticated branch and run `scripts/VERIFY_WO0014_AUTHENTICATED_NONPROD.ps1` for identity/database/tenant/reference plus one controlled write/readback. Do not redesign engines, PostgreSQL or Planar structures for these proofs.
