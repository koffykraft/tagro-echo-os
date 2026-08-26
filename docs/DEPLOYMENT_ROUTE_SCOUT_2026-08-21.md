# TAGRO ECHO OS — Deployment Route Scout & Horizon Study

Date: 2026-08-21
Scope: WO-0012 draft branch only
Intent: prepare the shortest safe route from current NonProd implementation to deployable daily-business operation without feature churn, semantic rewrites or callbacks caused by known dependencies.

## Convoy doctrine

The build advances only when the next road segment has been preflighted. Issues are classified by planar consequence, not by cosmetic severity.

- **RED / convoy blocker** — can stop daily operation, create duplicate/false business truth, leak authority/data, or force structural rewrite if deferred.
- **AMBER / route drag** — materially reduces usefulness or creates review load, but can be isolated while the convoy passes.
- **GREEN / side lane** — valuable improvement that can be repaired after the operational convoy is through.

Prismatic rule: do not force a narrow interpretation when evidence does not support it. Broad/unknown states remain explicit until corroborated.

## Mind map

```text
DAILY BUSINESS DESTINATION
|
+-- Identity / Authority
|   +-- Cognito JWT boundary
|   +-- Enterprise membership + capability
|   +-- browser/mobile login + session
|   +-- user/device/enterprise-local isolation
|
+-- Phone/Web vehicle
|   +-- static hosting/domain
|   +-- API base + Authorization client
|   +-- PWA cache
|   +-- offline queue/replay/ack
|   +-- reference search
|
+-- Operational Driver
|   +-- Billing
|   |   +-- sale
|   |   +-- stock movement
|   |   +-- payment evidence
|   |   +-- invoice/BUSY series + result readback
|   +-- Service intake
|   +-- Purchase Order lifecycle
|   +-- Stock Count
|   +-- Closing Cash
|
+-- Business truth inputs
|   +-- branch/user master
|   +-- products/prices/GST
|   +-- customers/suppliers
|   +-- opening/current stock
|   +-- current BUSY/TD feed
|
+-- Financial Health / Prism
|   +-- sales
|   +-- historical purchase references / LIFO-style cost
|   +-- Closing Cash
|   +-- bank statements
|   +-- expense meaning
|   +-- ON CALL projection + coverage
|
+-- Docked accounting
|   +-- BUSY local bridge
|   +-- dedicated ECHO series
|   +-- queued != booked
|   +-- result/readback/reconciliation
|
+-- Recovery / release
    +-- migration/package reproducibility
    +-- database backup/restore proof
    +-- rollback
    +-- phone smoke run
    +-- parallel business-day reconciliation
    +-- owner production admission
```

## Route branches and horizon effects

### R1 — Browser authentication and API routing — RED

**Observed:** API Gateway is JWT-authorized through the `Authorization` header. Current phone pages call relative paths such as `/billing/issue` and use `credentials:'include'`; no shared browser auth client currently supplies a Bearer JWT or an explicit API base. The SAM template has no CORS policy for a separately hosted web app.

**If allowed to remain:** pages may appear complete but return 401, call the static-site origin instead of API Gateway, or require one-off per-page patches. This is a direct deployment stall and a rewrite multiplier.

**Rectify now:** one shared runtime client; explicit environment config; Cognito login/session contract; Authorization header; API-base routing; CORS/hosting contract. All operational pages use the same client.

### R2 — Service-worker cache boundary — RED

**Observed:** current service worker handles every GET request from controlled pages and writes successful responses to Cache Storage. Once APIs are cross-origin authenticated GETs, tenant context or owner financial responses could be cached as if they were static assets.

**If allowed to remain:** stale financial truth or prior-user data may be replayed from device cache. This is both a truth and privacy failure.

**Rectify now:** cache same-origin admitted static shell only. Never cache API/auth/financial/reference responses.

### R3 — Offline persistence/replay identity — RED

**Observed:** phone pages save local work, but Service/PO/Stock primarily make one immediate runtime attempt. There is no common durable replay/ack loop. LocalStorage keys are not yet principal + enterprise scoped.

**If allowed to remain:** real staff work captured during a network failure can remain stranded indefinitely; shared devices can mix users/enterprises; repeated manual retry can create static review burden.

**Rectify now:** common device queue with principal/enterprise/device scope, stable idempotency keys, reconnect replay, acknowledgement, failed/review state and sign-out isolation.

### R4 — Operational master/reference admission — RED

**Observed:** read-only reference API exists for branches/products/customers/suppliers, but daily pages are not yet wired to it and there is no proven governed load of the required operational masters into PostgreSQL.

**If allowed to remain:** staff must type internal IDs or runtime calls reject valid work because entities do not exist in the operational store.

**Rectify now:** deterministic master/bootstrap load with stable IDs and reconciliation report; then wire all phone pickers/searches to `/reference-data`.

### R5 — Opening/current stock truth — RED

**Observed:** runtime stock position is derived only from ECHO `stock_movements`. No proven current BUSY/warehouse stock snapshot has yet been admitted as an opening movement set for go-live.

**If allowed to remain:** Billing sees zero/incorrect stock and either rejects sales or pushes owner override into routine use. That would destroy exception meaning and produce stock drift from day one.

**Rectify now:** obtain verified branch/item current stock at a declared cutover instant; admit it as provenance-bearing opening stock movements; reconcile totals before first live sale. From that cutover, ECHO movements advance operational stock.

### R6 — Billing payment truth — RED

**Observed:** Billing marks non-credit bills `paid` from the selected payment mode but does not create separate governed payment evidence in PostgreSQL. Existing doctrine says a sale does not itself prove receipt.

**If allowed to remain:** cash/UPI/card/bank receipt truth collapses into sale truth, contaminating Closing Cash, bank reconciliation and Financial Health.

**Rectify now:** add admitted payments/payment-allocation persistence and create/allocate staff-confirmed receipt evidence transactionally where appropriate; retain unpaid/unknown when receipt is not established.

### R7 — Statutory/customer invoice + BUSY booking roundtrip — RED for daily billing

**Observed:** ECHO runtime creates an operational sale and GST amount but has no admitted statutory invoice-number/HSN/place-of-supply snapshot model. BUSY Dock v1 explicitly says write admission is outside v1 and queued handoff is not a booked voucher.

**If allowed to remain:** ECHO can record a sale but cannot truthfully claim the GST/customer invoice that the current transition plan expects BUSY to produce. Staff would need duplicate manual billing and the migration would fail operationally.

**Rectify now:** define ECHO operational bill identity separately from statutory BUSY voucher identity; create dedicated branch ECHO BUSY series mapping; local bridge posts to copied/nonprod BUSY first; result/readback returns booked voucher number/tax details; only then admit first real branch bridge.

### R8 — Closing Cash shared runtime — RED for Financial Health

**Observed:** sophisticated Closing Cash engine exists in repository logic, but current phone Closing Cash remains local-only. PostgreSQL currently holds a simplified aggregate closing shape rather than the full entry/audit lifecycle.

**If allowed to remain:** ON CALL cannot reliably receive daily branch expense/cash evidence and local closings become another island requiring later migration/reconciliation.

**Rectify now:** admit shared Closing Cash lifecycle/entry schema and authenticated routes while preserving physical/noncash, expense/contra/deposit distinctions and idempotency. Phone offline queue submits the same contract.

### R9 — Financial purchase-cost policy alignment — RED for owner profit figures

**Observed:** established TAGRO rolling purchase reference logic keeps recent external purchases (5/3/1) plus protected historical maximum. Current ECHO Financial Health engine takes up to four references but uses their median as estimated unit cost. The owner's intended method is LIFO-style latest acquisition cost with several nearby prices available for comparison and prior-FY fallback.

**If allowed to remain:** ON CALL gross-profit numbers can systematically differ from the existing TAGRO Daily reasoning even when both use the same purchase evidence.

**Rectify now:** make latest valid external purchase the LIFO-style primary cost reference; keep 3/4+ recent observations and protected/high comparison evidence as confidence/range context; retain prior-FY fallback and stock-transfer exclusion.

### R10 — Financial evidence completeness / Prism consequence admission — AMBER moving toward RED

**Observed:** warehouse sales/cost observations can feed ON CALL only after a complete manifested import run. Closing Cash aggregate expenses remain unknown-classified and bank rows are intentionally unresolved until Prism consequence exists.

**If allowed to remain:** ON CALL remains honest but incomplete, especially below gross profit.

**Rectify in main convoy after R8/R9:** connect Closing Cash + bank Prism outputs to governed expense roles. Unknowns remain excluded and visibly valued.

### R11 — Purchase Order approval lifecycle — AMBER

**Observed:** authenticated PO creation safely creates `draft`; no owner approval route is yet present.

**If allowed to remain:** PO capture works, but supplier purchasing still requires another procedure and draft static can accumulate.

**Rectify after billing/cash road opens:** owner approval/reject/supersede and governed supplier-instruction handoff.

### R12 — Service progression beyond intake — GREEN for first deployment

**Observed:** shared runtime currently covers service intake. Existing domain supports more concepts, but full repair/estimate/ready runtime progression is not yet the immediate dependency for accepting machines.

**If allowed to remain:** service can begin and later stages remain manual/legacy temporarily.

**Rectify side lane after convoy:** add repair/estimate/parts/ready transitions without changing intake identity.

### R13 — Bank direct adapter — AMBER

**Observed:** bank normalization and historical learning exist, but production direct bank-source adapters are unadmitted.

**If allowed to remain:** bank status is import-driven/stale rather than live; ON CALL must label freshness.

**Rectify side lane unless a bank source becomes necessary for first counter:** governed statement import first; direct connector later.

### R14 — Database recovery / production boundary — RED before business production

**Observed:** architecture requires point-in-time recovery and tested restore before production. WO-0012 success criteria require a NonProd recovery check. Current repository does not contain evidence of a completed restore drill. Architecture also requires production/non-production account separation before production launch.

**If allowed to remain:** a technically functional counter could become dependent on an environment whose recovery and production isolation have not been proven.

**Rectify before owner production admission:** perform NonProd backup/restore drill; document RTO/RPO observations; prepare separate production account/runtime from the same admitted infrastructure package; no direct promotion of test data or credentials.

### R15 — Static prototype surfaces on staff home — AMBER

**Observed:** index still exposes old local prototypes beside newly authenticated workflows.

**If allowed to remain:** staff can enter operational data into a local-only page believing it is shared, building static and support burden.

**Rectify before staff onboarding:** staff home shows only admitted functions; prototypes/tools move behind explicit Admin/Toolbox surface and remain visibly local where retained.

### R16 — Runtime scaling/connection management — GREEN for first controlled counters

**Observed:** Lambda opens PostgreSQL connections directly and resolves Secrets Manager per invocation; no RDS Proxy is currently admitted.

**If allowed to remain at first-counter scale:** probably measurable rather than immediately blocking, but must be observed.

**Rectify when evidence warrants:** measure concurrency/connection pressure and admit RDS Proxy or another pool only if required; do not redesign pre-emptively.

## Business branch rollout horizon

Configured current TD source branches are KVR, PKM, NDD, MDM and SKT. No branch should be declared ready simply because its source feed exists. Each branch receives the same cutover checklist:

1. identity/users/capabilities valid;
2. branch master identity reconciled;
3. product/customer/supplier references loaded;
4. opening stock cutover snapshot verified;
5. dedicated ECHO BUSY series configured and copied-company bridge passed;
6. phone install/login passed;
7. bill -> payment -> stock -> BUSY result reconciliation passed;
8. Closing Cash day-close passed;
9. offline/reconnect replay passed;
10. rollback route known.

Branch-specific deviations are recorded rather than patched into common code unless they represent a genuine reusable business rule.

## Marching order

### Convoy Stage 0 — route hardening

R1, R2, R3, R9. These influence nearly every later surface and are cheaper to fix before more wiring.

**Gate:** one authenticated runtime client, safe static cache, durable scoped offline queue, Financial Health cost policy aligned with source logic; Runtime + Governance green.

### Convoy Stage 1 — real operational state

R4, R5, R6. Load governed masters and opening stock; establish separate payment truth; wire real reference search.

**Gate:** one controlled NonProd enterprise can issue an ECHO sale using real references, decrement verified stock and record payment evidence with idempotent retry.

### Convoy Stage 2 — money close and owner visibility

R8 then R10. Shared Closing Cash lifecycle; Prism consequences; manifested Financial Health evidence; ON CALL verification.

**Gate:** a real business day can be reconstructed from sale/payment/Closing Cash evidence and ON CALL explicitly states known/unknown coverage.

### Convoy Stage 3 — BUSY transition bridge

R7. Dedicated ECHO series, copied-company write/readback, reconciliation and failure queue.

**Gate:** ECHO bill -> BUSY booked result -> voucher identity/readback, with no duplicate posting on replay and no false booked state.

### Convoy Stage 4 — remaining core workflows

R11 and staff reference wiring for Service/PO/Stock Count. Hide/isolate R15 prototype surfaces.

**Gate:** staff can perform Billing, Service intake, PO proposal/approval and Stock Count from phone without entering internal IDs or local-only truth accidentally.

### Convoy Stage 5 — deployment proof

R14: NonProd restore/rollback drill, representative Android/iPhone/PWA install, network-loss tests, first-counter parallel day, end-of-day reconciliation.

**Gate:** evidence-based production-readiness report. Production remains a separate owner-admitted step.

## Side convoy after passage

R12 full Service Memory/progression, R13 direct bank adapters, R16 scale optimization, Page Toolbox/instance lifecycle extensions and ECHO Futures remain available but must not obstruct first daily-business operation.

## Current scouting conclusion

The destination is reachable without replacing the current architecture. The principal risk is not a missing core engine; it is a set of **integration seams that would otherwise create false completion**: browser auth/API origin, unsafe cache scope, offline replay, operational master/stock cutover, payment separation, Closing Cash shared persistence, LIFO cost-policy alignment, BUSY statutory roundtrip and recovery proof.

Repairing these seams now should let the existing Driver/domain/runtime body continue forward without a later rebuild.
